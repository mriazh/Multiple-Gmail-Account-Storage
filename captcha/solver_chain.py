"""Ordered CAPTCHA solver chain: Audio → Image → Manual."""

import logging
import time

from i18n import t
from captcha.audio_solver import AudioSolver
from captcha.image_solver import ImageSolver
from captcha.solver_base import CaptchaSolver

logger = logging.getLogger(__name__)

# Manual solver timeout (10 minutes)
MANUAL_TIMEOUT_SECONDS = 600
MANUAL_POLL_INTERVAL = 5  # Check every 5 seconds


class ManualSolver(CaptchaSolver):
    """
    Manual fallback: notify user and wait for them to solve CAPTCHA.
    Polls for resolution with a 10-minute timeout.
    """

    @property
    def name(self) -> str:
        return "ManualSolver"

    def solve(self, page) -> bool:
        """
        Wait for user to manually solve the CAPTCHA.

        Notifies user, then polls every 5 seconds for up to 10 minutes.
        If timeout reached, prompts user to cancel or keep waiting.
        """
        start_time = time.time()
        logger.info(f"[{self.name}] Waiting for manual CAPTCHA solve...")
        print(t("add.captcha_manual"))

        while True:
            elapsed = time.time() - start_time

            # Check if solved
            if not CaptchaSolver.detect_captcha(page):
                logger.info(f"[{self.name}] CAPTCHA resolved manually ({elapsed:.1f}s)")
                return True

            # Check timeout
            if elapsed >= MANUAL_TIMEOUT_SECONDS:
                cancel = input(t("add.captcha_timeout")).strip().lower()
                if cancel == "y":
                    logger.info(f"[{self.name}] User cancelled after timeout")
                    return False
                # Reset timer for another round
                start_time = time.time()

            # Poll interval
            time.sleep(MANUAL_POLL_INTERVAL)


def solve_captcha(page) -> bool:
    """
    Execute the solver chain in order: Audio → Image → Manual.

    Each solver is tried once. If it fails, the next solver is attempted.
    Logs each attempt with solver name, duration, and result.

    Args:
        page: Playwright Page object with CAPTCHA challenge

    Returns:
        True if any solver succeeded, False if all failed
    """
    solvers = [
        AudioSolver(),
        ImageSolver(),
        ManualSolver(),
    ]

    print(t("add.captcha_detected"))

    for solver in solvers:
        logger.info(f"Trying solver: {solver.name}")
        start = time.time()

        try:
            result = solver.solve(page)
            duration = time.time() - start

            logger.info(
                f"Solver {solver.name}: {'SUCCESS' if result else 'FAILED'} "
                f"(duration: {duration:.1f}s)"
            )

            if result:
                return True

        except Exception as e:
            duration = time.time() - start
            logger.error(f"Solver {solver.name}: ERROR after {duration:.1f}s — {e}")
            continue

    logger.warning("All CAPTCHA solvers failed")
    return False
