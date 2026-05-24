"""Yandex SMTP email verification code sender."""

import json
import os
import secrets
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from cryptography.fernet import Fernet

from crypto.key_derivation import derive_smtp_key

SMTP_CONFIG_PATH = os.path.join("config", "smtp_config.json")


def generate_code() -> str:
    """Generate a random 6-digit verification code."""
    return str(secrets.randbelow(900000) + 100000)


def _load_smtp_config() -> dict:
    """Load and decrypt SMTP configuration."""
    if not os.path.exists(SMTP_CONFIG_PATH):
        raise FileNotFoundError(
            "SMTP configuration not found. Run initial setup first."
        )

    with open(SMTP_CONFIG_PATH, "rb") as f:
        encrypted_data = f.read()

    key = derive_smtp_key()
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted_data)
    return json.loads(decrypted.decode("utf-8"))


def _save_smtp_config(config: dict) -> None:
    """Encrypt and save SMTP configuration."""
    from utils import atomic_write_bytes

    os.makedirs("config", exist_ok=True)
    key = derive_smtp_key()
    fernet = Fernet(key)

    plaintext = json.dumps(config, indent=2).encode("utf-8")
    encrypted = fernet.encrypt(plaintext)
    atomic_write_bytes(SMTP_CONFIG_PATH, encrypted)


def setup_smtp_config(
    smtp_host: str = "smtp.yandex.com",
    smtp_port: int = 465,
    smtp_user: str = "",
    smtp_password: str = "",
    sender_display_name: str = "Gmail Account Manager",
) -> None:
    """
    Set up SMTP configuration (run once during initial setup).

    Encrypts and stores the SMTP credentials using machine-bound key.
    """
    config = {
        "version": "1.0",
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_password": smtp_password,
        "sender_display_name": sender_display_name,
    }
    _save_smtp_config(config)


def send_verification(target_email: str) -> tuple[str, datetime]:
    """
    Send a 6-digit verification code to the target email.

    Returns:
        Tuple of (code, timestamp) where timestamp is when the code was generated.

    Raises:
        FileNotFoundError: If SMTP config doesn't exist
        smtplib.SMTPException: If email delivery fails
    """
    config = _load_smtp_config()
    code = generate_code()
    timestamp = datetime.now()

    # Compose email
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{config['sender_display_name']} <{config['smtp_user']}>"
    msg["To"] = target_email
    msg["Subject"] = "Verification Code - Gmail Account Manager"

    # Plain text body
    text_body = (
        f"Your verification code is: {code}\n\n"
        f"This code is valid for 10 minutes.\n\n"
        f"If you did not request this code, please ignore this email."
    )

    # HTML body
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>Verification Code</h2>
        <p>Your verification code is:</p>
        <h1 style="color: #2196F3; letter-spacing: 5px; font-size: 36px;">{code}</h1>
        <p>This code is valid for <strong>10 minutes</strong>.</p>
        <hr>
        <p style="color: #666; font-size: 12px;">
            If you did not request this code, please ignore this email.
        </p>
    </body>
    </html>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Send via SMTP SSL
    with smtplib.SMTP_SSL(config["smtp_host"], config["smtp_port"]) as server:
        server.login(config["smtp_user"], config["smtp_password"])
        server.send_message(msg)

    return code, timestamp


def smtp_config_exists() -> bool:
    """Check if SMTP configuration file exists."""
    return os.path.exists(SMTP_CONFIG_PATH)
