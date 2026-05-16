#!/usr/bin/env python3
"""
IndieGala Auto-Spin Bot
Automatically logs in and spins the daily Wheel of Fortune
Uses stealth techniques to avoid CAPTCHA detection
"""

import os
import sys
import time
import random
from pathlib import Path
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, will use environment variables


def random_delay(min_sec=0.5, max_sec=2.0):
    """Add random human-like delay"""
    time.sleep(random.uniform(min_sec, max_sec))


def human_type(element, text, debug=False):
    """Type text with random human-like delays between keystrokes"""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))
    if debug:
        print(f"Typed text with human-like timing")


def spin_wheel(headless=True, debug=False):
    """
    Login to IndieGala and spin the daily wheel

    Args:
        headless: Run browser in headless mode (no visible window)
        debug: Enable debug output
    """
    # Get credentials from environment variables
    email = os.getenv('INDIEGALA_EMAIL')
    password = os.getenv('INDIEGALA_PASSWORD')

    if not email or not password:
        print("ERROR: Please set INDIEGALA_EMAIL and INDIEGALA_PASSWORD environment variables")
        sys.exit(1)

    # Path to store persistent browser session
    user_data_dir = Path.home() / '.indiegala-session'
    user_data_dir.mkdir(exist_ok=True)

    # Configure undetected Chrome options
    options = uc.ChromeOptions()
    options.add_argument(f'--user-data-dir={user_data_dir}')

    # Additional stealth arguments
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-setuid-sandbox')

    if headless:
        options.add_argument('--headless=new')

    # Initialize undetected chromedriver
    if debug:
        print("Initializing stealth browser...")

    driver = uc.Chrome(options=options, use_subprocess=True)

    # Set realistic viewport
    driver.set_window_size(1920, 1080)

    try:
        # Navigate to IndieGala homepage first (more natural)
        if debug:
            print("Navigating to IndieGala...")
        driver.get('https://www.indiegala.com/')
        random_delay(2, 4)  # Human-like delay

        # Check if we're already logged in
        try:
            driver.find_element(By.CSS_SELECTOR, 'a[href="/profile"]')
            logged_in = True
            if debug:
                print("Already logged in!")
        except NoSuchElementException:
            logged_in = False

        if not logged_in:
            if debug:
                print("Not logged in, attempting login...")

            try:
                # Navigate directly to login page
                if debug:
                    print("Navigating to login page...")
                driver.get('https://www.indiegala.com/login')
                random_delay(2, 3)

                # Dismiss popups that may appear
                wait = WebDriverWait(driver, 5)

                # Try to dismiss cookie policy popup first
                try:
                    cookie_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'I agree')]")))
                    random_delay(0.3, 0.7)  # Human delay before clicking
                    driver.execute_script("arguments[0].click();", cookie_btn)
                    if debug:
                        print("Dismissed cookie popup")
                    random_delay(0.5, 1)
                except TimeoutException:
                    if debug:
                        print("No cookie popup found")

                # Try to close notification popup by X button
                try:
                    close_selectors = [
                        (By.XPATH, "//button[contains(@class, 'close') or @aria-label='Close']"),
                        (By.CSS_SELECTOR, "button.close"),
                        (By.XPATH, "//button[text()='×']"),
                        (By.XPATH, "//*[contains(text(), 'Subscribe to IndieGala')]/ancestor::div[1]//button"),
                    ]

                    for selector_type, selector_value in close_selectors:
                        try:
                            close_btn = driver.find_element(selector_type, selector_value)
                            random_delay(0.3, 0.7)
                            driver.execute_script("arguments[0].click();", close_btn)
                            if debug:
                                print(f"Closed notification popup via: {selector_value}")
                            random_delay(0.5, 1)
                            break
                        except NoSuchElementException:
                            continue
                except Exception as e:
                    if debug:
                        print(f"Could not close notification popup: {e}")

                # Or try to dismiss with "Don't allow" button
                try:
                    notif_btn = driver.find_element(By.XPATH, "//button[contains(text(), \"Don't allow\")]")
                    random_delay(0.3, 0.7)
                    driver.execute_script("arguments[0].click();", notif_btn)
                    if debug:
                        print("Dismissed notification popup with Don't allow button")
                    random_delay(0.5, 1)
                except NoSuchElementException:
                    if debug:
                        print("Don't allow button not found")

                # Wait for login form to appear
                wait = WebDriverWait(driver, 10)
                if debug:
                    print("Waiting for login form...")

                # Make sure we're on the LOGIN tab, not REGISTER
                try:
                    login_tab = driver.find_element(By.XPATH, "//a[contains(text(), 'LOGIN') or @href='#login']")
                    if login_tab:
                        random_delay(0.5, 1)  # Human delay before clicking tab
                        driver.execute_script("arguments[0].click();", login_tab)
                        if debug:
                            print("Clicked LOGIN tab")
                        random_delay(0.5, 1)
                except NoSuchElementException:
                    if debug:
                        print("LOGIN tab not found or already selected")

                # Find all input fields to debug
                if debug:
                    all_inputs = driver.find_elements(By.TAG_NAME, 'input')
                    print(f"Found {len(all_inputs)} input fields")
                    for idx, inp in enumerate(all_inputs[:10]):  # Show first 10
                        visible = inp.is_displayed()
                        print(f"  Input {idx}: type={inp.get_attribute('type')}, name={inp.get_attribute('name')}, id={inp.get_attribute('id')}, class={inp.get_attribute('class')}, visible={visible}")

                # Try multiple selectors for the email field - specifically for login form
                email_selectors = [
                    (By.CSS_SELECTOR, '.login-form-login-email'),
                    (By.CSS_SELECTOR, 'input.login-form-login-email'),
                    (By.CSS_SELECTOR, '#login input[type="text"]'),
                    (By.CSS_SELECTOR, '.tab-pane.active input[type="text"]'),
                    (By.CSS_SELECTOR, 'input[type="text"]'),
                    (By.CSS_SELECTOR, 'input[placeholder*="mail" i]'),
                    (By.CSS_SELECTOR, 'input[placeholder*="username" i]'),
                    (By.NAME, 'login_email'),
                    (By.NAME, 'email'),
                    (By.NAME, 'username'),
                    (By.ID, 'login_email'),
                    (By.ID, 'email'),
                    (By.CSS_SELECTOR, 'input[type="email"]'),
                ]

                email_input = None
                for selector_type, selector_value in email_selectors:
                    try:
                        element = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                        # Make sure the element is visible/interactable
                        if element.is_displayed():
                            email_input = element
                            if debug:
                                print(f"Found visible email field with selector: {selector_value}")
                            break
                        elif debug:
                            print(f"Found but not visible: {selector_value}")
                    except TimeoutException:
                        continue

                if not email_input:
                    driver.save_screenshot('debug_no_email_field.png')
                    print("ERROR: Could not find email field. Screenshot saved to debug_no_email_field.png")
                    sys.exit(1)

                # Find password field - specifically for login form
                password_selectors = [
                    (By.CSS_SELECTOR, '.login-form-login-password'),
                    (By.CSS_SELECTOR, 'input.login-form-login-password'),
                    (By.CSS_SELECTOR, '#login input[type="password"]'),
                    (By.CSS_SELECTOR, '.tab-pane.active input[type="password"]'),
                    (By.CSS_SELECTOR, 'input[type="password"]'),
                    (By.NAME, 'login_password'),
                    (By.NAME, 'password'),
                    (By.ID, 'login_password'),
                    (By.ID, 'password'),
                ]

                password_input = None
                for selector_type, selector_value in password_selectors:
                    try:
                        element = driver.find_element(selector_type, selector_value)
                        if element.is_displayed():
                            password_input = element
                            if debug:
                                print(f"Found visible password field with selector: {selector_value}")
                            break
                        elif debug:
                            print(f"Found but not visible: {selector_value}")
                    except NoSuchElementException:
                        continue

                if not password_input:
                    driver.save_screenshot('debug_no_password_field.png')
                    print("ERROR: Could not find password field. Screenshot saved to debug_no_password_field.png")
                    sys.exit(1)

                # Fill in credentials with human-like typing
                if debug:
                    print("Filling in credentials...")

                # Click on email field first (more human-like)
                random_delay(0.3, 0.7)
                email_input.click()
                random_delay(0.2, 0.5)

                # Type email with human-like delays
                human_type(email_input, email, debug)
                random_delay(0.3, 0.7)

                # Click on password field
                password_input.click()
                random_delay(0.2, 0.5)

                # Type password with human-like delays
                human_type(password_input, password, debug)
                random_delay(0.5, 1.5)

                # Check for CAPTCHA and wait for user to solve it
                if debug:
                    print("Checking for CAPTCHA...")

                try:
                    recaptcha = driver.find_element(By.CSS_SELECTOR, '.g-recaptcha, iframe[src*="recaptcha"]')
                    if recaptcha.is_displayed():
                        print("\n" + "="*70)
                        print("⚠  CAPTCHA DETECTED - Please solve it manually!")
                        print("="*70)
                        print("1. Look at the browser window")
                        print("2. Click the 'I'm not a robot' checkbox")
                        print("3. Solve any image challenges if they appear")
                        print("4. Come back here and press ENTER to continue")
                        print("="*70 + "\n")

                        input("Press ENTER after you've solved the CAPTCHA...")
                        random_delay(0.5, 1)
                        if debug:
                            print("Continuing after CAPTCHA solve...")
                except NoSuchElementException:
                    if debug:
                        print("No CAPTCHA detected - lucky!")

                # Find and click submit button
                submit_selectors = [
                    (By.CSS_SELECTOR, '.login-form-submit-btn'),
                    (By.CSS_SELECTOR, 'button.login-form-submit-btn'),
                    (By.CSS_SELECTOR, '.login-btn'),
                    (By.XPATH, "//button[contains(@class, 'login-form-submit-btn')]"),
                    (By.XPATH, "//button[contains(text(), 'LOGIN')]"),
                    (By.CSS_SELECTOR, 'button[type="submit"]'),
                    (By.XPATH, "//button[@type='submit']"),
                    (By.XPATH, "//input[@type='submit']"),
                ]

                submit_btn = None
                for selector_type, selector_value in submit_selectors:
                    try:
                        element = driver.find_element(selector_type, selector_value)
                        if element.is_displayed():
                            submit_btn = element
                            if debug:
                                print(f"Found visible submit button with selector: {selector_value}")
                            break
                        elif debug:
                            print(f"Found but not visible: {selector_value}")
                    except NoSuchElementException:
                        continue

                if not submit_btn:
                    driver.save_screenshot('debug_no_submit_button.png')
                    print("ERROR: Could not find submit button. Screenshot saved to debug_no_submit_button.png")
                    sys.exit(1)

                if debug:
                    print("Submitting login form...")

                # Human delay before clicking submit
                random_delay(0.5, 1.0)
                submit_btn.click()

                # Wait for login to process
                if debug:
                    print("Waiting for login to complete...")
                random_delay(3, 5)

                # Check if there's an error message
                try:
                    error_msg = driver.find_element(By.CSS_SELECTOR, '.alert-danger, .error-message, [class*="error"]')
                    if error_msg.is_displayed():
                        print(f"Login error: {error_msg.text}")
                except NoSuchElementException:
                    pass

                # Verify login succeeded - wait up to 10 seconds
                login_wait = WebDriverWait(driver, 10)
                try:
                    # Try multiple ways to verify login
                    login_success = False

                    # Check if we're redirected away from login page
                    if '/login' not in driver.current_url:
                        login_success = True
                        if debug:
                            print(f"Redirected to: {driver.current_url}")

                    # Check for profile link
                    try:
                        login_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href="/profile"]')))
                        login_success = True
                    except TimeoutException:
                        pass

                    # Check if login form disappeared
                    try:
                        driver.find_element(By.CSS_SELECTOR, '.login-form-submit-btn')
                        # Still on login page
                        if '/login' in driver.current_url:
                            login_success = False
                    except NoSuchElementException:
                        # Login form gone, probably logged in
                        login_success = True

                    if login_success:
                        if debug:
                            print("Login successful!")
                    else:
                        driver.save_screenshot('debug_login_failed.png')
                        print("ERROR: Login failed. Check your credentials or solve CAPTCHA. Screenshot saved to debug_login_failed.png")
                        sys.exit(1)

                except Exception as e:
                    driver.save_screenshot('debug_login_exception.png')
                    print(f"ERROR during login verification: {e}")
                    print("Screenshot saved to debug_login_exception.png")
                    sys.exit(1)

            except Exception as e:
                driver.save_screenshot('debug_exception.png')
                print(f"ERROR during login: {e}")
                print("Screenshot saved to debug_exception.png")
                raise

        # Wait for and handle the Wheel of Fortune popup
        if debug:
            print("Waiting for Wheel of Fortune popup...")

        # Add human delay before looking for wheel
        random_delay(2, 3)

        try:
            # Wait for the spin button to appear (try multiple selectors)
            wait = WebDriverWait(driver, 15)

            # Try to find the spin button - adjust selector as needed
            spin_button = None
            selectors_to_try = [
                (By.XPATH, "//button[contains(text(), 'Spin')]"),
                (By.XPATH, "//*[contains(text(), 'Spin')]"),
                (By.CLASS_NAME, "spin-button"),
                (By.CSS_SELECTOR, ".wheel-spin-btn"),
                (By.CSS_SELECTOR, "button.spin"),
                (By.XPATH, "//div[contains(@class, 'wheel')]//button"),
            ]

            for selector_type, selector_value in selectors_to_try:
                try:
                    spin_button = wait.until(EC.element_to_be_clickable((selector_type, selector_value)))
                    if debug:
                        print(f"Found spin button using selector: {selector_value}")
                    break
                except TimeoutException:
                    continue

            if spin_button:
                # Human delay before clicking spin button
                random_delay(0.5, 1.5)

                if debug:
                    print("Clicking spin button...")
                spin_button.click()

                # Wait for spin animation
                random_delay(5, 7)

                # Try to capture the result
                try:
                    result_element = driver.find_element(By.CSS_SELECTOR, '.wheel-result, .prize-text, .win-text')
                    result = result_element.text
                    print(f"✓ Wheel spun successfully! Prize: {result}")
                except NoSuchElementException:
                    print("✓ Wheel spun successfully!")
            else:
                print("⚠ Could not find spin button. You may have already spun today.")

        except TimeoutException:
            print("⚠ Wheel popup did not appear. You may have already spun today.")

    except Exception as e:
        print(f"ERROR: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        driver.quit()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='IndieGala Auto-Spin Bot')
    parser.add_argument('--visible', action='store_true', help='Run browser in visible mode')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')

    args = parser.parse_args()

    spin_wheel(headless=not args.visible, debug=args.debug)
