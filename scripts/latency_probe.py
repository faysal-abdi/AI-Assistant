#!/usr/bin/env python3
"""Simple harness to profile assistant pipeline latency."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter
from typing import Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from robot_assistant.runtime.ai.retrieval import Document
from robot_assistant.runtime.system import RobotRuntime


def load_documents(paths: Iterable[str]) -> List[Document]:
    documents: List[Document] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        documents.append(
            Document(
                doc_id=path.name,
                content=path.read_text(),
                metadata={"title": path.stem, "source_path": str(path)},
            )
        )
    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs",
        nargs="*",
        default=["docs/technical_prototype.md", "docs/architecture.md"],
        help="Paths to markdown documents to ingest for retrieval.",
    )
    parser.add_argument(
        "--query",
        default="How does the assistant orchestrate retrieval and generation?",
        help="Example user query to send to the assistant.",
    )
    parser.add_argument(
        "--fast-path",
        action="store_true",
        help="Route the request through the fast-path model configuration.",
    )
    args = parser.parse_args()

    runtime = RobotRuntime()
    runtime.assistant.ingest_documents(load_documents(args.docs))

    intents = {
        "skill": "assistant",
        "query": args.query,
        "fast_path": args.fast_path,
    }
    state = {"loop_rate_hz": runtime.config.loop_rate_hz}

    start = perf_counter()
    plan = runtime.assistant.handle(intents, state)
    total_ms = (perf_counter() - start) * 1000.0

    metadata = plan.get("metadata", {})
    print(f"Total latency: {total_ms:.2f} ms")

    latency_breakdown = metadata.get("latency_ms", {})
    if latency_breakdown:
        print("Stage breakdown:")
        for stage, value in latency_breakdown.items():
            print(f"  - {stage}: {value:.2f} ms")

    print(f"Model: {metadata.get('model')}")
    usage = metadata.get("usage", {})
    if usage:
        print(f"Token usage: prompt={usage.get('prompt_tokens')} completion={usage.get('completion_tokens')} total={usage.get('total_tokens')}")

    tool_results = metadata.get("tool_results", [])
    if tool_results:
        print("Tool results:")
        for result in tool_results:
            status = "ok" if result["success"] else f"error: {result.get('error')}"
            print(f"  - {result['name']} ({result['latency_ms']:.2f} ms): {status}")

    response_preview = plan.get("response", "")
    if response_preview:
        print("\nResponse preview:")
        print(response_preview[:400])


if __name__ == "__main__":
    main()
