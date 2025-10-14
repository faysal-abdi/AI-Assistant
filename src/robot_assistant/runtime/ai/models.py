"""Model selection and invocation utilities for the assistant pipeline."""

from __future__ import annotations

import random
import string
from dataclasses import dataclass
from time import perf_counter
from typing import Dict, Optional, Any

from robot_assistant.config.defaults import RuntimeConfig


@dataclass
class ModelSpec:
    """Represents a single model option."""

    name: str
    provider: str
    latency_budget_ms: int
    max_output_tokens: int
    temperature: float
    tier: str = "primary"
    fallback: Optional[str] = None


@dataclass
class ModelResponse:
    """Normalized model response for downstream consumption."""

    text: str
    model: str
    usage: Dict[str, int]
    latency_ms: float
    finish_reason: str = "stop"


class ModelGateway:
    """Routes generation requests to the appropriate language model."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        # Hard-coded catalog for prototype; swap with provider registry in production.
        self._catalog: Dict[str, ModelSpec] = {
            "gpt-4.1-mini": ModelSpec(
                name="gpt-4.1-mini",
                provider="openai",
                latency_budget_ms=1400,
                max_output_tokens=config.models.max_output_tokens,
                temperature=config.models.temperature,
                tier="primary",
                fallback="gpt-4o-mini",
            ),
            "gpt-4o-mini": ModelSpec(
                name="gpt-4o-mini",
                provider="openai",
                latency_budget_ms=650,
                max_output_tokens=512,
                temperature=0.3,
                tier="fast",
                fallback=None,
            ),
            "mixtral-8x7b": ModelSpec(
                name="mixtral-8x7b",
                provider="vllm",
                latency_budget_ms=2200,
                max_output_tokens=768,
                temperature=0.25,
                tier="offline",
                fallback="gpt-4o-mini",
            ),
        }

    def register_model(self, spec: ModelSpec) -> None:
        """Register or override a model specification."""
        self._catalog[spec.name] = spec

    def get_spec(self, name: str) -> Optional[ModelSpec]:
        """Return the model spec if available."""
        return self._catalog.get(name)

    def select_model(self, intents: Dict[str, Any]) -> ModelSpec:
        """Choose a model based on intent metadata and config policy."""
        target = intents.get("model")
        if target and target in self._catalog:
            return self._catalog[target]

        if intents.get("fast_path", False):
            spec = self.get_spec(self.config.models.fast_model)
            if spec:
                return spec

        if intents.get("offline_only", False):
            spec = self.get_spec(self.config.models.offline_model)
            if spec:
                return spec

        spec = self.get_spec(self.config.models.default_model)
        if spec:
            return spec

        # Fallback to any available model.
        return next(iter(self._catalog.values()))

    def generate(self, prompt: str, intents: Dict[str, Any]) -> ModelResponse:
        """Call the selected model (simulated for prototype)."""
        spec = self.select_model(intents)
        start_time = perf_counter()
        # Prototype simulates latency + token usage; replace with real API call.
        generated = self._simulate_response(prompt, spec)
        latency_ms = (perf_counter() - start_time) * 1000.0
        usage = {
            "prompt_tokens": self._estimate_tokens(prompt),
            "completion_tokens": self._estimate_tokens(generated),
            "total_tokens": 0,
        }
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        return ModelResponse(
            text=generated,
            model=spec.name,
            usage=usage,
            latency_ms=latency_ms,
        )

    def _simulate_response(self, prompt: str, spec: ModelSpec) -> str:
        """Prototype helper that fabricates a deterministic completion."""
        seed = abs(hash(prompt + spec.name)) % (2**32)
        random.seed(seed)
        tokens = prompt.split()
        projected_len = min(len(tokens) // 2 + 32, spec.max_output_tokens)
        synthetic_tokens = []
        for _ in range(projected_len):
            if tokens and random.random() > 0.6:
                synthetic_tokens.append(random.choice(tokens))
            else:
                synthetic_tokens.append(self._random_token())
        text = " ".join(synthetic_tokens)
        return text[: spec.max_output_tokens * 5]

    @staticmethod
    def _random_token(length: int = 5) -> str:
        return "".join(random.choice(string.ascii_lowercase) for _ in range(length))

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation using whitespace split."""
        return max(1, len(text.strip().split()))
