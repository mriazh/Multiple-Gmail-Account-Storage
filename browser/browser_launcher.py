"""Camoufox browser launch and management."""

import logging
import signal

from camoufox import Camoufox

logger = logging.getLogger(__name__)

# Default window size
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 700

# Prevent lengthy Playwright tracebacks on Ctrl+C
signal.signal(signal.SIGINT, signal.SIG_DFL)


def open_browser(user_data_dir: str, headless: bool = False):
    """
    Launch Camoufox with persistent context.
    
    Args:
        user_data_dir: Path to the profile directory (decrypted temp dir)
        headless: Whether to run headless (default: False for user interaction)
        
    Returns:
        Camoufox browser context (persistent context manager)
    """
    logger.info(f"Opening browser with profile: {user_data_dir}")
    
    browser = Camoufox(
        user_data_dir=user_data_dir,
        persistent_context=True,
        headless=headless,
        window=(WINDOW_WIDTH, WINDOW_HEIGHT),
    )
    
    return browser


def get_page(browser):
    """Get the first page or create a new one."""
    if browser.pages:
        return browser.pages[0]
    return browser.new_page()


def wait_for_close(browser) -> None:
    """
    Block until the user closes the browser window.
    
    Uses event-based waiting to detect browser close.
    """
    logger.info("Waiting for user to close browser...")
    
    try:
        page = get_page(browser)
        # Wait for a very long time (effectively until browser closes)
        page.wait_for_timeout(999999999)
    except Exception as e:
        logger.debug(f"Browser closed. Detail: {e}")


def close_browser(browser) -> None:
    """Close browser gracefully."""
    try:
        if hasattr(browser, 'close'):
            browser.close()
        logger.info("Browser closed gracefully.")
    except Exception as e:
        logger.warning(f"Error closing browser: {e}")


def navigate_to(page, url: str, timeout: int = 30000) -> None:
    """
    Navigate to a URL with timeout.
    
    Args:
        page: Playwright page object
        url: Target URL
        timeout: Navigation timeout in milliseconds
    """
    logger.debug(f"Navigating to: {url}")
    page.goto(url, timeout=timeout)
