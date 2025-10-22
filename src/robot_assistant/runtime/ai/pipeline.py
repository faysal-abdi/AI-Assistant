"""Assistant pipeline orchestrating retrieval, tool usage, and model calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from robot_assistant.config.defaults import RuntimeConfig
from robot_assistant.runtime.memory import ConversationMemory
from robot_assistant.runtime.safety import SafetyManager

from .models import ModelGateway, ModelResponse
from .retrieval import Document, EmbeddingProvider, InMemoryVectorStore, KnowledgeRetriever
from .telemetry import LatencyProbe
from .tools import ToolExecutor, ToolResult


@dataclass
class AssistantOutput:
    """Structured output from the assistant pipeline."""

    response: str
    model: str
    usage: Dict[str, int]
    tool_results: List[ToolResult]
    latency_breakdown_ms: Dict[str, float]


class AssistantPipeline:
    """Coordinates retrieval-augmented generation for the assistant."""

    def __init__(
        self,
        config: RuntimeConfig,
        model_gateway: Optional[ModelGateway] = None,
        retriever: Optional[KnowledgeRetriever] = None,
        tools: Optional[ToolExecutor] = None,
        telemetry: Optional[LatencyProbe] = None,
        memory: Optional[ConversationMemory] = None,
        safety: Optional[SafetyManager] = None,
    ) -> None:
        self.config = config
        self.telemetry = telemetry or LatencyProbe()
        self.model_gateway = model_gateway or ModelGateway(config)
        if retriever is None:
            embedder = EmbeddingProvider()
            vector_store = InMemoryVectorStore(embedder)
            retriever = KnowledgeRetriever(vector_store, config.retrieval)
        self.retriever = retriever
        self.safety = safety or SafetyManager(config.safety)
        self.tools = tools or ToolExecutor(self.retriever, config.tooling, safety=self.safety)
        self.memory = memory

    def ingest_documents(self, documents: Iterable[Document]) -> None:
        """Add domain documents to the retrieval store."""
        self.retriever.ingest(documents)

    def handle(self, intents: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Process an intent payload and produce an assistant plan."""
        tool_results: List[ToolResult] = []
        latency_summary: Dict[str, float] = {}
        self.telemetry.flush()

        session_id = intents.get("session_id", "default")
        query = intents.get("query") or intents.get("text") or intents.get("message")

        context_packages: List[Dict[str, Any]] = []
        if self.config.tooling.auto_search and query:
            with self.telemetry.track("retrieval"):
                result = self.tools.run(
                    "search_docs",
                    params={"query": query, "limit": self.config.retrieval.top_k},
                    state=state,
                )
            tool_results.append(result)
            if result.success:
                context_packages.extend(result.output.get("matches", []))

        history = intents.get("history")
        if history is None and self.memory:
            history = self.memory.get_recent_turns(session_id, self.config.memory.history_window)
        if history is None:
            history = []

        with self.telemetry.track("prompt_build"):
            prompt = self._build_prompt(query, intents, context_packages, state, history)

        with self.telemetry.track("generation"):
            response = self.model_gateway.generate(prompt, intents)

        for measurement in self.telemetry.flush():
            latency_summary[measurement.stage] = latency_summary.get(
                measurement.stage, 0.0
            ) + measurement.duration_ms

        assistant_output = AssistantOutput(
            response=response.text,
            model=response.model,
            usage=response.usage,
            tool_results=tool_results,
            latency_breakdown_ms=latency_summary,
        )

        payload = {
            "type": "assistant",
            "response": assistant_output.response,
            "metadata": {
                "model": assistant_output.model,
                "usage": assistant_output.usage,
                "latency_ms": assistant_output.latency_breakdown_ms,
                "tool_results": [self._serialize_tool_result(result) for result in assistant_output.tool_results],
            },
        }

        if self.memory:
            if query:
                self.memory.append_turn(
                    session_id,
                    "user",
                    query,
                    metadata=self._coerce_metadata(
                        {
                            "source": intents.get("source", "text"),
                            "confidence": str(intents.get("confidence", "")),
                        }
                    ),
                )
            if assistant_output.response:
                self.memory.append_turn(
                    session_id,
                    "assistant",
                    assistant_output.response,
                    metadata={"model": assistant_output.model},
                )
            preferences = intents.get("preferences", {})
            for key, value in preferences.items():
                self.memory.set_preference(session_id, key, str(value))

        return payload

    def _build_prompt(
        self,
        query: Optional[str],
        intents: Dict[str, Any],
        context_packages: List[Dict[str, Any]],
        state: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> str:
        """Construct the model prompt with retrieved context."""
        instructions = intents.get("instructions") or "You are a helpful AI assistant."
        sections = [instructions]

        if history:
            sections.append("Conversation history (most recent first):")
            for turn in history[-5:]:
                speaker = turn.get("role", "user")
                content = turn.get("content", "")
                sections.append(f"{speaker}: {content}")

        if context_packages:
            sections.append("Context documents:")
            for idx, package in enumerate(context_packages, 1):
                title = package.get("metadata", {}).get("title", f"Doc {idx}")
                sections.append(f"- [{package.get('doc_id')}] {title}: {package.get('content')}")

        if state:
            sections.append(f"State summary: {state}")

        user_query = query or intents.get("goal") or "Provide an update."
        sections.append(f"User request: {user_query}")

        return "\n\n".join(sections)

    @staticmethod
    def _serialize_tool_result(result: ToolResult) -> Dict[str, Any]:
        return {
            "name": result.name,
            "success": result.success,
            "latency_ms": result.latency_ms,
            "error": result.error,
            "output": result.output,
        }

    @staticmethod
    def _coerce_metadata(metadata: Dict[str, Any]) -> Dict[str, str]:
        return {key: str(value) for key, value in metadata.items() if value not in (None, "")}
