"""Sign out specific account from browser."""

import logging

logger = logging.getLogger(__name__)

MYACCOUNT_URL = "https://myaccount.google.com"
SIGNOUT_URL = "https://accounts.google.com/SignOutOptions"
STEP_TIMEOUT = 15000  # 15 seconds


def signout(page, target_email: str) -> bool:
    """
    Sign out a specific account from the browser profile.
    
    Navigates to Google account management and signs out the target email.
    
    Args:
        page: Playwright page object
        target_email: Email address to sign out
        
    Returns:
        True if sign-out was successful, False otherwise
    """
    try:
        logger.info(f"Attempting to sign out: {target_email}")
        
        # Navigate to sign-out options page
        page.goto(SIGNOUT_URL, timeout=STEP_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)
        page.wait_for_timeout(2000)
        
        # Look for the target email in the accounts list
        # Google shows accounts with their email addresses
        email_elements = page.query_selector_all(f'[data-email="{target_email}"]')
        
        if not email_elements:
            # Try finding by text content
            all_text = page.content()
            if target_email.lower() not in all_text.lower():
                logger.warning(f"Email {target_email} not found on sign-out page")
                return False
        
        # Try to find and click "Sign out" or "Remove" for this account
        # Google's sign-out page varies, try multiple approaches
        
        # Approach 1: Click "Sign out of all accounts" if single account
        signout_all = page.query_selector('button:has-text("Sign out"), a:has-text("Sign out")')
        if signout_all:
            signout_all.click()
            page.wait_for_timeout(3000)
            logger.info(f"Signed out from account(s)")
            return True
        
        # Approach 2: Find specific account removal
        # Look for remove/signout button near the target email
        account_rows = page.query_selector_all('[data-email], .account-row, li[data-identifier]')
        for row in account_rows:
            row_text = row.inner_text().lower()
            if target_email.lower() in row_text:
                # Found the row, look for remove/signout action
                remove_btn = row.query_selector('button, [role="button"]')
                if remove_btn:
                    remove_btn.click()
                    page.wait_for_timeout(2000)
                    logger.info(f"Removed account: {target_email}")
                    return True
        
        # Approach 3: Navigate to myaccount and use account switcher
        page.goto(MYACCOUNT_URL, timeout=STEP_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)
        
        # Click profile picture/avatar to open account menu
        avatar = page.query_selector('img[class*="avatar"], a[aria-label*="Account"], button[aria-label*="Account"]')
        if avatar:
            avatar.click()
            page.wait_for_timeout(2000)
            
            # Look for sign out option
            signout_link = page.query_selector('a:has-text("Sign out"), button:has-text("Sign out")')
            if signout_link:
                signout_link.click()
                page.wait_for_timeout(3000)
                return True
        
        logger.warning("Could not find sign-out mechanism")
        return False
        
    except Exception as e:
        logger.error(f"Sign-out error: {e}")
        return False


def verify_signed_out(page, target_email: str) -> bool:
    """
    Verify that an account is no longer signed in.
    
    Args:
        page: Playwright page object
        target_email: Email to check
        
    Returns:
        True if account is NOT signed in (sign-out confirmed)
    """
    try:
        page.goto(SIGNOUT_URL, timeout=STEP_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=STEP_TIMEOUT)
        
        content = page.content().lower()
        return target_email.lower() not in content
    except Exception:
        return False
