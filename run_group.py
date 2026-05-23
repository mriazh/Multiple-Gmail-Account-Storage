from camoufox import Camoufox
import sys
import os
import re
import time
import logging
from datetime import datetime
import signal

# ============================================================
# CONFIGURATION
# ============================================================
WINDOW_WIDTH = int(os.environ.get('BROWSER_WIDTH', 1200))
WINDOW_HEIGHT = int(os.environ.get('BROWSER_HEIGHT', 700))
LOG_DIR = "logs"
SENSITIVE_DOMAINS = ['accounts.google.com', 'mail.google.com', 'myaccount.google.com']

# Prevent lengthy Playwright tracebacks on Ctrl+C
signal.signal(signal.SIGINT, signal.SIG_DFL)

IGNORED_DIRS = {'.git', 'logs', '__pycache__', '.venv', 'node_modules'}

def get_available_groups():
    """Scan current directory for group folders."""
    groups = []
    for entry in sorted(os.listdir('.')):
        if os.path.isdir(entry) and entry.lower() not in IGNORED_DIRS and not entry.startswith('.'):
            groups.append(entry)
    return groups

def resolve_group_input(user_input):
    """
    Resolve flexible user input to an actual group folder name.
    Accepts:
      - A number (e.g. "1") matching the listed order
      - A group name, case-insensitive (e.g. "Group_1", "group_1", "GROUP_1")
    """
    groups = get_available_groups()

    # Try as a number first
    if user_input.isdigit():
        idx = int(user_input) - 1
        if 0 <= idx < len(groups):
            return groups[idx]
        raise ValueError(
            f"Invalid number '{user_input}'. Available: 1-{len(groups)}"
        )

    # Try case-insensitive match against existing folders
    for group in groups:
        if group.lower() == user_input.lower():
            return group

    # If no match found, validate as a new group name
    if not re.match(r'^[a-zA-Z0-9_-]+$', user_input):
        raise ValueError(f"Invalid group name: {user_input}")
    if user_input.startswith(('.', '-')):
        raise ValueError("Group name cannot start with '.' or '-'")

    return user_input

