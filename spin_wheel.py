#!/usr/bin/env python3
"""
IndieGala Auto-Spin Bot
Automatically logs in and spins the daily Wheel of Fortune
Uses stealth techniques to avoid CAPTCHA detection
"""

import os
import random
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows terminals (handles emoji in print statements)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import undetected_chromedriver as uc
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, will use environment variables


def random_delay(min_sec=0.5, max_sec=2.0):
    time.sleep(random.uniform(min_sec, max_sec))


def human_type(element, text, debug=False):
    """Type text with short per-keystroke delays to appear human without wasting time."""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.02, 0.06))
    if debug:
        print("Filled field")


def is_first_run(user_data_dir):
    """Return True if no Chrome session cookies exist yet (never logged in).
    Chrome 96+ stores cookies in Default/Network/Cookies, not Default/Cookies."""
    network_cookies = user_data_dir / "Default" / "Network" / "Cookies"
    legacy_cookies = user_data_dir / "Default" / "Cookies"
    return not network_cookies.exists() and not legacy_cookies.exists()


def try_dismiss(driver, selectors, timeout=1.5, debug=False, label="popup"):
    """
    Try each selector in order; click the first visible match within timeout.
    Returns True if dismissed, False if nothing found.
    Short timeout means we don't stall when the popup simply isn't there.
    """
    for selector_type, selector_value in selectors:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((selector_type, selector_value))
            )
            driver.execute_script("arguments[0].click();", el)
            if debug:
                print(f"Dismissed {label} via: {selector_value}")
            return True
        except TimeoutException:
            continue
    if debug:
        print(f"No {label} found")
    return False


def _wait_for_result(driver, timeout=15, debug=False):
    """
    Poll until a prize/result element appears after the wheel spin.
    Returns the prize text, or None if nothing readable was found within timeout.

    Strategy:
    1. Poll specific CSS selectors for common prize-display patterns.
    2. When the spin button disappears (spin started), watch for any new modal/dialog.
    3. Fall back to reading visible text from any overlay that appeared.
    4. Final fallback: JS to find the deepest non-empty text node inside wheel area.
    """
    # Selectors tried in order — prefer specific classes over generic ones
    result_selectors = [
        # IndieGala-specific guesses based on their naming patterns
        ".wheel-result",
        ".wheel-prize",
        ".spin-result",
        ".spin-prize",
        ".fortune-result",
        ".fortune-prize",
        ".daily-prize",
        # Common prize/reward class fragments (partial match via attribute contains)
        '[class*="prize"]',
        '[class*="reward"]',
        '[class*="result"]',
        # SweetAlert2 — very common for prize popups
        ".swal2-title",
        ".swal2-html-container",
        ".swal2-content",
        # Bootstrap modal that becomes visible
        ".modal.show .modal-title",
        ".modal.show .modal-body",
        ".modal.fade.show h2",
        ".modal.fade.show h3",
        ".modal.fade.show p",
        # Generic dialog/overlay
        '[role="dialog"] h2',
        '[role="dialog"] h3',
        '[role="dialog"] p',
        '[role="alertdialog"]',
        ".popup-content h2",
        ".popup-content h3",
        ".overlay-content h2",
        ".overlay-content",
        ".alert-success",
        ".toast-success",
    ]

    deadline = time.time() + timeout
    while time.time() < deadline:
        for sel in result_selectors:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if not el.is_displayed():
                    continue
                text = el.text.strip()
                if text and len(text) > 1:
                    if debug:
                        print(f"Result found via selector '{sel}': {text}")
                    return text
            except NoSuchElementException:
                continue
        time.sleep(0.5)

    # Fallback: scrape text from any visible modal/dialog that appeared
    for container_sel in [
        ".modal.show",
        '[role="dialog"]',
        ".swal2-popup",
        ".popup",
        ".overlay",
    ]:
        try:
            container = driver.find_element(By.CSS_SELECTOR, container_sel)
            if container.is_displayed():
                text = container.text.strip()
                if text:
                    if debug:
                        print(f"Result scraped from container '{container_sel}'")
                    return text
        except NoSuchElementException:
            continue

    # Last resort: JS — find all visible leaf text nodes in the document body
    try:
        result = driver.execute_script("""
            var walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT, null, false
            );
            var texts = [];
            var node;
            while (node = walker.nextNode()) {
                var text = node.textContent.trim();
                var parent = node.parentElement;
                if (text.length > 2 && parent && parent.offsetParent !== null) {
                    var cls = (parent.className || '') + ' ' + (parent.id || '');
                    if (/prize|reward|result|win|spin|wheel|fortune/i.test(cls)) {
                        texts.push(text);
                    }
                }
            }
            return texts.join(' | ');
        """)
        if result and result.strip():
            if debug:
                print(f"Result via JS text walker: {result.strip()}")
            return result.strip()
    except Exception:
        pass

    return None


