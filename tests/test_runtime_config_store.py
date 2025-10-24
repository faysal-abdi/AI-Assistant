from __future__ import annotations

import json
from pathlib import Path

from robot_assistant.config.defaults import RuntimeConfig
from robot_assistant.config.runtime_store import (
    load_runtime_config,
    runtime_config_from_dict,
    runtime_config_to_dict,
    save_runtime_config,
)


def test_round_trip(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.loop_rate_hz = 5.0
    config.tooling.allow_shell_commands = True
    config.memory.history_window = 12
    target = tmp_path / "runtime_config.json"

    save_runtime_config(config, target)
    loaded = load_runtime_config(target)

    assert loaded.loop_rate_hz == config.loop_rate_hz
    assert loaded.tooling.allow_shell_commands is True
    assert loaded.memory.history_window == 12


def test_missing_file_returns_base(tmp_path: Path) -> None:
    base = RuntimeConfig()
    base.loop_rate_hz = 7.5
    path = tmp_path / "missing.json"

    loaded = load_runtime_config(path, base)

    assert loaded.loop_rate_hz == 7.5


def test_dict_conversion_handles_partials() -> None:
    base = RuntimeConfig()
    payload = {
        "loop_rate_hz": 15.0,
        "tooling": {"allow_shell_commands": True, "shell_allowlist": ["pwd", "ls", "whoami"]},
        "memory": {"history_window": 3},
    }

    merged = runtime_config_from_dict(payload, base)
    assert merged.loop_rate_hz == 15.0
    assert merged.tooling.allow_shell_commands is True
    assert merged.tooling.shell_allowlist == ["pwd", "ls", "whoami"]
    assert merged.memory.history_window == 3
    assert merged.voice.tts_voice == base.voice.tts_voice


def test_save_writes_json(tmp_path: Path) -> None:
    config = RuntimeConfig()
    target = tmp_path / "config.json"

    save_runtime_config(config, target)

    parsed = json.loads(target.read_text())
    assert isinstance(parsed, dict)
    assert parsed["memory"]["history_window"] == config.memory.history_window