def validate_group_name(group_name):
    """Validate group name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', group_name):
        raise ValueError(f"Invalid group name: {group_name}")
    if group_name.startswith(('.', '-')):
        raise ValueError("Group name cannot start with '.' or '-'")
    return group_name

def setup_logger(group_name):
    """Setup logger: file (comprehensive, append per day) + console (minimal)."""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOG_DIR, f"{date_str}_{group_name}.log")
    
    # Unique logger name per invocation
    logger = logging.getLogger(f"camoufox_{group_name}_{os.getpid()}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_fmt)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter(fmt="%(message)s")
    console_handler.setFormatter(console_fmt)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger, log_file

def is_sensitive_url(url):
    """Check if URL contains sensitive domains."""
    return any(domain in url for domain in SENSITIVE_DOMAINS)

def write_log_header(logger, group_name, log_file):
    """Write START session header to log file."""
    divider = "=" * 60
    logger.debug("")
    logger.debug(divider)
    logger.debug(f"  SESSION STARTED — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.debug(divider)
    logger.debug(f"Profile      : {group_name}")
    logger.debug(f"Log file     : {log_file}")
    logger.debug(f"Window size  : {WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    logger.debug(f"Platform     : {sys.platform}")
    logger.debug(f"Python       : {sys.version}")
    logger.debug(divider)

def write_log_footer(logger, start_time):
    """Write END session footer to log file."""
    duration = time.time() - start_time
    minutes, seconds = divmod(int(duration), 60)
    divider = "=" * 60
    logger.debug(divider)
    logger.debug(f"  SESSION ENDED — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Duration: {minutes}m {seconds}s")
    logger.debug(divider)
    logger.debug("")

def attach_navigation_monitor(browser, logger):
    """Attach event listeners on all tabs to log browsing activities."""
    def monitor_page(page):
        def on_navigation(frame):
            if frame == page.main_frame:
                url = frame.url
                if url and url != "about:blank":
                    if is_sensitive_url(url):
                        logger.debug("[NAVIGATION] [REDACTED - Sensitive URL]")
                    else:
                        logger.debug(f"[NAVIGATION] {url}")
        
        def on_load():
            title = ""
            try:
                title = page.title()
            except Exception:
                pass
            logger.debug(f"[LOADED]     Title: \"{title}\"")
        
        def on_download(download):
            logger.debug(f"[DOWNLOAD]   {download.suggested_filename} from {download.url}")
        
        def on_popup(popup):
            logger.debug(f"[NEW TAB]    Popup opened: {popup.url}")
            monitor_page(popup)
        
        def on_page_error(error):
            logger.debug(f"[WEB ERR]    {error}")
        
        page.on("framenavigated", on_navigation)
        page.on("load", on_load)
        page.on("download", on_download)
        page.on("popup", on_popup)
        page.on("pageerror", on_page_error)
    
    for page in browser.pages:
        monitor_page(page)
        logger.debug(f"Monitor attached to tab: {page.url or 'about:blank'}")
    
    def on_new_page(page):
        logger.debug(f"[NEW TAB]    New tab opened.")
        monitor_page(page)
    
    def on_close_page(page):
        logger.debug(f"[CLOSE TAB]  Tab closed: {page.url}")
    
    browser.on("page", on_new_page)
    browser.on("close", lambda: logger.debug("[BROWSER]    Browser closed by user."))

def main():
    if len(sys.argv) < 2:
        groups = get_available_groups()
        print("Usage: python run_group.py <group_name_or_number>")
        print()
        if groups:
            print("Available groups:")
            for i, g in enumerate(groups, 1):
                print(f"  {i}. {g}")
            print()
            print("Examples:")
            print(f"  python run_group.py 1")
            print(f"  python run_group.py {groups[0]}")
        else:
            print("Example: python run_group.py Group_1")
        sys.exit(1)

    try:
        group_name = resolve_group_input(sys.argv[1])
        validate_group_name(group_name)
    except ValueError as e:
        print(f"[!] ERROR: {e}")
        sys.exit(1)

    start_time = time.time()
    logger, log_file = setup_logger(group_name)
    write_log_header(logger, group_name, log_file)
    
    print(f"[*] Opening profile '{group_name}'...")
    print(f"[i] Detailed log: {log_file}")
    print()
    
    logger.debug("Starting Camoufox browser initialization...")

    try:
        with Camoufox(
            user_data_dir=group_name,
            persistent_context=True,
            headless=False,
            window=(WINDOW_WIDTH, WINDOW_HEIGHT)
        ) as browser:
            logger.debug("Camoufox browser opened successfully.")
            logger.debug(f"Active tabs: {len(browser.pages)} tabs open.")
            
            attach_navigation_monitor(browser, logger)
            logger.debug("Navigation & web activity monitor is active.")
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            logger.debug("Initial navigation to whatismyipaddress.com...")
            page.goto('https://whatismyipaddress.com/')
            
            try:
                info = page.evaluate("""() => ({
                    innerW: window.innerWidth,
                    innerH: window.innerHeight,
                    outerW: window.outerWidth,
                    outerH: window.outerHeight,
                    screenW: screen.width,
                    screenH: screen.height,
                    dpr: window.devicePixelRatio,
                    ua: navigator.userAgent
                })""")
                
                logger.debug("-" * 60)
                logger.debug("BROWSER INFO (as seen by websites):")
                logger.debug(f"  window.inner : {info['innerW']}x{info['innerH']}")
                logger.debug(f"  window.outer : {info['outerW']}x{info['outerH']}")
                logger.debug(f"  screen       : {info['screenW']}x{info['screenH']}")
                logger.debug(f"  devicePixelRatio: {info['dpr']}")
                logger.debug(f"  userAgent    : {info['ua']}")
                logger.debug("-" * 60)
            except Exception as e:
                logger.warning(f"Failed to retrieve browser info: {e}")
            
            print("[+] Browser opened! Feel free to use the browser.")
            print("[!] Close the browser window when finished.")
            print()
            
            logger.debug("Waiting for user to close the browser...")
            
            try:
                # Event-based wait
                if hasattr(browser, 'contexts') and len(browser.contexts) > 0:
                    browser.contexts[0].wait_for_event('close')
                else:
                    page.wait_for_timeout(999999999)
            except Exception as e:
                logger.debug(f"Browser closed. Detail: {e}")
    
    except Exception as e:
        logger.error(f"Unexpected ERROR: {e}", exc_info=True)
        print(f"[!] ERROR: {e}")
        print(f"[i] Check log for details: {log_file}")
    
    finally:
        write_log_footer(logger, start_time)
        print(f"[*] Done. Log saved at: {log_file}")

if __name__ == "__main__":
    main()
