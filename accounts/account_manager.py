"""Account operations orchestrator: check, add, edit, delete."""

import logging
import getpass

from i18n import t
from accounts import credential_store
from accounts.group_manager import (
    list_groups,
    create_group,
    resolve_group_input,
    get_group_count,
    group_exists,
)
from crypto.profile_encryptor import (
    encrypt_profile,
    decrypt_profile,
    create_backup,
    restore_backup,
    profile_exists,
    cleanup_temp,
)
from crypto.integrity import verify_checksum, update_checksum
from crypto.temp_manager import register_temp_dir, unregister_temp_dir
from browser.browser_launcher import open_browser, wait_for_close, close_browser, get_page

logger = logging.getLogger(__name__)

MAX_ACCOUNTS_PER_GROUP = 5


def check_account(fernet_key: bytes) -> None:
    """
    Check Account operation:
    1. Group selection
    2. Verify checksum
    3. Create backup
    4. Decrypt profile
    5. Open browser with temp dir
    6. Wait for user to close browser
    7. Re-encrypt profile
    8. Update checksum
    9. Cleanup
    """
    group = _select_group()
    if group is None:
        return

    if not profile_exists(group):
        print(t("error.generic", message=f"No encrypted profile for {group}"))
        return

    # Verify integrity
    if not _handle_integrity_check(group):
        return

    temp_dir = None
    browser = None

    try:
        # Backup before decrypt
        print(t("profile.decrypting", group=group))
        create_backup(group)
        temp_dir = decrypt_profile(group, fernet_key)
        register_temp_dir(temp_dir)

        # Open browser
        print(t("browser.opening", group=group))
        browser = open_browser(temp_dir)
        print(t("browser.close_prompt"))

        # Wait for user to close
        wait_for_close(browser)
        print(t("browser.closed"))

    except Exception as e:
        logger.error(f"Check account error: {e}")
        print(t("error.generic", message=str(e)))
        if browser:
            close_browser(browser)
    finally:
        # Always re-encrypt and cleanup
        if temp_dir:
            try:
                print(t("profile.encrypting", group=group))
                encrypt_profile(temp_dir, group, fernet_key)
                update_checksum(group)
            except Exception as e:
                logger.error(f"Re-encryption error: {e}")
                print(t("error.generic", message=f"Re-encryption failed: {e}"))
            finally:
                cleanup_temp(temp_dir)
                unregister_temp_dir(temp_dir)


def add_account(fernet_key: bytes) -> None:
    """
    Add Account operation:
    1. Group select/create
    2. Capacity check (max 5)
    3. Email/password input
    4. Decrypt profile
    5. Login automation
    6. CAPTCHA handling
    7. 2FA pause
    8. Add credential on success
    9. Re-encrypt + update checksum
    """
    group = _select_or_create_group(fernet_key)
    if group is None:
        return

    # Capacity check
    count = get_group_count(group)
    if count >= MAX_ACCOUNTS_PER_GROUP:
        print(t("group.full", name=group))
        print(t("group.full_options"))
        choice = input("Select: ").strip()
        if choice == "1":
            group = _create_new_group()
            if group is None:
                return
        elif choice == "2":
            # Offer to delete an account first
            delete_account(fernet_key)
            # Re-check capacity
            count = get_group_count(group)
            if count >= MAX_ACCOUNTS_PER_GROUP:
                return
        else:
            return

    # Email input
    email = input(t("add.email_prompt")).strip()
    if not _validate_email(email):
        print(t("add.email_invalid"))
        return

    # Check duplicate
    if credential_store.email_exists(group, email):
        print(t("add.email_duplicate", email=email, group=group))
        return

    # Password input
    password = getpass.getpass(t("add.password_prompt", email=email))
    if not password:
        return

    temp_dir = None
    browser = None

    try:
        # Decrypt profile (or create new one if first account in group)
        if profile_exists(group):
            print(t("profile.decrypting", group=group))
            create_backup(group)
            temp_dir = decrypt_profile(group, fernet_key)
        else:
            # Create empty temp dir for new group
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix=f"gam_{group}_")

        register_temp_dir(temp_dir)

        # Open browser and attempt login
        print(t("add.logging_in", email=email))
        browser = open_browser(temp_dir)
        page = get_page(browser)

        # Attempt login
        from browser.login_automator import login, LoginResult
        result = login(page, email, password)

        if result == LoginResult.CAPTCHA_NEEDED:
            from captcha.solver_chain import solve_captcha
            if solve_captcha(page):
                # Retry login after CAPTCHA
                result = login(page, email, password)
            else:
                print(t("add.login_failed", reason="CAPTCHA not solved"))
                close_browser(browser)
                browser = None
                _reencrypt_and_cleanup(temp_dir, group, fernet_key)
                return

        if result == LoginResult.TWO_FA_NEEDED:
            print(t("add.twofa_detected"))
            # Wait for user to complete 2FA
            wait_for_close(browser)
            browser = None

        elif result == LoginResult.WRONG_PASSWORD:
            print(t("add.login_failed", reason="Wrong password"))
            close_browser(browser)
            browser = None
            _reencrypt_and_cleanup(temp_dir, group, fernet_key)
            return

        elif result == LoginResult.UNKNOWN_ERROR:
            print(t("add.login_failed", reason="Unknown error"))
            close_browser(browser)
            browser = None
            _reencrypt_and_cleanup(temp_dir, group, fernet_key)
            return

        elif result == LoginResult.SUCCESS:
            print(t("add.login_success"))
            # Wait for user to close browser
            print(t("browser.close_prompt"))
            wait_for_close(browser)
            browser = None

        # Add credential to store
        credential_store.add(group, email, password, fernet_key)
        print(t("add.login_success"))

    except Exception as e:
        logger.error(f"Add account error: {e}")
        print(t("error.generic", message=str(e)))
        if browser:
            close_browser(browser)
            browser = None
    finally:
        if temp_dir:
            _reencrypt_and_cleanup(temp_dir, group, fernet_key)


