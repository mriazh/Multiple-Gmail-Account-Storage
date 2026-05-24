"""Gmail login automation flow."""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class LoginResult(Enum):
    """Possible outcomes of a login attempt."""
    SUCCESS = "success"
    WRONG_PASSWORD = "wrong_password"
    CAPTCHA_NEEDED = "captcha_needed"
    TWO_FA_NEEDED = "two_fa_needed"
    UNKNOWN_ERROR = "unknown_error"


# Gmail login selectors (may need updating if Google changes their UI)
SELECTORS = {
    "email_input": 'input[type="email"]',
    "email_next": '#identifierNext',
    "password_input": 'input[type="password"]',
    "password_next": '#passwordNext',
    "wrong_password": 'span[jsname="B34EJ"]',  # "Wrong password" error text
    "captcha_iframe": 'iframe[src*="recaptcha"]',
    "two_fa_challenge": '[data-challengetype]',
    "myaccount_indicator": 'a[href*="myaccount.google.com"]',
}

GMAIL_SIGNIN_URL = "https://accounts.google.com/signin/v2/identifier"
STEP_TIMEOUT = 30000  # 30 seconds per step


def login(page, email: str, password: str) -> LoginResult:
    """
    Automate Gmail login flow.
    
    Args:
        page: Playwright page object
        email: Gmail address
        password: Account password
        
    Returns:
        LoginResult enum indicating the outcome
    """
    try:
        # Navigate to Gmail sign-in
        logger.info(f"Navigating to Gmail sign-in for {email}")
        page.goto(GMAIL_SIGNIN_URL, timeout=STEP_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)
        
        # Enter email
        logger.info("Entering email address...")
        email_input = page.wait_for_selector(SELECTORS["email_input"], timeout=STEP_TIMEOUT)
        email_input.fill(email)
        page.click(SELECTORS["email_next"])
        
        # Wait for password page or error
        logger.info("Waiting for password field...")
        page.wait_for_timeout(2000)  # Brief wait for transition
        
        # Check for CAPTCHA before password
        if _detect_captcha(page):
            logger.warning("CAPTCHA detected before password entry")
            return LoginResult.CAPTCHA_NEEDED
        
        # Enter password
        try:
            password_input = page.wait_for_selector(
                SELECTORS["password_input"], 
                timeout=STEP_TIMEOUT,
                state="visible"
            )
        except Exception:
            # Password field not found — might be CAPTCHA or other challenge
            if _detect_captcha(page):
                return LoginResult.CAPTCHA_NEEDED
            return LoginResult.UNKNOWN_ERROR
        
        logger.info("Entering password...")
        password_input.fill(password)
        page.click(SELECTORS["password_next"])
        
        # Wait for result
        page.wait_for_timeout(3000)  # Wait for response
        
        # Check outcomes in priority order
        result = _detect_outcome(page)
        logger.info(f"Login result: {result.value}")
        return result
        
    except Exception as e:
        logger.error(f"Login automation error: {e}")
        return LoginResult.UNKNOWN_ERROR


def _detect_captcha(page) -> bool:
    """Check if CAPTCHA is present on page."""
    try:
        captcha = page.query_selector(SELECTORS["captcha_iframe"])
        return captcha is not None
    except Exception:
        return False


def _detect_outcome(page) -> LoginResult:
    """Detect the outcome after submitting password."""
    # Check for wrong password error
    try:
        wrong_pw = page.query_selector(SELECTORS["wrong_password"])
        if wrong_pw and wrong_pw.is_visible():
            return LoginResult.WRONG_PASSWORD
    except Exception:
        pass
    
    # Check for CAPTCHA
    if _detect_captcha(page):
        return LoginResult.CAPTCHA_NEEDED
    
    # Check for 2FA/verification challenge
    try:
        two_fa = page.query_selector(SELECTORS["two_fa_challenge"])
        if two_fa:
            return LoginResult.TWO_FA_NEEDED
    except Exception:
        pass
    
    # Check for successful login (redirected to myaccount or inbox)
    current_url = page.url.lower()
    success_indicators = [
        "myaccount.google.com",
        "mail.google.com",
        "accounts.google.com/signin/v2/challenge/selection",  # account chooser = logged in
    ]
    
    if any(indicator in current_url for indicator in success_indicators):
        return LoginResult.SUCCESS
    
    # Check page title for inbox
    title = page.title().lower()
    if "inbox" in title or "gmail" in title:
        return LoginResult.SUCCESS
    
    # If we got past password without error, likely success
    try:
        password_field = page.query_selector(SELECTORS["password_input"])
        if password_field is None or not password_field.is_visible():
            # Password field gone = we moved past it
            return LoginResult.SUCCESS
    except Exception:
        pass
    
    return LoginResult.UNKNOWN_ERROR


def verify_active_account(page, expected_email: str) -> bool:
    """
    Verify which account is currently active in the browser.
    
    Navigates to myaccount.google.com and checks the displayed email.
    
    Args:
        page: Playwright page object
        expected_email: Email we expect to be active
        
    Returns:
        True if active account matches expected, False otherwise
    """
    try:
        logger.info(f"Verifying active account matches: {expected_email}")
        page.goto("https://myaccount.google.com", timeout=STEP_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)
        page.wait_for_timeout(2000)
        
        # Try to find the active email on the page
        # Google shows the email in various places on myaccount
        
        # Method 1: Check page content for email
        content = page.content()
        if expected_email.lower() in content.lower():
            logger.info(f"Active account verified: {expected_email}")
            return True
        
        # Method 2: Check aria labels and data attributes
        email_elements = page.query_selector_all(
            f'[data-email], [aria-label*="@"], a[href*="mail"]'
        )
        for elem in email_elements:
            text = elem.inner_text().lower()
            if expected_email.lower() in text:
                return True
            # Check attributes
            for attr in ['data-email', 'aria-label', 'title']:
                val = elem.get_attribute(attr)
                if val and expected_email.lower() in val.lower():
                    return True
        
        logger.warning(f"Active account does NOT match {expected_email}")
        return False
        
    except Exception as e:
        logger.error(f"Account verification error: {e}")
        return False
