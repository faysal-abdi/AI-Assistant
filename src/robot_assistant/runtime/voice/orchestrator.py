"""Voice orchestration primitives tailored for macOS experimentation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import perf_counter
from typing import Deque, Dict, Optional, Tuple, Any

from robot_assistant.config.defaults import RuntimeConfig, VoiceConfig


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
        self.recognizer = recognizer or SpeechRecognizer(voice_cfg)
        self.wake_detector = wake_detector or WakeWordDetector(voice_cfg)
        self.synthesizer = synthesizer or SpeechSynthesizer(voice_cfg)

    def poll_intent(self) -> Optional[Dict[str, Any]]:
        """Return a runtime intent derived from speech input."""
        if not self.wake_detector.listen():
            return None
        utterance = self.recognizer.transcribe_once()
        if not utterance:
            return None
        return {
            "skill": "assistant",
            "query": utterance.text,
            "confidence": utterance.confidence,
            "source": "voice",
            "timestamps": {"start": utterance.start_ts, "end": utterance.end_ts},
        }

    def enqueue_transcript(self, text: str, confidence: float = 0.92) -> None:
        """Add scripted voice input and trigger wake detection."""
        self.recognizer.enqueue_scripted_input(text, confidence)
        self.wake_detector.trigger()

    def speak(self, text: str) -> None:
        """Forward assistant responses to the synthesizer."""
        self.synthesizer.speak(text)