def edit_account(fernet_key: bytes) -> None:
    """
    Edit Account operation (manual mode):
    1. Select group/account
    2. Confirm
    3. Decrypt profile
    4. Open browser for user to edit
    5. Close browser
    6. Re-open and verify account
    7. Prompt new password
    8. Update credential
    9. Re-encrypt
    """
    group = _select_group()
    if group is None:
        return

    email = _select_account(group)
    if email is None:
        return

    # Edit mode selection
    print(t("edit.options"))
    mode = input(t("edit.select_mode")).strip()

    if mode == "2":
        print(t("edit.under_dev"))
        return
    elif mode == "3":
        # Delete and re-add
        _confirm_and_delete(group, email, fernet_key, reason="other")
        add_account(fernet_key)
        return
    elif mode != "1":
        return

    # Manual mode
    confirm = input(t("edit.confirm", email=email)).strip().lower()
    if confirm != "y":
        print(t("edit.cancelled"))
        return

    if not profile_exists(group):
        print(t("error.generic", message=f"No encrypted profile for {group}"))
        return

    temp_dir = None
    browser = None

    try:
        # Decrypt
        print(t("profile.decrypting", group=group))
        create_backup(group)
        temp_dir = decrypt_profile(group, fernet_key)
        register_temp_dir(temp_dir)

        # Open browser for user to change password
        print(t("edit.browser_open"))
        browser = open_browser(temp_dir)
        wait_for_close(browser)
        browser = None
        print(t("browser.closed"))

        # Re-open to verify
        print(t("edit.verifying"))
        browser = open_browser(temp_dir)
        page = get_page(browser)

        from browser.login_automator import verify_active_account
        if verify_active_account(page, email):
            print(t("edit.verify_match", email=email))
            close_browser(browser)
            browser = None

            # Prompt for new password
            new_pass = getpass.getpass(t("edit.new_password"))
            confirm_pass = getpass.getpass(t("edit.confirm_password"))

            if new_pass != confirm_pass:
                print(t("edit.password_mismatch"))
                _reencrypt_and_cleanup(temp_dir, group, fernet_key)
                return

            final = input(t("edit.final_confirm")).strip().lower()
            if final == "y":
                credential_store.update_password(group, email, new_pass, fernet_key)
                print(t("edit.success", email=email))
            else:
                print(t("edit.cancelled"))
        else:
            # Mismatch — get active account info
            print(t("edit.verify_mismatch", active="unknown", expected=email))
            close_browser(browser)
            browser = None

    except Exception as e:
        logger.error(f"Edit account error: {e}")
        print(t("error.generic", message=str(e)))
        if browser:
            close_browser(browser)
            browser = None
    finally:
        if temp_dir:
            _reencrypt_and_cleanup(temp_dir, group, fernet_key)


def delete_account(fernet_key: bytes) -> None:
    """
    Delete Account operation:
    - Banned: double confirm → remove credential (no browser)
    - Other: double confirm → decrypt → sign out → remove → re-encrypt
    """
    group = _select_group()
    if group is None:
        return

    email = _select_account(group)
    if email is None:
        return

    # First confirmation
    confirm = input(t("delete.confirm", email=email, group=group)).strip().lower()
    if confirm != "y":
        print(t("delete.cancelled"))
        return

    # Reason
    print(t("delete.reason"))
    reason = input(t("delete.reason_prompt")).strip()

    if reason == "1":
        _delete_banned(group, email)
    else:
        _delete_other(group, email, fernet_key)


def _delete_banned(group: str, email: str) -> None:
    """Delete a banned account (no browser needed)."""
    confirm = input(t("delete.banned_confirm")).strip().lower()
    if confirm != "y":
        print(t("delete.cancelled"))
        return

    credential_store.remove(group, email)
    print(t("delete.success", email=email, group=group))


