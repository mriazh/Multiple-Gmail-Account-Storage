"""Logging configuration with daily rotation and redaction."""

import logging
import logging.handlers
import os
import re
from datetime import datetime


# Redaction patterns — never log these
REDACT_PATTERNS = [
    # Passwords (common parameter names)
    re.compile(r'(password|passwd|pwd|secret|token|key)\s*[=:]\s*\S+', re.IGNORECASE),
    # Recovery keys (XXXX-XXXX-XXXX-XXXX-XXXX format)
    re.compile(r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}'),
    # Fernet keys (base64url, 44 chars)
    re.compile(r'[A-Za-z0-9_-]{43}='),
]

LOGS_DIR = "logs"
LOG_FORMAT = "[%(asctime)s][%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
RETENTION_DAYS = 30


class RedactingFilter(logging.Filter):
    """Filter that redacts sensitive information from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive patterns from the log message."""
        if isinstance(record.msg, str):
            for pattern in REDACT_PATTERNS:
                record.msg = pattern.sub("[REDACTED]", record.msg)
        # Format args too
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact(v) for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact(a) for a in record.args)
        return True

    def _redact(self, value):
        """Redact a single value if it's a string."""
        if isinstance(value, str):
            for pattern in REDACT_PATTERNS:
                value = pattern.sub("[REDACTED]", value)
        return value


def setup_logging() -> None:
    """
    Configure logging with:
    - Daily rotation (logs/YYYY-MM-DD_session.log)
    - Redaction of sensitive data
    - 30-day retention
    - Console output separate from file
    """
    # Ensure logs directory exists
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Clean up old logs (30-day retention)
    _cleanup_old_logs()

    # Create log filename with today's date
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOGS_DIR, f"{today}_session.log")

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    root_logger.handlers.clear()

    # File handler (DEBUG level — captures everything)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    file_handler.addFilter(RedactingFilter())

    # Console handler (WARNING level — minimal output)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    console_handler.addFilter(RedactingFilter())

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info("Logging initialized. Log file: %s", log_file)


def _cleanup_old_logs() -> None:
    """Remove log files older than RETENTION_DAYS."""
    if not os.path.isdir(LOGS_DIR):
        return

    now = datetime.now()

    for filename in os.listdir(LOGS_DIR):
        if filename == ".gitkeep":
            continue
        filepath = os.path.join(LOGS_DIR, filename)
        if not os.path.isfile(filepath):
            continue

        # Try to parse date from filename (YYYY-MM-DD_session.log)
        match = re.match(r'^(\d{4}-\d{2}-\d{2})_', filename)
        if match:
            try:
                file_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                age_days = (now - file_date).days
                if age_days > RETENTION_DAYS:
                    os.remove(filepath)
            except ValueError:
                pass
