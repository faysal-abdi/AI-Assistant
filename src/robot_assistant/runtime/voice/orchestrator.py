"""Voice orchestration primitives tailored for macOS experimentation."""

from __future__ import annotations

import queue
import time
from collections import deque
from dataclasses import dataclass
from time import perf_counter
from typing import Deque, Dict, Optional, Tuple, Any

import os

from robot_assistant.config.defaults import RuntimeConfig, VoiceConfig

try:  # pragma: no cover - optional macOS dependency
    import objc  # type: ignore  # noqa: F401
    from Cocoa import NSSpeechSynthesizer, NSRunLoop, NSDate  # type: ignore
    from Foundation import NSLocale  # type: ignore
    from AVFoundation import AVAudioEngine, AVAudioSession  # type: ignore
    from Speech import (  # type: ignore
        SFSpeechRecognizer,
        SFSpeechAudioBufferRecognitionRequest,
        SFSpeechRecognizerAuthorizationStatusAuthorized,
        SFSpeechRecognizerAuthorizationStatusDenied,
        SFSpeechRecognizerAuthorizationStatusRestricted,
    )

    DISABLE_NATIVE = os.environ.get("ROBOT_ASSISTANT_DISABLE_NATIVE_VOICE") == "1"
    HAS_MAC_SPEECH = not DISABLE_NATIVE
except ImportError:  # pragma: no cover - optional dependency fallback
    HAS_MAC_SPEECH = False


@dataclass
class RecognizedUtterance:
    """Represents a single transcription result."""

    text: str
    confidence: float
    start_ts: float
    end_ts: float


class SpeechRecognizer:
    """Facade over speech-to-text engines (Apple Speech, Vosk, etc.)."""

    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._scripted_inputs: Deque[Tuple[str, float]] = deque()

    def start(self) -> None:
        """Initialize recognizer resources (override in subclasses)."""

    def stop(self) -> None:
        """Release recognizer resources (override in subclasses)."""

    def transcribe_once(self) -> Optional[RecognizedUtterance]:
        """Return one transcription result."""
        if not self._scripted_inputs:
            return None
        text, confidence = self._scripted_inputs.popleft()
        end_ts = perf_counter()
        start_ts = end_ts - max(0.2, len(text.split()) * 0.12)
        return RecognizedUtterance(
            text=text,
            confidence=confidence,
            start_ts=start_ts,
            end_ts=end_ts,
        )

    def enqueue_scripted_input(self, text: str, confidence: float = 0.92) -> None:
        """Add a simulated transcription for testing."""
        self._scripted_inputs.append((text, confidence))


class WakeWordDetector:
    """Wake word listener stub with manual triggers for prototyping."""

    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._triggered: bool = False

    def listen(self) -> bool:
        """Return True if the wake word has been detected."""
        if not self.config.use_wake_word:
            return True
        if self._triggered:
            self._triggered = False
            return True
        return False

    def trigger(self) -> None:
        """Simulate wake word activation."""
        self._triggered = True


class SpeechSynthesizer:
    """Delegates text-to-speech playback to the host OS."""

    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._spoken_log: Deque[str] = deque(maxlen=20)

    def speak(self, text: str) -> None:
        """Play synthesized speech (no-op in prototype)."""
        if not self.config.enable_tts or not text:
            return
        self._spoken_log.append(text)
        # In production integrate with NSSpeechSynthesizer or another backend.

    def get_spoken_log(self) -> Tuple[str, ...]:
        """Return the latest synthesized snippets."""
        return tuple(self._spoken_log)