def _delete_other(group: str, email: str, fernet_key: bytes) -> None:
    """Delete account with sign-out flow."""
    confirm = input(t("delete.other_confirm")).strip().lower()
    if confirm != "y":
        print(t("delete.cancelled"))
        return

    if not profile_exists(group):
        # No profile — just remove credential
        credential_store.remove(group, email)
        print(t("delete.success", email=email, group=group))
        return

    temp_dir = None
    browser = None

    try:
        # Decrypt
        print(t("profile.decrypting", group=group))
        create_backup(group)
        temp_dir = decrypt_profile(group, fernet_key)
        register_temp_dir(temp_dir)

        # Open browser and sign out
        print(t("delete.signing_out", email=email))
        browser = open_browser(temp_dir)
        page = get_page(browser)

        from browser.logout_handler import signout
        success = signout(page, email)

        close_browser(browser)
        browser = None

        if success:
            print(t("delete.signout_success"))
            credential_store.remove(group, email)
            print(t("delete.success", email=email, group=group))
        else:
            print(t("delete.signout_failed"))
            force = input(t("general.yes_no")).strip().lower()
            if force == "y":
                credential_store.remove(group, email)
                print(t("delete.success", email=email, group=group))
            else:
                print(t("delete.cancelled"))

    except Exception as e:
        logger.error(f"Delete account error: {e}")
        print(t("error.generic", message=str(e)))
        if browser:
            close_browser(browser)
            browser = None
    finally:
        if temp_dir:
            _reencrypt_and_cleanup(temp_dir, group, fernet_key)


def _confirm_and_delete(group: str, email: str, fernet_key: bytes, reason: str) -> None:
    """Delete account as part of edit flow (skip first confirmation)."""
    if reason == "banned":
        _delete_banned(group, email)
    else:
        _delete_other(group, email, fernet_key)


# ─── Helper functions ───────────────────────────────────────────────────────


def _select_group() -> str | None:
    """Display groups and let user select one."""
    groups = list_groups()

    if not groups:
        print(t("group.no_groups"))
        return None

    print(t("group.list_header"))
    for i, g in enumerate(groups, 1):
        print(t("group.item", num=i, name=g["name"], count=g["count"]))

    choice = input(t("group.select")).strip()
    resolved = resolve_group_input(choice)

    if resolved is None:
        print(t("group.invalid"))
        return None

    return resolved


def _select_or_create_group(fernet_key: bytes) -> str | None:
    """Select existing group or create new one."""
    groups = list_groups()

    if not groups:
        print(t("group.no_groups"))
        create = input(t("group.create_offer")).strip().lower()
        if create == "y":
            return _create_new_group()
        return None

    print(t("group.list_header"))
    for i, g in enumerate(groups, 1):
        print(t("group.item", num=i, name=g["name"], count=g["count"]))

    print(f"  {len(groups) + 1}. [Create new group]")
    choice = input(t("group.select")).strip()

    # Check if user wants to create new
    if choice == str(len(groups) + 1):
        return _create_new_group()

    resolved = resolve_group_input(choice)
    if resolved is None:
        print(t("group.invalid"))
        return None

    return resolved


def _create_new_group() -> str | None:
    """Create a new group with user input."""
    name_input = input(t("group.new_name")).strip()

    try:
        if name_input:
            group = create_group(name_input)
        else:
            group = create_group()  # Auto-increment
        print(t("group.created", name=group))
        return group
    except ValueError as e:
        print(t("error.generic", message=str(e)))
        return None


def _select_account(group: str) -> str | None:
    """Display accounts in a group and let user select one."""
    emails = credential_store.get_emails(group)

    if not emails:
        print(t("account.no_accounts"))
        return None

    print(t("account.emails_header", group=group))
    for i, email in enumerate(emails, 1):
        print(t("account.email_item", num=i, email=email))

    choice = input(t("account.select")).strip()

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(emails):
            return emails[idx]

    print(t("account.invalid"))
    return None


def _validate_email(email: str) -> bool:
    """Basic email format validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _handle_integrity_check(group: str) -> bool:
    """Handle integrity check with user options on failure."""
    if verify_checksum(group):
        return True

    print(t("profile.integrity_fail", group=group))
    print(t("profile.integrity_options"))
    choice = input(t("profile.integrity_prompt")).strip()

    if choice == "1":
        return True  # Try anyway
    elif choice == "2":
        if restore_backup(group):
            print(t("profile.backup_restored"))
            return True
        else:
            print(t("error.generic", message="No backup available"))
            return False
    else:
        print(t("general.cancelled"))
        return False


def _reencrypt_and_cleanup(temp_dir: str, group: str, fernet_key: bytes) -> None:
    """Re-encrypt profile and cleanup temp directory."""
    try:
        print(t("profile.encrypting", group=group))
        encrypt_profile(temp_dir, group, fernet_key)
        update_checksum(group)
    except Exception as e:
        logger.error(f"Re-encryption error: {e}")
        print(t("error.generic", message=f"Re-encryption failed: {e}"))
    finally:
        cleanup_temp(temp_dir)
        unregister_temp_dir(temp_dir)
