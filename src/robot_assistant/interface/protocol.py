"""Interaction protocol handling intents and feedback."""

from typing import Any, Dict, Optional

from robot_assistant.runtime.voice import VoiceOrchestrator


class InteractionProtocol:
    """Placeholder interface for capturing intents and returning feedback."""

    def __init__(self, voice: Optional[VoiceOrchestrator] = None) -> None:
        self.voice = voice
        self._fallback_intent: Dict[str, Any] = {"skill": "default", "args": []}

    def attach_voice(self, voice: VoiceOrchestrator) -> None:
        """Attach a voice orchestrator for intent sourcing."""
        self.voice = voice

    def poll_intents(self) -> Dict[str, Any]:
        """Obtain intents from users or upstream systems."""
        if self.voice:
            voice_intent = self.voice.poll_intent()
            if voice_intent:
                return voice_intent
        return dict(self._fallback_intent)

    def push_feedback(self, state: Dict[str, Any], commands: Dict[str, Any]) -> None:
        """Publish state and command feedback."""
        if self.voice and "plan" in commands:
            plan_payload = commands["plan"]
            if isinstance(plan_payload, dict):
                response_text = plan_payload.get("response")
                if response_text:
                    self.voice.speak(response_text)

    def close(self) -> None:
        """Close interface resources."""
