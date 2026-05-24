"""Master authentication: setup, login, lockout."""

import getpass
import secrets
import string
from datetime import datetime, timedelta

from i18n import t
from crypto.key_derivation import (
    derive_fernet_key,
    generate_salt,
    hash_credential,
    verify_credential,
)
from auth.auth_config import (
    auth_config_exists,
    create_auth_config,
    load_auth_config,
    save_auth_config,
    update_lockout,
    reset_lockout,
    update_credential,
)
from auth.email_sender import send_verification, smtp_config_exists, setup_smtp_config

import base64


# Lockout constants
MAX_ATTEMPTS = 10
BASE_LOCKOUT_MINUTES = 5
MAX_LOCKOUT_MINUTES = 1440  # 24 hours
LOCKOUT_RESET_HOURS = 24


def first_time_setup() -> bytes | None:
    """
    First-time setup flow:
    1. Email verification
    2. PIN/Password choice
    3. Hint
    4. Recovery Key generation
    5. Hash all credentials
    6. Save to auth_config.json
    7. Return derived Fernet key

    Returns:
        Fernet key bytes on success, None on failure/cancel
    """
    print(t("auth.setup.welcome"))
    print()

    # Step 1: SMTP setup if not configured
    if not smtp_config_exists():
        print("SMTP configuration required for email verification.")
        smtp_user = input("Yandex email address: ").strip()
        smtp_password = getpass.getpass("Yandex app password: ")
        setup_smtp_config(smtp_user=smtp_user, smtp_password=smtp_password)
        print()

    # Step 2: Recovery email verification
    recovery_email = _verify_recovery_email()
    if recovery_email is None:
        return None

    # Step 3: Credential type choice (PIN or Password)
    credential_type, credential = _choose_credential()
    if credential is None:
        return None

    # Step 4: Hint
    type_label = "PIN" if credential_type == "pin" else "Password"
    hint = input(t("auth.setup.hint_prompt", type=type_label)).strip()

    # Step 5: Recovery Key generation
    recovery_key = _generate_recovery_key()
    print(t("auth.setup.recovery_key_header"))
    print(t("auth.setup.recovery_key_warning"))
    print(t("auth.setup.recovery_key_display", key=recovery_key))
    input(t("auth.setup.recovery_key_ack"))

    # Step 6: Hash all credentials
    credential_hash = hash_credential(credential)
    recovery_email_hash = hash_credential(recovery_email.lower())
    recovery_key_hash = hash_credential(recovery_key)

    # Generate salt for Fernet key derivation
    salt = generate_salt()
    credential_salt = base64.b64encode(salt).decode("utf-8")

    # Step 7: Save auth config
    config = create_auth_config(
        credential_type=credential_type,
        credential_hash=credential_hash,
        credential_salt=credential_salt,
        recovery_email_hash=recovery_email_hash,
        recovery_key_hash=recovery_key_hash,
        hint=hint,
    )
    save_auth_config(config)

    # Step 8: Derive and return Fernet key
    fernet_key = derive_fernet_key(credential, salt)

    print()
    print(t("auth.setup.complete"))
    return fernet_key


def login() -> bytes | None:
    """
    Normal login flow:
    1. Check lockout state
    2. Prompt PIN/Password
    3. Verify against hash
    4. Max 10 attempts with exponential backoff
    5. Derive Fernet key on success

    Returns:
        Fernet key bytes on success, None triggers recovery
    """
    config = load_auth_config()
    if config is None:
        return None

    # Check lockout
    if _is_locked_out(config):
        lockout_until = config["lockout"]["lockout_until"]
        remaining = _get_lockout_remaining_minutes(lockout_until)
        print(t("auth.login.locked", minutes=remaining))
        return None

    # Check if 24h has passed since last failure → reset counter
    _check_24h_reset(config)

    credential_type = config.get("credential_type", "pin")
    prompt_key = "auth.login.prompt_pin" if credential_type == "pin" else "auth.login.prompt_password"

    attempts_used = config["lockout"]["failed_attempts"]
    remaining_attempts = MAX_ATTEMPTS - attempts_used

    while remaining_attempts > 0:
        # Prompt for credential
        credential = getpass.getpass(t(prompt_key))

        # Verify
        if verify_credential(credential, config["credential_hash"]):
            # Success — reset lockout and derive key
            reset_lockout()
            salt = base64.b64decode(config["credential_salt"])
            fernet_key = derive_fernet_key(credential, salt)
            print(t("auth.login.success"))
            return fernet_key

        # Failed attempt
        attempts_used += 1
        remaining_attempts = MAX_ATTEMPTS - attempts_used

        if remaining_attempts > 0:
            print(t("auth.login.wrong", remaining=remaining_attempts))

            # Offer hint
            show_hint = input(t("auth.login.show_hint")).strip().lower()
            if show_hint == "y":
                print(t("auth.login.hint", hint=config.get("hint", "")))
        else:
            # Max attempts reached — trigger lockout
            _apply_lockout(config)
            print(t("auth.login.locked", minutes=_get_current_lockout_minutes(config)))

    # Offer recovery
    type_label = "PIN" if credential_type == "pin" else "Password"
    print(t("auth.login.forgot", type=type_label))
    return None


