"""Tests for logging_config.py — logging setup and redaction."""

import logging
import os
from datetime import datetime

from logging_config import setup_logging, RedactingFilter, LOGS_DIR


class TestRedactingFilter:
    def test_redacts_password_pattern(self):
        filt = RedactingFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="password=MySecret123", args=None, exc_info=None,
        )
        filt.filter(record)
        assert "MySecret123" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_redacts_recovery_key(self):
        filt = RedactingFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Key is AB12-CD34-EF56-GH78-IJ90", args=None, exc_info=None,
        )
        filt.filter(record)
        assert "AB12-CD34-EF56-GH78-IJ90" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_preserves_normal_messages(self):
        filt = RedactingFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="User logged in: user@gmail.com", args=None, exc_info=None,
        )
        filt.filter(record)
        assert "user@gmail.com" in record.msg

    def test_redacts_token_pattern(self):
        filt = RedactingFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="token=abc123xyz", args=None, exc_info=None,
        )
        filt.filter(record)
        assert "abc123xyz" not in record.msg


class TestSetupLogging:
    def test_creates_log_dir(self, project_dir):
        # Remove logs dir
        import shutil
        if os.path.exists(LOGS_DIR):
            shutil.rmtree(LOGS_DIR)

        setup_logging()
        assert os.path.isdir(LOGS_DIR)

    def test_creates_log_file(self, project_dir):
        setup_logging()
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(LOGS_DIR, f"{today}_session.log")
        # Log something to trigger file creation
        logging.info("test message")
        assert os.path.exists(log_file)

    def test_log_content(self, project_dir):
        setup_logging()
        logging.info("Hello from test")
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(LOGS_DIR, f"{today}_session.log")
        with open(log_file, "r") as f:
            content = f.read()
        assert "Hello from test" in content
