#!/usr/bin/env python3
"""Conversational shell for the AI assistant with session memory and telemetry."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from time import sleep
from typing import Dict, Iterable, List, Optional

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


def format_metrics(metadata: Dict[str, object]) -> str:
    lines: List[str] = []
    latency = metadata.get("latency_ms", {})
    if latency:
        budget = ", ".join(f"{stage}={value:.1f}ms" for stage, value in latency.items())
        lines.append(f"latency: {budget}")
    usage = metadata.get("usage", {})
    if usage:
        lines.append(
            "tokens: "
            + ", ".join(
                f"{key}={usage.get(key)}"
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if key in usage
            )
        )
    lines.append(f"model: {metadata.get('model')}")
    tools = metadata.get("tool_results", [])
    if tools:
        serialized = json.dumps(tools, indent=2) if len(tools) <= 3 else json.dumps(tools[:3], indent=2)
        lines.append(f"tools: {serialized}")
    return " | ".join(lines)


def stream_text(text: str, delay: float = 0.0) -> None:
    """Print response text with optional streaming effect."""
    if not text:
        return
    chunks = text.split()
    for idx, chunk in enumerate(chunks):
        end = "\n" if idx == len(chunks) - 1 else " "
        print(chunk, end=end, flush=True)
        if delay:
            sleep(delay)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs",
        nargs="*",
        default=["docs/technical_prototype.md", "docs/architecture.md"],
        help="Knowledge base documents to ingest before the session.",
    )
    parser.add_argument(
        "--persona",
        default="You are a helpful AI copilot named Jarvis.",
        help="Default system instruction/persona.",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream responses word by word for a live typing feel.",
    )
    parser.add_argument(
        "--stream-delay",
        type=float,
        default=0.05,
        help="Delay between streamed words when --stream is set.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Route requests through the fast-path model.",
    )
    args = parser.parse_args()

    runtime = RobotRuntime()
    runtime.assistant.ingest_documents(load_documents(args.docs))

    persona = args.persona
    history: List[Dict[str, str]] = []
    fast_mode = args.fast
    forced_model: Optional[str] = None

    print("--- Assistant shell ---")
    print("Commands: /exit, /clear, /persona <text>, /model <default|fast|offline>, /history")
    print("Type your message and press Enter.")

    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting shell.")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            command = parts[0]
            argument = parts[1] if len(parts) > 1 else ""

            if command == "/exit":
                print("Goodbye.")
                break
            if command == "/clear":
                history.clear()
                print("History cleared.")
                continue
            if command == "/persona":
                persona = argument or persona
                print(f"Persona set to: {persona}")
                continue
            if command == "/model":
                lookup = {
                    "default": None,
                    "fast": "fast",
                    "offline": "offline",
                }
                key = argument.lower()
                if key not in lookup:
                    print("Valid options: default, fast, offline")
                else:
                    forced_model = lookup[key]
                    if forced_model == "fast":
                        fast_mode = True
                    elif forced_model == "offline":
                        fast_mode = False
                    else:
                        fast_mode = args.fast
                    print(f"Model routing updated: {key}")
                continue
            if command == "/history":
                if not history:
                    print("(history empty)")
                else:
                    for turn in history:
                        print(f"{turn['role']}: {turn['content']}")
                continue

            print("Unknown command.")
            continue

        intents = {
            "skill": "assistant",
            "query": user_input,
            "history": history[-8:],
            "instructions": persona,
        }
        if fast_mode:
            intents["fast_path"] = True
        if forced_model == "offline":
            intents["offline_only"] = True
        if forced_model == "fast":
            intents["fast_path"] = True

        state = {"loop_rate_hz": runtime.config.loop_rate_hz, "turn": len(history) // 2 + 1}
        plan = runtime.assistant.handle(intents, state)
        metadata = plan.get("metadata", {})
        response = plan.get("response", "")

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})

        if args.stream:
            stream_text(response, delay=args.stream_delay)
        else:
            wrapped = textwrap.fill(response, width=88)
            print(f"Assistant> {wrapped}")

        if metadata:
            print(f"  ▸ {format_metrics(metadata)}")


if __name__ == "__main__":
    main()
