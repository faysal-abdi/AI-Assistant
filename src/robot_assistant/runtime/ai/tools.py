"""Tool registration and execution for the assistant pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Dict, Optional

from robot_assistant.config.defaults import ToolingConfig
from robot_assistant.runtime.ai.retrieval import KnowledgeRetriever, RetrievalResult


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


class ToolExecutor:
    """Executes registered tools with timing and error handling."""

    def __init__(self, retriever: KnowledgeRetriever, config: ToolingConfig) -> None:
        self.retriever = retriever
        self.config = config
        self._tools: Dict[str, Tool] = {}
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
            )
        )

    def register(self, tool: Tool) -> None:
        """Add or override a tool definition."""
        self._tools[tool.name] = tool

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

        return ToolResult(
            name=name,
            success=success,
            output=output,
            latency_ms=latency_ms,
            error=error,
        )

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

    @staticmethod
    def _serialize_result(result: RetrievalResult) -> Dict[str, Any]:
        return {
            "doc_id": result.document.doc_id,
            "score": result.score,
            "metadata": result.document.metadata,
            "content": result.document.content,
            "components": result.components,
        }
