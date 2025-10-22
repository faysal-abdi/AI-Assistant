"""Voice interface helpers for speech recognition, wake words, and synthesis."""

from .orchestrator import (
    RecognizedUtterance,
    SpeechRecognizer,
    WakeWordDetector,
    SpeechSynthesizer,
    VoiceOrchestrator,
    HAS_MAC_SPEECH,
)

__all__ = [
    "RecognizedUtterance",
    "SpeechRecognizer",
    "WakeWordDetector",
    "SpeechSynthesizer",
    "VoiceOrchestrator",
]

if HAS_MAC_SPEECH:  # pragma: no cover - optional
    from .orchestrator import MacSpeechRecognizer, MacSpeechSynthesizer

    __all__.extend(["MacSpeechRecognizer", "MacSpeechSynthesizer"])
