#!/usr/bin/env python3
"""Interactive CLI harness to exercise the voice orchestrator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from robot_assistant.runtime.ai.retrieval import Document
from robot_assistant.runtime.system import RobotRuntime


def load_documents(paths: Iterable[str]) -> List[Document]:
    docs: List[Document] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        docs.append(
            Document(
                doc_id=path.name,
                content=path.read_text(),
                metadata={"title": path.stem, "source_path": str(path)},
            )
        )
    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs",
        nargs="*",
        default=["docs/technical_prototype.md", "docs/architecture.md"],
        help="Knowledge base documents to ingest before the session.",
    )
    parser.add_argument(
        "--wake-word",
        default="jarvis",
        help="Wake word to display in the prompt (informational only).",
    )
    parser.add_argument(
        "--exit-cmd",
        default="/exit",
        help="Command to terminate the demo.",
    )
    args = parser.parse_args()

    runtime = RobotRuntime()
    runtime.assistant.ingest_documents(load_documents(args.docs))

    print("--- Voice demo ---")
    print(f"Type utterances to simulate speech, prefixed by wake word '{args.wake_word}'.")
    print(f"Use '{args.exit_cmd}' to stop.")

    while True:
        try:
            raw_input_text = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not raw_input_text:
            continue

        if raw_input_text == args.exit_cmd:
            print("Session terminated.")
            break

        runtime.voice.enqueue_transcript(raw_input_text)
        artifacts = runtime.step()
        plan = artifacts.get("plan", {})
        response = plan.get("response")
        if response:
            print(f"Assistant> {response[:500]}")
        else:
            print("Assistant> (no response)")


if __name__ == "__main__":
    main()
