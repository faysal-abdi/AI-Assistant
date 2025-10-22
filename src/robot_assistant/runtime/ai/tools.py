"""Tool registration and execution for the assistant pipeline."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional

from robot_assistant.config.defaults import ToolingConfig
from robot_assistant.runtime.ai.retrieval import KnowledgeRetriever, RetrievalResult
from robot_assistant.runtime.safety import SafetyManager


ToolHandler = Callable[["ToolContext"], Any]


@dataclass
class ToolContext:
    """Context object passed into tool handlers."""

    params: Dict[str, Any]
    state_snapshot: Dict[str, Any]
    retriever: Optional[KnowledgeRetriever] = None


@dataclass
class ToolResult:
    """Represents the outcome of a tool execution."""

    name: str
    success: bool
    output: Any
    latency_ms: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Tool:
    """Metadata wrapper for a registered tool."""

    name: str
    description: str
    handler: Callable[[ToolContext], Any]
    timeout_ms: int = 500
    expected_latency_ms: int = 200
    requires_consent: bool = False
    category: str = "general"


class ConsentRegistry:
    """Tracks user consent for privileged tool execution."""

    def __init__(self) -> None:
        self._consent: Dict[str, bool] = {}

    def grant(self, tool_name: str) -> None:
        self._consent[tool_name] = True

    def revoke(self, tool_name: str) -> None:
        if tool_name in self._consent:
            del self._consent[tool_name]

    def has(self, tool_name: str) -> bool:
        return self._consent.get(tool_name, False)


class ToolExecutor:
    """Executes registered tools with timing, safety checks, and consent tracking."""

    def __init__(
        self,
        retriever: KnowledgeRetriever,
        config: ToolingConfig,
        safety: Optional[SafetyManager] = None,
    ) -> None:
        self.retriever = retriever
        self.config = config
        self._tools: Dict[str, Tool] = {}
        self._consent = ConsentRegistry()
        self.safety = safety
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Install prototype default tools."""
        self.register(
            Tool(
                name="search_docs",
                description="Retrieve knowledge base passages relevant to a textual query.",
                handler=self._search_docs,
                expected_latency_ms=180,
            )
        )
        self.register(
            Tool(
                name="get_runtime_state",
                description="Return a snapshot of the latest state estimation.",
                handler=self._get_runtime_state,
                expected_latency_ms=40,
            )
        )
        self.register(
            Tool(
                name="issue_command",
                description="Queue a structured actuator command via the control stack.",
                handler=self._issue_command,
                expected_latency_ms=120,
                requires_consent=True,
                category="control",
            )
        )
        self.register(
            Tool(
                name="search_files",
                description="Search local files within allowlisted directories.",
                handler=self._search_files,
                expected_latency_ms=160,
            )
        )
        if self.config.allow_shell_commands:
            self.register(
                Tool(
                    name="run_shell_command",
                    description="Execute an allowlisted shell command with consent.",
                    handler=self._run_shell_command,
                    expected_latency_ms=220,
                    requires_consent=True,
                    category="system",
                )
            )
        if self.config.enable_calendar_tools:
            self.register(
                Tool(
                    name="create_calendar_event",
                    description="Create a calendar event via the host calendar APIs.",
                    handler=self._create_calendar_event,
                    expected_latency_ms=250,
                    requires_consent=True,
                    category="calendar",
                )
            )
        if self.config.enable_email_tools:
            self.register(
                Tool(
                    name="summarize_inbox",
                    description="Summarize recent email messages.",
                    handler=self._summarize_inbox,
                    expected_latency_ms=320,
                    requires_consent=True,
                    category="email",
                )
            )
        if self.config.enable_home_automation:
            self.register(
                Tool(
                    name="run_home_automation",
                    description="Trigger a HomeKit / smart home action.",
                    handler=self._run_home_automation,
                    expected_latency_ms=280,
                    requires_consent=True,
                    category="home_automation",
                )
            )

    def register(self, tool: Tool) -> None:
        """Add or override a tool definition."""
        self._tools[tool.name] = tool

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return metadata about registered tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "requires_consent": tool.requires_consent,
                "category": tool.category,
                "consent_granted": self._consent.has(tool.name),
            }
            for tool in self._tools.values()
        ]

    def grant_consent(self, name: str) -> None:
        """Grant consent for a privileged tool."""
        self._consent.grant(name)

    def revoke_consent(self, name: str) -> None:
        """Revoke consent for a privileged tool."""
        self._consent.revoke(name)

    def run(self, name: str, params: Dict[str, Any], state: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                name=name,
                success=False,
                output=None,
                latency_ms=0.0,
                error=f"tool '{name}' not registered",
            )

        if tool.requires_consent and not self._consent.has(tool.name):
            return ToolResult(
                name=name,
                success=False,
                output=None,
                latency_ms=0.0,
                error="consent required",
                metadata={"requires_consent": True},
            )

        if self.safety:
            status = self.safety.is_allowed(tool.category)
            if not status.allowed:
                blocked_output = {"status": "blocked", "reason": status.reason}
                self.safety.log_tool(
                    tool.name,
                    tool.category,
                    "blocked",
                    {"reason": status.reason},
                )
                return ToolResult(
                    name=name,
                    success=False,
                    output=blocked_output,
                    latency_ms=0.0,
                    error=status.reason,
                    metadata={
                        "requires_consent": tool.requires_consent,
                        "category": tool.category,
                        "blocked": True,
                        "reason": status.reason,
                    },
                )

        context = ToolContext(params=params, state_snapshot=state, retriever=self.retriever)
        start_time = perf_counter()
        try:
            output = tool.handler(context)
            success = True
            error: Optional[str] = None
        except Exception as exc:  # pragma: no cover - diagnostic path
            output = None
            success = False
            error = str(exc)
        latency_ms = (perf_counter() - start_time) * 1000.0

        result = ToolResult(
            name=name,
            success=success,
            output=output,
            latency_ms=latency_ms,
            error=error,
            metadata={"requires_consent": tool.requires_consent, "category": tool.category},
        )
        if self.safety:
            outcome = "success" if success else "error"
            self.safety.log_tool(
                tool.name,
                tool.category,
                outcome,
                {
                    "latency_ms": f"{latency_ms:.2f}",
                    "requires_consent": str(tool.requires_consent),
                },
            )
        return result

    # Built-in tool handlers -------------------------------------------------
    def _search_docs(self, context: ToolContext) -> Dict[str, Any]:
        query = context.params.get("query")
        limit = int(context.params.get("limit", 4))
        if not query:
            return {"matches": [], "reason": "empty query"}
        if not context.retriever:
            return {"matches": [], "reason": "retriever unavailable"}
        results = context.retriever.retrieve(query, top_k=limit)
        return {"matches": [self._serialize_result(result) for result in results]}

    def _get_runtime_state(self, context: ToolContext) -> Dict[str, Any]:
        return {"state": context.state_snapshot}

    def _issue_command(self, context: ToolContext) -> Dict[str, Any]:
        if not self.config.allow_control_commands:
            return {"status": "rejected", "reason": "control commands disabled"}
        command = context.params.get("command")
        return {"status": "accepted", "command": command}

    def _run_shell_command(self, context: ToolContext) -> Dict[str, Any]:
        if not self.config.allow_shell_commands:
            return {"status": "rejected", "reason": "shell commands disabled"}
        raw_command = context.params.get("command")
        if not raw_command:
            return {"status": "rejected", "reason": "missing command"}
        if isinstance(raw_command, str):
            argv = shlex.split(raw_command)
        else:
            argv = list(raw_command)
        if not argv:
            return {"status": "rejected", "reason": "empty command"}
        if argv[0] not in self.config.shell_allowlist:
            return {"status": "rejected", "reason": "command not in allowlist"}
        try:
            process = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(1.0, self.config.max_tool_time_ms / 1000.0),
            )
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        stdout = process.stdout[:2048]
        stderr = process.stderr[:2048]
        return {
            "status": "ok",
            "command": argv,
            "returncode": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    def _search_files(self, context: ToolContext) -> Dict[str, Any]:
        query = context.params.get("query", "").lower()
        limit = int(context.params.get("limit", 10))
        patterns_param = context.params.get("patterns") or ["*"]
        patterns: List[str] = patterns_param if isinstance(patterns_param, list) else [patterns_param]
        results: List[Dict[str, Any]] = []
        for root in self.config.file_search_roots:
            root_path = Path(root).expanduser()
            if not root_path.exists():
                continue
            for pattern in patterns:
                for path in root_path.rglob(pattern):
                    if not path.is_file():
                        continue
                    if query and query not in path.name.lower():
                        continue
                    stat = path.stat()
                    results.append(
                        {
                            "path": str(path),
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                        }
                    )
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        return {"matches": results, "limit": limit, "query": query}

    def _create_calendar_event(self, context: ToolContext) -> Dict[str, Any]:
        if not self.config.enable_calendar_tools:
            return {"status": "rejected", "reason": "calendar tools disabled"}
        event = {
            "title": context.params.get("title", "Untitled Event"),
            "start": context.params.get("start"),
            "end": context.params.get("end"),
            "location": context.params.get("location"),
            "notes": context.params.get("notes"),
            "attendees": context.params.get("attendees", []),
        }
        # Placeholder integration: queue event for manual review.
        return {
            "status": "queued",
            "event": event,
            "integration": "EventKit (pending implementation)",
        }

    def _summarize_inbox(self, context: ToolContext) -> Dict[str, Any]:
        if not self.config.enable_email_tools:
            return {"status": "rejected", "reason": "email tools disabled"}
        limit = int(context.params.get("limit", 5))
        # Placeholder summarization output. Real integration would call MailKit.
        fake_summary = [
            {
                "from": "alice@example.com",
                "subject": "Project status update",
                "preview": "Review the latest sprint burndown ...",
            },
            {
                "from": "ops@example.com",
                "subject": "Weekly system report",
                "preview": "No incidents detected in the last 7 days.",
            },
        ][:limit]
        return {
            "status": "ok",
            "messages": fake_summary,
            "note": "MailKit integration pending; returning synthesized summary.",
        }

    def _run_home_automation(self, context: ToolContext) -> Dict[str, Any]:
        if not self.config.enable_home_automation:
            return {"status": "rejected", "reason": "home automation disabled"}
        action = context.params.get("action", "status")
        device = context.params.get("device")
        # Placeholder for HomeKit invocation.
        return {
            "status": "queued",
            "action": action,
            "device": device,
            "note": "HomeKit integration pending implementation.",
        }

    @staticmethod
    def _serialize_result(result: RetrievalResult) -> Dict[str, Any]:
        return {
            "doc_id": result.document.doc_id,
            "score": result.score,
            "metadata": result.document.metadata,
            "content": result.document.content,
            "components": result.components,
        }