if HAS_MAC_SPEECH:  # pragma: no cover - macOS specific integration

    class MacSpeechRecognizer(SpeechRecognizer):
        """Speech recognizer backed by AVAudioEngine + SFSpeechRecognizer."""

        def __init__(self, config: VoiceConfig) -> None:
            super().__init__(config)
            self._queue: "queue.Queue[RecognizedUtterance]" = queue.Queue()
            self._audio_engine = AVAudioEngine.alloc().init()
            locale_id = config.transcription_language or "en-US"
            locale = NSLocale.localeWithLocaleIdentifier_(locale_id)
            self._recognizer = SFSpeechRecognizer.alloc().initWithLocale_(locale)
            if self._recognizer is None:
                raise RuntimeError(f"Unsupported locale for speech recognition: {locale_id}")
            self._recognition_request = None
            self._recognition_task = None
            self._result_handler = None
            self._running = False
            self._authorize()
            self._prepare_audio_session()
            self._tap_block = None

        def _authorize(self) -> None:
            status = SFSpeechRecognizer.authorizationStatus()
            if status == SFSpeechRecognizerAuthorizationStatusAuthorized:
                return
            if status in (
                SFSpeechRecognizerAuthorizationStatusDenied,
                SFSpeechRecognizerAuthorizationStatusRestricted,
            ):
                raise RuntimeError("Speech recognition authorization denied")

            status_holder: "queue.Queue[int]" = queue.Queue()

            def completion(auth_status: int) -> None:
                status_holder.put(auth_status)

            SFSpeechRecognizer.requestAuthorization_(completion)
            while status_holder.empty():
                NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
            new_status = status_holder.get()
            if new_status != SFSpeechRecognizerAuthorizationStatusAuthorized:
                raise RuntimeError("Speech recognition authorization not granted")

        def _prepare_audio_session(self) -> None:
            try:
                session = AVAudioSession.sharedInstance()
                # Category and mode strings documented by Apple; ignore errors on macOS if not supported.
                session.setCategory_error_("AVAudioSessionCategoryPlayAndRecord", None)
                session.setMode_error_("AVAudioSessionModeDefault", None)
                session.setActive_error_(True, None)
            except Exception:
                pass

        def start(self) -> None:
            if self._running:
                return
            self._recognition_request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
            self._recognition_request.setShouldReportPartialResults_(True)
            input_node = self._audio_engine.inputNode()
            format = input_node.outputFormatForBus_(0)

            def tap_block(buffer, when) -> None:
                if self._recognition_request is not None:
                    self._recognition_request.appendAudioPCMBuffer_(buffer)

            try:
                input_node.removeTapOnBus_(0)
            except Exception:
                pass

            input_node.installTapOnBus_bufferSize_format_block_(0, 1024, format, tap_block)
            self._tap_block = tap_block
            self._audio_engine.prepare()
            ok = self._audio_engine.startAndReturnError_(None)
            if not ok:
                input_node.removeTapOnBus_(0)
                raise RuntimeError("Failed to start AVAudioEngine for speech recognition")

            self._result_handler = self._build_result_handler()
            self._recognition_task = self._recognizer.recognitionTaskWithRequest_resultHandler_(
                self._recognition_request, self._result_handler
            )
            self._running = True

        def _build_result_handler(self):
            def handler(result, error) -> None:
                if result is not None:
                    text = result.bestTranscription().formattedString()
                    if text:
                        confidence = self._extract_confidence(result)
                        timestamp = time.time()
                        self._queue.put(
                            RecognizedUtterance(
                                text=text,
                                confidence=confidence,
                                start_ts=timestamp,
                                end_ts=timestamp,
                            )
                        )
                    if result.isFinal():
                        self._stop_stream()
                if error is not None:
                    self._stop_stream()

            return handler

        @staticmethod
        def _extract_confidence(result) -> float:
            try:
                segments = result.bestTranscription().segments()
                if segments and hasattr(segments[-1], "confidence"):
                    return float(segments[-1].confidence())
            except Exception:
                pass
            return 0.85

        def _stop_stream(self) -> None:
            if not self._running:
                return
            try:
                input_node = self._audio_engine.inputNode()
                input_node.removeTapOnBus_(0)
            except Exception:
                pass
            try:
                self._audio_engine.stop()
            except Exception:
                pass
            if self._recognition_request is not None:
                try:
                    self._recognition_request.endAudio()
                except Exception:
                    pass
            if self._recognition_task is not None:
                try:
                    self._recognition_task.cancel()
                except Exception:
                    pass
            self._recognition_task = None
            self._recognition_request = None
            self._tap_block = None
            self._running = False

        def stop(self) -> None:
            self._stop_stream()

        def transcribe_once(self) -> Optional[RecognizedUtterance]:
            if not self._queue.empty():
                return self._queue.get()
            return super().transcribe_once()

    class MacSpeechSynthesizer(SpeechSynthesizer):
        """NSSpeechSynthesizer-backed TTS."""

        def __init__(self, config: VoiceConfig) -> None:
            super().__init__(config)
            self._synth = None

        def _ensure_synth(self):
            if self._synth is not None:
                return
            voice = self.config.tts_voice or None
            try:
                if voice:
                    self._synth = NSSpeechSynthesizer.alloc().initWithVoice_(voice)
                if self._synth is None:
                    self._synth = NSSpeechSynthesizer.alloc().init()
            except Exception:
                self._synth = None

        def speak(self, text: str) -> None:
            if not text:
                return
            super().speak(text)
            if not self.config.enable_tts:
                return
            self._ensure_synth()
            if self._synth is None:
                return
            try:
                if self._synth.isSpeaking():
                    self._synth.stopSpeaking()
                self._synth.startSpeakingString_(text)
            except Exception:
                pass


