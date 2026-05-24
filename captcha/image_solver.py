"""Image CAPTCHA solver (minimal/best-effort fallback for v1)."""

import logging
import time

from captcha.solver_base import CaptchaSolver

logger = logging.getLogger(__name__)


class ImageSolver(CaptchaSolver):
    """
    Minimal image CAPTCHA solver.

    For v1, this is a best-effort implementation that:
    - Detects image grid challenges
    - Returns False gracefully if unable to solve
    - Does not crash or hang on unexpected challenge types

    Future versions may integrate AI-based image classification.
    """

    @property
    def name(self) -> str:
        return "ImageSolver"

    def solve(self, page) -> bool:
        """
        Attempt to solve an image CAPTCHA challenge.

        Currently a stub that detects the challenge type and returns False,
        allowing the solver chain to fall through to manual solving.

        Args:
            page: Playwright Page object with CAPTCHA challenge

        Returns:
            False (v1 does not implement automated image solving)
        """
        start_time = time.time()
        logger.info(f"[{self.name}] Checking for image challenge...")

        try:
            challenge_type = self._detect_challenge_type(page)
            elapsed = time.time() - start_time

            if challenge_type:
                logger.info(
                    f"[{self.name}] Detected image challenge type: {challenge_type} "
                    f"({elapsed:.1f}s) — automated solving not available in v1"
                )
            else:
                logger.info(
                    f"[{self.name}] No image challenge detected ({elapsed:.1f}s)"
                )

            # v1: Always return False to fall through to manual solver
            return False

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[{self.name}] Error after {elapsed:.1f}s: {e}")
            return False

    def _detect_challenge_type(self, page) -> str | None:
        """
        Detect what type of image challenge is presented.

        Returns:
            Challenge description string, or None if not detected
        """
        try:
            challenge_frame = page.frame_locator(
                'iframe[src*="recaptcha/api2/bframe"], iframe[title*="challenge"]'
            )

            # Check for image grid (3x3 or 4x4)
            grid = challenge_frame.locator('.rc-imageselect-table-33, .rc-imageselect-table-44')
            if grid.count() > 0:
                # Try to read the instruction text
                instruction = challenge_frame.locator('.rc-imageselect-desc-no-canonical, .rc-imageselect-desc')
                if instruction.count() > 0:
                    text = instruction.first.inner_text()
                    return f"image_grid: {text}"
                return "image_grid: unknown prompt"

            # Check for dynamic tile challenge
            dynamic = challenge_frame.locator('.rc-imageselect-dynamic-selected')
            if dynamic.count() > 0:
                return "dynamic_tile"

            # Check for single image challenge
            single = challenge_frame.locator('.rc-imageselect-challenge')
            if single.count() > 0:
                return "single_image"

            return None

        except Exception as e:
            logger.debug(f"Challenge type detection error: {e}")
            return None