def _verify_recovery_email() -> str | None:
    """Verify recovery email with 6-digit code. Returns email or None."""
    email = input(t("auth.setup.email_prompt")).strip()
    if not email:
        return None

    confirm = input(t("auth.setup.email_confirm", email=email)).strip().lower()
    if confirm != "y":
        return None

    # Send verification code
    try:
        code, timestamp = send_verification(email)
    except Exception as e:
        print(t("error.smtp_failed"))
        retry = input(t("general.yes_no")).strip().lower()
        if retry == "y":
            return _verify_recovery_email()
        return None

    print(t("auth.setup.code_sent", email=email))

    # Verify code (3 attempts, 10 min expiry)
    for attempt in range(3):
        user_code = input(t("auth.setup.code_prompt")).strip()

        # Check expiry
        if (datetime.now() - timestamp).total_seconds() > 600:
            # Code expired, resend
            print(t("auth.setup.code_expired"))
            try:
                code, timestamp = send_verification(email)
            except Exception:
                print(t("error.smtp_failed"))
                return None
            continue

        if user_code == code:
            return email

        print(t("auth.setup.code_invalid"))

    return None


def _choose_credential() -> tuple[str, str | None]:
    """
    Let user choose PIN or Password and validate input.
    Returns (type, credential) or ("", None) on failure.
    """
    print(t("auth.setup.type_prompt"), end="")
    choice = input().strip()

    if choice == "1":
        return _setup_pin()
    elif choice == "2":
        return _setup_password()
    else:
        # Default to PIN
        return _setup_pin()


def _setup_pin() -> tuple[str, str | None]:
    """PIN setup with validation and confirmation."""
    for _ in range(5):  # Max 5 retries
        pin = getpass.getpass(t("auth.setup.pin_prompt"))

        # Validate: 4-8 digits
        if not pin.isdigit() or not (4 <= len(pin) <= 8):
            print(t("auth.setup.pin_invalid"))
            continue

        confirm = getpass.getpass(t("auth.setup.pin_confirm"))
        if pin != confirm:
            print(t("auth.setup.pin_mismatch"))
            continue

        return "pin", pin

    return "", None


def _setup_password() -> tuple[str, str | None]:
    """Password setup with validation and confirmation."""
    for _ in range(5):  # Max 5 retries
        password = getpass.getpass(t("auth.setup.password_prompt"))

        # Validate: 8+ characters
        if len(password) < 8:
            print(t("auth.setup.password_invalid"))
            continue

        confirm = getpass.getpass(t("auth.setup.password_confirm"))
        if password != confirm:
            print(t("auth.setup.password_mismatch"))
            continue

        return "password", password

    return "", None


def _generate_recovery_key() -> str:
    """Generate recovery key in XXXX-XXXX-XXXX-XXXX-XXXX format."""
    chars = string.ascii_uppercase + string.digits
    segments = []
    for _ in range(5):
        segment = "".join(secrets.choice(chars) for _ in range(4))
        segments.append(segment)
    return "-".join(segments)


def _is_locked_out(config: dict) -> bool:
    """Check if currently locked out."""
    lockout_until = config["lockout"].get("lockout_until")
    if lockout_until is None:
        return False

    try:
        until = datetime.fromisoformat(lockout_until)
        return datetime.now() < until
    except (ValueError, TypeError):
        return False


def _get_lockout_remaining_minutes(lockout_until: str) -> int:
    """Get remaining lockout minutes."""
    try:
        until = datetime.fromisoformat(lockout_until)
        remaining = (until - datetime.now()).total_seconds() / 60
        return max(1, int(remaining))
    except (ValueError, TypeError):
        return 0


def _get_current_lockout_minutes(config: dict) -> int:
    """Calculate lockout duration for current backoff level."""
    level = config["lockout"].get("backoff_level", 0)
    minutes = min(BASE_LOCKOUT_MINUTES * (2 ** level), MAX_LOCKOUT_MINUTES)
    return minutes


def _apply_lockout(config: dict) -> None:
    """Apply lockout with exponential backoff."""
    level = config["lockout"].get("backoff_level", 0)
    minutes = min(BASE_LOCKOUT_MINUTES * (2 ** level), MAX_LOCKOUT_MINUTES)
    lockout_until = (datetime.now() + timedelta(minutes=minutes)).isoformat()

    update_lockout(
        failed_attempts=MAX_ATTEMPTS,
        backoff_level=level + 1,
        lockout_until=lockout_until,
    )


def _check_24h_reset(config: dict) -> None:
    """Reset failed attempts counter if 24h has passed since last failure."""
    last_failed = config["lockout"].get("last_failed")
    if last_failed is None:
        return

    try:
        last = datetime.fromisoformat(last_failed)
        if (datetime.now() - last).total_seconds() > LOCKOUT_RESET_HOURS * 3600:
            reset_lockout()
    except (ValueError, TypeError):
        pass