class VoiceOrchestrator:
    """Coordinates wake-word detection, recognition, and synthesis."""

    def __init__(
        self,
        config: RuntimeConfig,
        recognizer: Optional[SpeechRecognizer] = None,
        wake_detector: Optional[WakeWordDetector] = None,
        synthesizer: Optional[SpeechSynthesizer] = None,
    ) -> None:
        self.config = config
        voice_cfg = config.voice
        if recognizer is None and HAS_MAC_SPEECH:
            try:
                recognizer = MacSpeechRecognizer(voice_cfg)  # type: ignore[arg-type]
            except Exception:
                recognizer = None
        self.recognizer = recognizer or SpeechRecognizer(voice_cfg)
        self.wake_detector = wake_detector or WakeWordDetector(voice_cfg)
        if synthesizer is None and HAS_MAC_SPEECH:
            try:
                synthesizer = MacSpeechSynthesizer(voice_cfg)  # type: ignore[arg-type]
            except Exception:
                synthesizer = None
        self.synthesizer = synthesizer or SpeechSynthesizer(voice_cfg)
        self._last_utterance: Optional[RecognizedUtterance] = None
        self.recognizer.start()

    def poll_intent(self) -> Optional[Dict[str, Any]]:
        """Return a runtime intent derived from speech input."""
        if not self.wake_detector.listen():
            return None
        utterance = self.recognizer.transcribe_once()
        if not utterance:
            return None
        self._last_utterance = utterance
        intent = {
            "skill": "assistant",
            "query": utterance.text,
            "confidence": utterance.confidence,
            "source": "voice",
            "timestamps": {"start": utterance.start_ts, "end": utterance.end_ts},
        }
        # Re-arm recognizer for the next utterance.
        try:
            self.recognizer.start()
        except Exception:
            pass
        return intent

    def enqueue_transcript(self, text: str, confidence: float = 0.92) -> None:
        """Add scripted voice input and trigger wake detection."""
        self.recognizer.enqueue_scripted_input(text, confidence)
        self.wake_detector.trigger()

    def speak(self, text: str) -> None:
        """Forward assistant responses to the synthesizer."""
        self.synthesizer.speak(text)

    def last_utterance(self) -> Optional[RecognizedUtterance]:
        """Return the most recent recognized utterance."""
        return self._last_utterance

    def shutdown(self) -> None:
        """Stop voice resources."""
        self.recognizer.stop()
