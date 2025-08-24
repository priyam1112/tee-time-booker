import logging
import os
import time
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By


# Set logging to gauge when program should be scheduled to start
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logfile.log")
    ]
)


# getPHPSessionID(), getOtherCookies(), getCSRFToken() are separately accessed to
# store the necessary cookies for login from the various BRS Golf domains
def getPHPSessionID(session, url):
    session.get(url)

    # print('getPHPSessionID() Cookies *****************')
    # print(session.cookies)


def getOtherCookies(session, url):
    session.get(url)

    # print('getOtherCookies() Cookies *****************')
    # print(session.cookies)
    # print('\n')


def getCSRFToken(session, url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/115.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = session.get(url, headers=headers)
    #print("response", response.text)
    soup = BeautifulSoup(response.content, 'html.parser')
    csrf_token_tag = soup.find('input', {'name': 'login_form[_token]'})
    if csrf_token_tag:
        csrf_token = csrf_token_tag['value']
    else:
        raise RuntimeError("Could not find CSRF token in login form. Page HTML:\n" + soup.prettify())

    # print('getOtherCookies() Cookies *****************')
    # print(session.cookies)
    # print('CSRF token: ' + csrf_token)
    # print('\n')

    return csrf_token


def getTimeSheet(session, csrf_token):
    # Perform the login and obtain the necessary authentication token or cookies
    login_url = f'https://members.brsgolf.com/{club_name}/login'

    payload = {
        'login_form[username]': username,
        'login_form[password]': password,
        'login_form[login]': '',
        'login_form[_token]': csrf_token,
    }

    headers = {
        'authority': 'members.brsgolf.com:',
        'method': 'POST',
        'path': f'/{club_name}/login',
        'scheme': 'https',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'cache-control': 'max-age=0',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://members.brsgolf.com',
        'referer': f'https://members.brsgolf.com/{club_name}/login'
    }

    try:
        response = session.post(login_url, headers=headers, data=payload)
        response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes

        # Check if the login was successful and retrieve the necessary authentication information
        if response.status_code == 200:
            logging.info('<--- LOGIN SUCCESSFUL! --->')
            # print('TEE TIME REFS......................')
            # print(session.cookies)

        else:
            print('Login failed.')
            print(response.status_code)
            print(response.reason)

    except requests.exceptions.RequestException as e:
        print('An error occurred during login:', e)


# Selenium webdriver is required to access token values and other identifiers that are generated
# via Javascript and hiddden in the HTML page source. Other libraries could not render the Javascript
# properly; hence, it was a last resort.
#
# The key value needed is a href for each booking slot that contains a dynamically generated token
def getDynamicHTML(date):
    url = f'https://members.brsgolf.com/{club_name}/tee-sheet/1/{date}'

    # Create a new Chrome browser instance using Selenium
    driver = webdriver.Chrome()

    # Initial page load to pull down and align cookie domains
    driver.get(url)

    # delete the current cookies
    driver.delete_all_cookies()

    # Convert CookieJar to Selenium's dictionary format
    cookies_dict = {}

    for cookie in session.cookies:
        # Omit cookie expiry property if the cookie is a session cookie
        if cookie.expires == None:
            cookies_dict[cookie.name] = {
                'name': cookie.name,
                'value': cookie.value,
                'path': cookie.path,
                'domain': cookie.domain,
                'secure': cookie.secure
            }
        else:
            cookies_dict[cookie.name] = {
                'name': cookie.name,
                'value': cookie.value,
                'path': cookie.path,
                'domain': cookie.domain,
                'secure': cookie.secure,
                'expiry': cookie.expires
            }

        driver.add_cookie(cookies_dict[cookie.name])

    # Give time for all HTML to load, otherwise it is intermittently missed
    driver.implicitly_wait(10)

    # Navigate to the webpage using Selenium
    driver.get(url)
    driver.find_elements(By.CSS_SELECTOR, "tr.bg-white.even\\:bg-grey-faded")

    # Get the page source after JavaScript execution
    page_source = driver.page_source

    # Close the browser
    driver.quit()

    return page_source


def hrefParser(dynamic_html, tee_time_preferences):
    soup = BeautifulSoup(dynamic_html, "html.parser")


    # Find the all timesheet rows
    tr_elements = soup.find_all("tr", class_="bg-white even:bg-grey-faded")

    # Initialise empty array and flag
    available_tee_times_hrefs = []
    tee_time_available = True

    for time in tee_time_preferences:
        # Find <tr> elements containing tee times
        for tr_element in tr_elements:
            tee_time_available = True  # Reset tee_time_available for each tr_element
            if time in tr_element.text:
                # Multiple conditions in above did not work consistently.
                # Div elements separated for filtering
                div_elements = tr_element.find_all("div")
                for div_element in div_elements:
                    # All bookings with 1-4 players have '18 Holes' text added to first column
                    if 'Holes' in div_element.text:
                        tee_time_available = False
                # If 'Holes' isn't in the table row then all 4 slots available
                if tee_time_available:
                    # Find the anchor tag and extract its href value
                    anchor_tag = tr_element.find('a')
                    if anchor_tag and 'href' in anchor_tag.attrs:
                        href_value = anchor_tag['href']
                        available_tee_times_hrefs.append(href_value)

    # print('TEE TIME REFS......................')
    # print(available_tee_times_hrefs)

    return available_tee_times_hrefs


def bookingSlotTokens(session, available_tee_times_hrefs):
    tokens_array = []  # Create an empty array to store the tokens

    for hrefs in available_tee_times_hrefs:

        tokens_array_inner = []
        url = f'https://members.brsgolf.com{hrefs}'

        try:
            response = session.get(url)
            response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes
            response_content = response.content

            soup = BeautifulSoup(response_content, 'html.parser')
            token_1 = soup.find('input', {'name': '_token'})['value']
            #token_2 = soup.find('input', {'name': '_token'})['value']

            # Add the tokens to the array
            tokens_array_inner.append(token_1)
            #tokens_array_inner.append(token_2)
            tokens_array.append(tokens_array_inner)

            # print('MEMBER TOKENS......................')
            # print(tokens_array)

        except requests.exceptions.RequestException as e:
            print(f"An error occurred while fetching tokens for {url}: {e}")

    # Optionally, you may want to log the extracted tokens
    logging.info("Tokens array: %s", tokens_array)

    return tokens_array


def bookTeeTime(session, hrefs, tokens, player_1, player_2="", player_3="", player_4=""):
    i = 0
    status_code = 0
    response = None

    logging.info("Reaching bookTeeTime while loop...")

    # Tries to book initial time slot (href), if it fails, it then tries the 2nd, and so on.
    # hrefs array can only be max length of three, so it will only try three times at most.
    while status_code != 200 and i < len(hrefs):
        split_date_time = hrefs[i].split('/')
        time = split_date_time[-1]
        date = split_date_time[-2]

        url = f"https://members.brsgolf.com/{club_name}/bookings/store/1/{date}/{time}"

        payload = {
            f'_token': {tokens[i][0]},
            'member_booking_form[holes]': 18,
            'member_booking_form[player_1]': player_1,
            'member_booking_form[player_2]': player_2,
            'member_booking_form[player_3]': player_3,
            'member_booking_form[player_4]': player_4,
            'member_booking_form[vendor-tx-code]': ''
        }

        # For whatever reason, a successful request requires an empty files array
        files = []

        try:

            logging.info("Sending POST request for %s", url)

            response = session.post(url, data=payload, files=files)

            i += 1
            status_code = response.status_code

            # Optionally, log the response content for debugging
            # print(response.status_code)
            # print(response.content)

        except requests.exceptions.RequestException as e:
            print(f"An error occurred during the booking attempt: {e}")
            response = None

    return response


if __name__ == "__main__":
    logging.info("Script started at: %s", datetime.now())

    # Use environment vars to protect secrets
    load_dotenv()
    username = os.environ['BRS_USERNAME']
    password = os.environ['BRS_PASSWORD']
    player_1 = os.environ['PLAYER_1']
    player_2 = os.environ['PLAYER_2']
    player_3 = os.environ['PLAYER_3']
    player_4 = os.environ['PLAYER_4']
    club_name = os.environ['CLUB_NAME']


    # URLs
    club_brs_url = f'https://brsgolf.com/{club_name}'
    club_members_brs_url = f'https://members.brsgolf.com/'
    club_login_brs_url = f'https://members.brsgolf.com/{club_name}/login'

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/115.0 Safari/537.36",
        "Referer": club_login_brs_url,
    })

    # Prefs

    tee_time_preferences = ["08:22", "08:30", "08:37", "08:45", "08:52", "09:22", "16:22", "16:30", "16:37", "16:45", "16:52", "18:30"]
    # tee_time_date = '2025/08/23'
    tee_time_date = (datetime.today() + timedelta(days=5)).strftime("%Y/%m/%d")
    logging.info("Booking date is %s ", tee_time_date)
    # Run continuously until success
    booking_success = False
    attempt = 0
    getPHPSessionID(session, club_brs_url)
    logging.info("got PHP session ID")
    getOtherCookies(session, club_members_brs_url)
    logging.info("got cookies")
    csrf_token = getCSRFToken(session, club_login_brs_url)
    logging.info("got csrf token")
    getTimeSheet(session, csrf_token)
    logging.info("get timesheet")
    while not booking_success:
        attempt += 1
        logging.info("Attempt #%s at %s", attempt, datetime.now())
        try:

            available_tee_times_hrefs = []

            dynamic_html = getDynamicHTML(tee_time_date)
            logging.info("get dynamic_html ")
            available_tee_times_hrefs = hrefParser(dynamic_html, tee_time_preferences)

            if not available_tee_times_hrefs:
                logging.info("No tee times found. Retrying in 2s...")
                time.sleep(1)
                continue
            logging.info("get available_tee_times_hrefs %s", available_tee_times_hrefs)
            booking_tokens = bookingSlotTokens(session, available_tee_times_hrefs)
            logging.info("get booking_tokens %s", booking_tokens)
            response = bookTeeTime(session, available_tee_times_hrefs, booking_tokens, player_1, player_2, player_3, player_4)
            if response and response.status_code == 200:
                logging.info(" bookTeeTime response %s", response)
                booking_success = True
            else:
                logging.info("Booking failed (status: %s). Retrying in 2s...",
                             response.status_code if response else "None")
                time.sleep(2)

        except Exception as e:
            logging.error("Error during attempt #%s: %s", attempt, e, exc_info=True)
            time.sleep(3)
