"""System runtime coordinating the robot assistant subsystems."""

from typing import Optional, Dict, Any

from robot_assistant.config.defaults import RuntimeConfig
from robot_assistant.hardware.interfaces import HardwareSuite
from robot_assistant.perception.pipeline import PerceptionPipeline
from robot_assistant.planning.planner import Planner
from robot_assistant.control.controller import Controller
from robot_assistant.skills.registry import SkillRegistry
from robot_assistant.interface.protocol import InteractionProtocol
from robot_assistant.runtime.ai import AssistantPipeline
from robot_assistant.runtime.voice import VoiceOrchestrator
from robot_assistant.runtime.memory import ConversationMemory
from robot_assistant.runtime.safety import SafetyManager


class RobotRuntime:
    """High-level orchestrator for the robot assistant."""

    def __init__(
        self,
        config: Optional[RuntimeConfig] = None,
        hardware: Optional[HardwareSuite] = None,
        perception: Optional[PerceptionPipeline] = None,
        planner: Optional[Planner] = None,
        controller: Optional[Controller] = None,
        skills: Optional[SkillRegistry] = None,
        interface: Optional[InteractionProtocol] = None,
        assistant: Optional[AssistantPipeline] = None,
        voice: Optional[VoiceOrchestrator] = None,
        memory: Optional[ConversationMemory] = None,
        safety: Optional[SafetyManager] = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.hardware = hardware or HardwareSuite()
        self.perception = perception or PerceptionPipeline(self.hardware)
        self.planner = planner or Planner(self.config)
        self.controller = controller or Controller(self.hardware, self.config)
        self.skills = skills or SkillRegistry(self.planner, self.controller)
        self.voice = voice or VoiceOrchestrator(self.config)
        self.safety = safety or SafetyManager(self.config.safety)
        self.memory = memory or ConversationMemory(self.config.memory)
        self.interface = interface or InteractionProtocol(self.voice)
        if interface is not None and self.voice:
            self.interface.attach_voice(self.voice)
        self.assistant = assistant or AssistantPipeline(
            self.config,
            memory=self.memory,
            safety=self.safety,
        )
        self.skills.register("assistant", self.assistant.handle)

    def step(self) -> Dict[str, Any]:
        """Run one perception-planning-control loop and return artifacts."""
        observations = self.hardware.read_sensors()
        state = self.perception.process(observations)
        intents = self.interface.poll_intents()
        plan = self.skills.dispatch(intents, state)
        control_commands = self.controller.execute(plan, state)
        self.hardware.apply_commands(control_commands)
        self.interface.push_feedback(state, control_commands)
        return {"state": state, "plan": plan, "commands": control_commands}

    def shutdown(self) -> None:
        """Gracefully stop the runtime."""
        self.interface.close()
        self.hardware.shutdown()
        if hasattr(self.voice, "shutdown"):
            self.voice.shutdown()
        self.memory.close()