def spin_wheel(headless=True, debug=False):
    """
    Login to IndieGala and spin the daily wheel

    Args:
        headless: Run browser in headless mode (no visible window)
        debug: Enable debug output
    """
    # Get credentials from environment variables
    email = os.getenv("INDIEGALA_EMAIL")
    password = os.getenv("INDIEGALA_PASSWORD")

    if not email or not password:
        print(
            "ERROR: Please set INDIEGALA_EMAIL and INDIEGALA_PASSWORD environment variables"
        )
        sys.exit(1)

    # Path to store persistent browser session
    user_data_dir = Path.home() / ".indiegala-session"
    user_data_dir.mkdir(exist_ok=True)

    # Configure undetected Chrome options
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={user_data_dir}")

    # Additional stealth arguments
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")

    if headless:
        options.add_argument("--headless=new")

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
        driver.get("https://www.indiegala.com/")
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
                driver.get("https://www.indiegala.com/login")
                random_delay(2, 3)

                # Dismiss any popups quickly; only sleep if something was actually dismissed
                cookie_dismissed = try_dismiss(
                    driver,
                    [
                        (By.XPATH, "//button[contains(text(), 'I agree')]"),
                        (By.XPATH, "//button[contains(text(), 'Accept')]"),
                    ],
                    timeout=2,
                    debug=debug,
                    label="cookie popup",
                )
                if cookie_dismissed:
                    random_delay(0.3, 0.6)

                notif_dismissed = try_dismiss(
                    driver,
                    [
                        (
                            By.XPATH,
                            "//button[contains(@class, 'close') or @aria-label='Close']",
                        ),
                        (By.CSS_SELECTOR, "button.close"),
                        (By.XPATH, "//button[text()='×']"),
                        (By.XPATH, '//button[contains(text(), "Don\'t allow")]'),
                        (
                            By.XPATH,
                            "//*[contains(text(), 'Subscribe to IndieGala')]/ancestor::div[1]//button",
                        ),
                    ],
                    timeout=1,
                    debug=debug,
                    label="notification popup",
                )
                if notif_dismissed:
                    random_delay(0.3, 0.6)

                # Wait for login form to appear
                wait = WebDriverWait(driver, 10)
                if debug:
                    print("Waiting for login form...")

                # Make sure we're on the LOGIN tab, not REGISTER
                try:
                    login_tab = driver.find_element(
                        By.XPATH, "//a[contains(text(), 'LOGIN') or @href='#login']"
                    )
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
                    all_inputs = driver.find_elements(By.TAG_NAME, "input")
                    print(f"Found {len(all_inputs)} input fields")
                    for idx, inp in enumerate(all_inputs[:10]):  # Show first 10
                        visible = inp.is_displayed()
                        print(
                            f"  Input {idx}: type={inp.get_attribute('type')}, name={inp.get_attribute('name')}, id={inp.get_attribute('id')}, class={inp.get_attribute('class')}, visible={visible}"
                        )

                # Try multiple selectors for the email field - specifically for login form
                email_selectors = [
                    (By.CSS_SELECTOR, ".login-form-login-email"),
                    (By.CSS_SELECTOR, "input.login-form-login-email"),
                    (By.CSS_SELECTOR, '#login input[type="text"]'),
                    (By.CSS_SELECTOR, '.tab-pane.active input[type="text"]'),
                    (By.CSS_SELECTOR, 'input[type="text"]'),
                    (By.CSS_SELECTOR, 'input[placeholder*="mail" i]'),
                    (By.CSS_SELECTOR, 'input[placeholder*="username" i]'),
                    (By.NAME, "login_email"),
                    (By.NAME, "email"),
                    (By.NAME, "username"),
                    (By.ID, "login_email"),
                    (By.ID, "email"),
                    (By.CSS_SELECTOR, 'input[type="email"]'),
                ]

                email_input = None
                for selector_type, selector_value in email_selectors:
                    try:
                        element = wait.until(
                            EC.presence_of_element_located(
                                (selector_type, selector_value)
                            )
                        )
                        # Make sure the element is visible/interactable
                        if element.is_displayed():
                            email_input = element
                            if debug:
                                print(
                                    f"Found visible email field with selector: {selector_value}"
                                )
                            break
                        elif debug:
                            print(f"Found but not visible: {selector_value}")
                    except TimeoutException:
                        continue

                if not email_input:
                    driver.save_screenshot("debug_no_email_field.png")
                    print(
                        "ERROR: Could not find email field. Screenshot saved to debug_no_email_field.png"
                    )
                    sys.exit(1)

                # Find password field - specifically for login form
                password_selectors = [
                    (By.CSS_SELECTOR, ".login-form-login-password"),
                    (By.CSS_SELECTOR, "input.login-form-login-password"),
                    (By.CSS_SELECTOR, '#login input[type="password"]'),
                    (By.CSS_SELECTOR, '.tab-pane.active input[type="password"]'),
                    (By.CSS_SELECTOR, 'input[type="password"]'),
                    (By.NAME, "login_password"),
                    (By.NAME, "password"),
                    (By.ID, "login_password"),
                    (By.ID, "password"),
                ]

                password_input = None
                for selector_type, selector_value in password_selectors:
                    try:
                        element = driver.find_element(selector_type, selector_value)
                        if element.is_displayed():
                            password_input = element
                            if debug:
                                print(
                                    f"Found visible password field with selector: {selector_value}"
                                )
                            break
                        elif debug:
                            print(f"Found but not visible: {selector_value}")
                    except NoSuchElementException:
                        continue

                if not password_input:
                    driver.save_screenshot("debug_no_password_field.png")
                    print(
                        "ERROR: Could not find password field. Screenshot saved to debug_no_password_field.png"
                    )
                    sys.exit(1)

                if debug:
                    print("Filling in credentials...")

                email_input.click()
                random_delay(0.1, 0.3)
                human_type(email_input, email, debug)
                random_delay(0.2, 0.4)

                password_input.click()
                random_delay(0.1, 0.2)
                human_type(password_input, password, debug)
                random_delay(0.3, 0.6)

                if debug:
                    print("Checking for CAPTCHA...")

                try:
                    recaptcha = driver.find_element(
                        By.CSS_SELECTOR, '.g-recaptcha, iframe[src*="recaptcha"]'
                    )
                    if recaptcha.is_displayed():
                        if headless:
                            driver.save_screenshot("debug_captcha_headless.png")
                            print("ERROR: CAPTCHA required but running headless.")
                            print(
                                "Delete ~/.indiegala-session and run again — it will open visibly for first-time setup."
                            )
                            sys.exit(1)
                        print("\n" + "=" * 70)
                        print(
                            "CAPTCHA DETECTED - Please solve it in the browser window!"
                        )
                        print("=" * 70)
                        if sys.stdin.isatty():
                            input("Press ENTER after you've solved the CAPTCHA...")
                        else:
                            print("Non-interactive: waiting 90 seconds...")
                            time.sleep(90)
                        random_delay(0.3, 0.6)
                        if debug:
                            print("Continuing after CAPTCHA...")
                except NoSuchElementException:
                    if debug:
                        print("No CAPTCHA detected")

                # Find and click submit button
                submit_selectors = [
                    (By.CSS_SELECTOR, ".login-form-submit-btn"),
                    (By.CSS_SELECTOR, "button.login-form-submit-btn"),
                    (By.CSS_SELECTOR, ".login-btn"),
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
                                print(
                                    f"Found visible submit button with selector: {selector_value}"
                                )
                            break
                        elif debug:
                            print(f"Found but not visible: {selector_value}")
                    except NoSuchElementException:
                        continue

                if not submit_btn:
                    driver.save_screenshot("debug_no_submit_button.png")
                    print(
                        "ERROR: Could not find submit button. Screenshot saved to debug_no_submit_button.png"
                    )
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
                    error_msg = driver.find_element(
                        By.CSS_SELECTOR,
                        '.alert-danger, .error-message, [class*="error"]',
                    )
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
                    if "/login" not in driver.current_url:
                        login_success = True
                        if debug:
                            print(f"Redirected to: {driver.current_url}")

                    # Check for profile link
                    try:
                        login_wait.until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, 'a[href="/profile"]')
                            )
                        )
                        login_success = True
                    except TimeoutException:
                        pass

                    # Check if login form disappeared
                    try:
                        driver.find_element(By.CSS_SELECTOR, ".login-form-submit-btn")
                        # Still on login page
                        if "/login" in driver.current_url:
                            login_success = False
                    except NoSuchElementException:
                        # Login form gone, probably logged in
                        login_success = True

                    if login_success:
                        if debug:
                            print("Login successful!")
                    else:
                        driver.save_screenshot("debug_login_failed.png")
                        print(
                            "ERROR: Login failed. Check your credentials or solve CAPTCHA. Screenshot saved to debug_login_failed.png"
                        )
                        sys.exit(1)

                except Exception as e:
                    driver.save_screenshot("debug_login_exception.png")
                    print(f"ERROR during login verification: {e}")
                    print("Screenshot saved to debug_login_exception.png")
                    sys.exit(1)

            except Exception as e:
                driver.save_screenshot("debug_exception.png")
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
                    spin_button = wait.until(
                        EC.element_to_be_clickable((selector_type, selector_value))
                    )
                    if debug:
                        print(f"Found spin button using selector: {selector_value}")
                    break
                except TimeoutException:
                    continue

            if spin_button:
                # Dismiss any popups that might be blocking the spin button
                # Scope selectors to notification popup container to avoid closing the wheel modal
                notification_selectors = [
                    (
                        By.XPATH,
                        "//div[contains(@class, 'sp-prompt-message')]//button[contains(@class, 'close') or @aria-label='Close']",
                    ),
                    (By.CSS_SELECTOR, ".sp-prompt-message button.close"),
                    (
                        By.XPATH,
                        "//div[contains(@class, 'sp-prompt-message')]//button[text()='×']",
                    ),
                ]
                try_dismiss(
                    driver,
                    notification_selectors,
                    timeout=1,
                    debug=debug,
                    label="blocking popup",
                )

                # Re-locate spin button after dismissing popups to avoid stale element reference
                spin_button = None
                for selector_type, selector_value in selectors_to_try:
                    try:
                        spin_button = wait.until(
                            EC.element_to_be_clickable((selector_type, selector_value))
                        )
                        if debug:
                            print(
                                f"Re-located spin button using selector: {selector_value}"
                            )
                        break
                    except TimeoutException:
                        continue

                if not spin_button:
                    print("Could not re-locate spin button after dismissing popups.")
                    return

                random_delay(0.5, 1.5)
                if debug:
                    print("Clicking spin button...")

                # Use JavaScript click to bypass any overlay issues
                try:
                    driver.execute_script("arguments[0].click();", spin_button)
                except Exception:
                    # Fallback to regular click
                    spin_button.click()

                result = _wait_for_result(driver, debug=debug)
                if result:
                    print(f"Wheel result: {result}")
                else:
                    print("Wheel spun — could not read result (check debug_result.png)")
                    driver.save_screenshot("debug_result.png")
            else:
                print("Could not find spin button. You may have already spun today.")

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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IndieGala Auto-Spin Bot")
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Force visible browser (overrides auto-detect)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Force headless browser (overrides auto-detect)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable verbose debug output"
    )

    args = parser.parse_args()

    # Auto-detect: first run (no saved session) → visible so user can solve CAPTCHA.
    # Explicit --visible / --headless always wins.
    session_dir = Path.home() / ".indiegala-session"
    first = is_first_run(session_dir)
    if args.visible:
        headless = False
    elif args.headless:
        headless = True
    else:
        headless = not first
        if first:
            print(
                "First run detected — opening browser visibly for login/CAPTCHA setup."
            )
            print("Future runs will be fully headless and automated.")

    spin_wheel(headless=headless, debug=args.debug)
