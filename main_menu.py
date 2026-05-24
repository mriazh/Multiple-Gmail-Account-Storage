"""Gmail Account Manager - Main entry point and menu loop."""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logging_config import setup_logging
from i18n import set_language, t
from config_manager import (
    load_settings,
    save_settings,
    is_first_run,
    get_language,
    set_language_preference,
    set_first_run_complete,
)
from auth.auth_config import auth_config_exists
from auth.master_auth import first_time_setup, login
from auth.recovery import recovery_menu
from crypto.temp_manager import prompt_orphan_cleanup, cleanup_all_temp_dirs
from accounts.account_manager import (
    check_account,
    add_account,
    edit_account,
    delete_account,
)


def main():
    """Application entry point."""
    # Initialize logging first
    setup_logging()

    try:
        # Load settings and set language
        settings = load_settings()
        set_language(settings.get("language", "en"))

        # Startup flow
        fernet_key = _startup_flow()
        if fernet_key is None:
            # Authentication failed or user cancelled
            return

        # Register signal handlers for graceful shutdown
        from signal_handlers import setup_signal_handlers
        setup_signal_handlers(fernet_key)

        # Scan for orphaned temp dirs from previous crashes
        prompt_orphan_cleanup()

        # Check gitignore warning (once per session)
        from accounts.credential_store import check_gitignore_warning
        if not check_gitignore_warning():
            print("[!] Warning: accounts.json is not in .gitignore")

        # Main menu loop
        _menu_loop(fernet_key)

    except KeyboardInterrupt:
        print("\n" + t("general.quit_cleanup"))
        cleanup_all_temp_dirs()
        print(t("general.quit"))
    except Exception as e:
        print(t("error.generic", message=str(e)))
        cleanup_all_temp_dirs()


def _startup_flow() -> bytes | None:
    """
    Handle startup:
    - First run: language selection + first_time_setup
    - Subsequent runs: login with lockout check

    Returns:
        Fernet key on success, None on failure
    """
    if is_first_run() or not auth_config_exists():
        # First run — language selection
        fernet_key = _first_run_flow()
        return fernet_key
    else:
        # Normal login
        fernet_key = login()
        if fernet_key is None:
            # Login failed — offer recovery
            fernet_key = recovery_menu()
        return fernet_key


def _first_run_flow() -> bytes | None:
    """First-time setup: language selection + credential setup."""
    print(t("lang.prompt"))
    print(t("lang.option_en"))
    print(t("lang.option_id"))

    while True:
        choice = input("> ").strip()
        if choice == "1":
            set_language("en")
            set_language_preference("en")
            break
        elif choice == "2":
            set_language("id")
            set_language_preference("id")
            break
        else:
            print(t("lang.invalid"))

    print()

    # Run first-time setup
    fernet_key = first_time_setup()
    if fernet_key is not None:
        set_first_run_complete()
    return fernet_key


def _menu_loop(fernet_key: bytes) -> None:
    """Main menu display and routing loop."""
    while True:
        print()
        print(t("menu.title"))
        print(t("menu.header"))
        print(t("menu.separator"))
        print(t("menu.check"))
        print(t("menu.add"))
        print(t("menu.edit"))
        print(t("menu.delete"))
        print(t("menu.quit"))
        print()

        choice = input(t("menu.prompt")).strip()

        if choice == "1":
            check_account(fernet_key)
        elif choice == "2":
            add_account(fernet_key)
        elif choice == "3":
            edit_account(fernet_key)
        elif choice == "4":
            delete_account(fernet_key)
        elif choice == "5":
            _quit(fernet_key)
            break
        else:
            print(t("menu.invalid"))


def _quit(fernet_key: bytes) -> None:
    """Graceful quit with cleanup."""
    print(t("general.quit_cleanup"))
    cleanup_all_temp_dirs()
    print(t("general.quit"))


if __name__ == "__main__":
    main()
