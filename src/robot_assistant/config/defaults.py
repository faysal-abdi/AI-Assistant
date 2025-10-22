"""Default configuration definitions for the robot assistant."""

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class ModelRoutingConfig:
    """Configuration describing model routing policies."""

    default_model: str = "gpt-4.1-mini"
    fast_model: str = "gpt-4o-mini"
    offline_model: str = "mixtral-8x7b"
    temperature: float = 0.2
    max_output_tokens: int = 1024


@dataclass
class RetrievalConfig:
    """Baseline retrieval configuration."""

    top_k: int = 4
    lexical_weight: float = 0.35
    vector_weight: float = 0.65
    min_score: float = 0.12


@dataclass
class ToolingConfig:
    """Tool orchestration defaults."""

    auto_search: bool = True
    max_tool_time_ms: int = 600
    allow_control_commands: bool = False
    allow_shell_commands: bool = False
    shell_allowlist: List[str] = field(default_factory=lambda: ["pwd", "ls"])
    file_search_roots: List[str] = field(default_factory=lambda: ["docs"])
    enable_calendar_tools: bool = False
    enable_email_tools: bool = False
    enable_home_automation: bool = False


@dataclass
class MemoryConfig:
    """Persistent memory configuration."""

    db_path: str = "var/memory.db"
    history_window: int = 8


@dataclass
class VoiceConfig:
    """Voice interface configuration defaults."""

    wake_word: str = "jarvis"
    use_wake_word: bool = True
    transcription_provider: str = "macos_speech"
    transcription_language: str = "en-US"
    tts_voice: str = "Alex"
    enable_tts: bool = True


@dataclass
class SafetyConfig:
    """Safety and privilege configuration."""

    default_privilege: str = "informational"
    audit_log_path: str = "var/safety.log"
    pause_on_start: bool = False


@dataclass
class RuntimeConfig:
    """Base configuration for the runtime and downstream subsystems."""

    loop_rate_hz: float = 10.0
    perception: Dict[str, Any] = field(default_factory=lambda: {"latency_budget_ms": 50})
    planning: Dict[str, Any] = field(default_factory=lambda: {"horizon_s": 5.0})
    control: Dict[str, Any] = field(default_factory=lambda: {"safety_margin": 0.1})
    models: ModelRoutingConfig = field(default_factory=ModelRoutingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    tooling: ToolingConfig = field(default_factory=ToolingConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
