"""Audio CAPTCHA solver using speech recognition."""

import logging
import os
import tempfile
import time
import urllib.request

from captcha.solver_base import CaptchaSolver

logger = logging.getLogger(__name__)


class AudioSolver(CaptchaSolver):
    """
    Solve reCAPTCHA via audio challenge:
    1. Click "I'm not a robot" checkbox
    2. Click audio challenge icon
    3. Download mp3 audio
    4. Convert to wav (pydub/FFmpeg)
    5. Speech recognition
    6. Submit text answer
    7. Verify success
    """

    @property
    def name(self) -> str:
        return "AudioSolver"

    def solve(self, page) -> bool:
        """
        Attempt to solve reCAPTCHA via audio challenge.

        Args:
            page: Playwright Page object with reCAPTCHA

        Returns:
            True if solved, False otherwise
        """
        start_time = time.time()
        logger.info(f"[{self.name}] Starting audio CAPTCHA solve attempt")

        try:
            # Step 1: Click the reCAPTCHA checkbox
            if not self._click_checkbox(page):
                logger.warning(f"[{self.name}] Failed to click checkbox")
                return False

            # Check if already solved (sometimes clicking checkbox is enough)
            if self._is_solved(page):
                elapsed = time.time() - start_time
                logger.info(f"[{self.name}] Solved by checkbox click alone ({elapsed:.1f}s)")
                return True

            # Step 2: Switch to audio challenge
            if not self._switch_to_audio(page):
                logger.warning(f"[{self.name}] Failed to switch to audio challenge")
                return False

            # Step 3: Download audio
            audio_url = self._get_audio_url(page)
            if not audio_url:
                logger.warning(f"[{self.name}] Failed to get audio URL")
                return False

            # Step 4: Download and convert audio
            audio_text = self._transcribe_audio(audio_url)
            if not audio_text:
                logger.warning(f"[{self.name}] Failed to transcribe audio")
                return False

            # Step 5: Submit answer
            if not self._submit_answer(page, audio_text):
                logger.warning(f"[{self.name}] Failed to submit answer")
                return False

            # Step 6: Verify
            page.wait_for_timeout(2000)
            solved = self._is_solved(page)

            elapsed = time.time() - start_time
            logger.info(f"[{self.name}] Result: {'SOLVED' if solved else 'FAILED'} ({elapsed:.1f}s)")
            return solved

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[{self.name}] Error after {elapsed:.1f}s: {e}")
            return False

    def _click_checkbox(self, page) -> bool:
        """Click the reCAPTCHA 'I'm not a robot' checkbox."""
        try:
            # Find the reCAPTCHA iframe
            recaptcha_frame = page.frame_locator(
                'iframe[src*="recaptcha/api2/anchor"], iframe[title*="reCAPTCHA"]'
            )
            checkbox = recaptcha_frame.locator('#recaptcha-anchor')
            checkbox.click(timeout=10000)
            page.wait_for_timeout(2000)
            return True
        except Exception as e:
            logger.debug(f"Checkbox click error: {e}")
            return False

    def _is_solved(self, page) -> bool:
        """Check if reCAPTCHA is solved (checkbox checked)."""
        try:
            recaptcha_frame = page.frame_locator(
                'iframe[src*="recaptcha/api2/anchor"], iframe[title*="reCAPTCHA"]'
            )
            anchor = recaptcha_frame.locator('#recaptcha-anchor')
            aria_checked = anchor.get_attribute("aria-checked")
            return aria_checked == "true"
        except Exception:
            return False

    def _switch_to_audio(self, page) -> bool:
        """Click the audio challenge button in the challenge iframe."""
        try:
            challenge_frame = page.frame_locator(
                'iframe[src*="recaptcha/api2/bframe"], iframe[title*="challenge"]'
            )
            audio_button = challenge_frame.locator('#recaptcha-audio-button')
            audio_button.click(timeout=10000)
            page.wait_for_timeout(2000)
            return True
        except Exception as e:
            logger.debug(f"Switch to audio error: {e}")
            return False

    def _get_audio_url(self, page) -> str | None:
        """Extract the audio download URL from the challenge."""
        try:
            challenge_frame = page.frame_locator(
                'iframe[src*="recaptcha/api2/bframe"], iframe[title*="challenge"]'
            )
            # The audio source link
            audio_source = challenge_frame.locator('.rc-audiochallenge-tdownload-link')
            href = audio_source.get_attribute("href")
            if href:
                return href

            # Alternative: look for audio element
            audio_elem = challenge_frame.locator('audio source')
            src = audio_elem.get_attribute("src")
            return src
        except Exception as e:
            logger.debug(f"Get audio URL error: {e}")
            return None

    def _transcribe_audio(self, audio_url: str) -> str | None:
        """Download audio, convert to wav, and transcribe."""
        temp_mp3 = None
        temp_wav = None

        try:
            # Download mp3
            temp_mp3 = tempfile.mktemp(suffix=".mp3")
            urllib.request.urlretrieve(audio_url, temp_mp3)
            logger.debug(f"Downloaded audio to {temp_mp3}")

            # Convert to wav using pydub
            from pydub import AudioSegment
            audio = AudioSegment.from_mp3(temp_mp3)
            temp_wav = tempfile.mktemp(suffix=".wav")
            audio.export(temp_wav, format="wav")
            logger.debug(f"Converted to wav: {temp_wav}")

            # Speech recognition
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(temp_wav) as source:
                audio_data = recognizer.record(source)

            text = recognizer.recognize_google(audio_data)
            logger.info(f"Transcribed text: {text}")
            return text.strip()

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
        finally:
            # Cleanup temp files
            for f in [temp_mp3, temp_wav]:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except OSError:
                        pass

    def _submit_answer(self, page, text: str) -> bool:
        """Type the transcribed text and submit."""
        try:
            challenge_frame = page.frame_locator(
                'iframe[src*="recaptcha/api2/bframe"], iframe[title*="challenge"]'
            )
            # Find the response input
            response_input = challenge_frame.locator('#audio-response')
            response_input.fill(text)

            # Click verify button
            verify_button = challenge_frame.locator('#recaptcha-verify-button')
            verify_button.click()
            page.wait_for_timeout(2000)
            return True
        except Exception as e:
            logger.debug(f"Submit answer error: {e}")
            return False
