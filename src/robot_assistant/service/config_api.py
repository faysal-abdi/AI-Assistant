"""FastAPI service exposing runtime configuration and diagnostics endpoints."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Body, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from robot_assistant.config.defaults import RuntimeConfig
from robot_assistant.config.runtime_store import (
    CONFIG_PATH,
    load_runtime_config,
    runtime_config_from_dict,
    runtime_config_to_dict,
    save_runtime_config,
)
from robot_assistant.runtime.memory import ConversationMemory


def _default_cors_origins() -> list[str]:
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


app = FastAPI(title="Robot Assistant Config Service", version="0.1.0")

cors_origins = os.environ.get("ROBOT_ASSISTANT_CONFIG_CORS")
origins = (
    [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
    if cors_origins
    else _default_cors_origins()
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_TOKEN = os.environ.get("ROBOT_ASSISTANT_CONFIG_TOKEN")
_CONFIG_CACHE: RuntimeConfig = load_runtime_config()


async def verify_token(x_api_token: Optional[str] = Header(default=None)) -> None:
    """Simple header token check; bypassed when unset."""
    if CONFIG_TOKEN and x_api_token != CONFIG_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api token")


def _get_config() -> RuntimeConfig:
    return _CONFIG_CACHE


def _set_config(config: RuntimeConfig) -> None:
    global _CONFIG_CACHE  # noqa: PLW0603 - module level cache
    _CONFIG_CACHE = config
    save_runtime_config(config, CONFIG_PATH)


@app.get("/health", dependencies=[Depends(verify_token)])
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/config", dependencies=[Depends(verify_token)])
async def get_config() -> Dict[str, Any]:
    """Return the complete runtime configuration."""
    return runtime_config_to_dict(_get_config())


@app.put("/config", dependencies=[Depends(verify_token)])
async def replace_config(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Replace the entire runtime configuration."""
    try:
        new_config = runtime_config_from_dict(payload, RuntimeConfig())
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _set_config(new_config)
    return runtime_config_to_dict(new_config)


@app.patch("/config/{section}", dependencies=[Depends(verify_token)])
async def patch_section(section: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Patch a specific configuration section (models, tooling, voice, safety, memory, retrieval)."""
    config = _get_config()
    config_dict = runtime_config_to_dict(config)
    if section not in config_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown section")
    section_data = config_dict[section]
    if not isinstance(section_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="section is not patchable via dict merge",
        )
    updated = copy.deepcopy(config_dict)
    updated_section = updated[section]
    updated_section.update(payload)
    try:
        new_config = runtime_config_from_dict(updated, RuntimeConfig())
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _set_config(new_config)
    return runtime_config_to_dict(new_config)[section]


@app.get("/sessions/{session_id}/preferences", dependencies=[Depends(verify_token)])
async def get_preferences(session_id: str) -> Dict[str, Any]:
    """Return stored preferences for a session."""
    memory = ConversationMemory(_get_config().memory)
    try:
        prefs = memory.get_preferences(session_id)
    finally:
        memory.close()
    return {"session_id": session_id, "preferences": prefs}


class PreferenceUpdate(BaseModel):
    value: str


@app.put("/sessions/{session_id}/preferences/{key}", dependencies=[Depends(verify_token)])
async def set_preference(session_id: str, key: str, update: PreferenceUpdate) -> Dict[str, Any]:
    """Persist a preference value for the given session."""
    memory = ConversationMemory(_get_config().memory)
    try:
        memory.set_preference(session_id, key, update.value)
        prefs = memory.get_preferences(session_id)
    finally:
        memory.close()
    return {"session_id": session_id, "preferences": prefs}


@app.get("/safety/log", dependencies=[Depends(verify_token)])
async def get_safety_log(limit: int = 200) -> Dict[str, Any]:
    """Return recent entries from the safety audit log."""
    path = Path(_get_config().safety.audit_log_path)
    if not path.exists():
        return {"entries": []}
    lines = path.read_text(encoding="utf-8").splitlines()
    tail = lines[-limit:] if limit > 0 else lines
    entries = []
    for line in tail:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"raw": line, "error": "invalid json"})
    return {"entries": entries}


@app.get("/tooling/consent", dependencies=[Depends(verify_token)])
async def get_tooling_metadata() -> Dict[str, Any]:
    """Describe tooling configuration with consent requirements."""
    tooling = _get_config().tooling
    consent_matrix = [
        {"tool": "search_docs", "requires_consent": False, "enabled": True},
        {"tool": "get_runtime_state", "requires_consent": False, "enabled": True},
        {"tool": "issue_command", "requires_consent": True, "enabled": tooling.allow_control_commands},
        {"tool": "search_files", "requires_consent": False, "enabled": True},
        {
            "tool": "run_shell_command",
            "requires_consent": True,
            "enabled": tooling.allow_shell_commands,
        },
        {
            "tool": "create_calendar_event",
            "requires_consent": True,
            "enabled": tooling.enable_calendar_tools,
        },
        {
            "tool": "summarize_inbox",
            "requires_consent": True,
            "enabled": tooling.enable_email_tools,
        },
        {
            "tool": "run_home_automation",
            "requires_consent": True,
            "enabled": tooling.enable_home_automation,
        },
    ]
    return {
        "auto_search": tooling.auto_search,
        "max_tool_time_ms": tooling.max_tool_time_ms,
        "shell_allowlist": tooling.shell_allowlist,
        "file_search_roots": tooling.file_search_roots,
        "consent_matrix": consent_matrix,
    }
