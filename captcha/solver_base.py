"""Abstract CAPTCHA solver interface."""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CaptchaSolver(ABC):
    """
    Abstract base class for CAPTCHA solvers.
    
    All CAPTCHA solving implementations must inherit from this class
    and implement the solve() method and name property.
    
    This provides a pluggable interface — new solvers (2Captcha, CapSolver)
    can be added by creating a new class that inherits CaptchaSolver
    without modifying existing code.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable solver name for logging."""
        ...
    
    @abstractmethod
    def solve(self, page) -> bool:
        """
        Attempt to solve a CAPTCHA on the given page.
        
        Args:
            page: Playwright Page object with a CAPTCHA challenge
            
        Returns:
            True if CAPTCHA was solved successfully, False otherwise
        """
        ...
    
    @staticmethod
    def detect_captcha(page) -> bool:
        """
        Check if a reCAPTCHA iframe is present on the current page.
        
        Args:
            page: Playwright Page object to check
            
        Returns:
            True if reCAPTCHA is detected, False otherwise
        """
        try:
            # Check for reCAPTCHA iframe
            recaptcha_frame = page.frame_locator(
                'iframe[src*="recaptcha"], iframe[title*="reCAPTCHA"]'
            )
            # Try to find the checkbox or challenge
            checkbox = recaptcha_frame.locator('.recaptcha-checkbox-border')
            return checkbox.count() > 0
        except Exception:
            return False
    
    @staticmethod
    def detect_captcha_challenge(page) -> bool:
        """
        Check if a reCAPTCHA challenge (not just checkbox) is active.
        
        Args:
            page: Playwright Page object to check
            
        Returns:
            True if an active challenge is detected
        """
        try:
            # Check for the challenge iframe (appears after clicking checkbox)
            challenge_frame = page.frame_locator(
                'iframe[src*="recaptcha"][title*="challenge"], '
                'iframe[src*="recaptcha/api2/bframe"]'
            )
            return challenge_frame.locator('body').count() > 0
        except Exception:
            return False
