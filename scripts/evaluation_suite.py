#!/usr/bin/env python3
"""Continuous evaluation harness for text, voice, and command scenarios."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from robot_assistant.config.defaults import RuntimeConfig
from robot_assistant.runtime.ai.retrieval import Document
from robot_assistant.runtime.system import RobotRuntime


TEXT_SCENARIOS = [
    {
        "name": "retrieval_overview",
        "query": "Summarize the technical prototype architecture document.",
    },
    {
        "name": "tooling_question",
        "query": "Which tools are available to the assistant right now?",
    },
    {
        "name": "safety_modes",
        "query": "Describe the safety and privilege tiers configured.",
    },
]

VOICE_SCENARIOS = [
    {
        "name": "status_check",
        "spoken": "Jarvis give me a quick status update.",
        "expected": "Jarvis give me a quick status update.",
    },
    {
        "name": "tool_request",
        "spoken": "Jarvis search the knowledge base for memory features.",
        "expected": "Jarvis search the knowledge base for memory features.",
    },
]

COMMAND_SCENARIOS = [
    {"name": "no_consent", "description": "issue_command without consent"},
    {"name": "paused", "description": "issue_command with consent while paused"},
    {"name": "authorized", "description": "issue_command with consent and command privilege"},
]


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


def total_latency(metadata: Dict[str, Dict[str, float]]) -> float:
    latency = metadata.get("latency_ms", {})
    return float(sum(latency.values()))


def run_text_scenarios(runtime: RobotRuntime) -> Tuple[List[Dict[str, float]], float]:
    results: List[Dict[str, float]] = []
    for scenario in TEXT_SCENARIOS:
        plan = runtime.assistant.handle(
            {
                "skill": "assistant",
                "session_id": "eval_text",
                "query": scenario["query"],
                "instructions": "You are an analytical AI assistant evaluating system quality.",
            },
            {"scenario": scenario["name"]},
        )
        latency = total_latency(plan.get("metadata", {}))
        results.append({"name": scenario["name"], "latency_ms": latency})
    average = statistics.mean(item["latency_ms"] for item in results)
    return results, average


def run_voice_scenarios(runtime: RobotRuntime) -> Tuple[List[Dict[str, float]], float]:
    results: List[Dict[str, float]] = []
    accuracy_hits = 0
    for scenario in VOICE_SCENARIOS:
        runtime.voice.enqueue_transcript(scenario["spoken"])
        artifacts = runtime.step()
        plan = artifacts.get("plan", {})
        metadata = plan.get("metadata", {})
        utterance = runtime.voice.last_utterance()
        recognized = utterance.text if utterance else ""
        expected = scenario["expected"]
        accuracy = 1.0 if recognized.strip().lower() == expected.strip().lower() else 0.0
        accuracy_hits += accuracy
        results.append(
            {
                "name": scenario["name"],
                "recognized": recognized,
                "expected": expected,
                "accuracy": accuracy,
                "latency_ms": total_latency(metadata),
            }
        )
    average_accuracy = accuracy_hits / max(1, len(VOICE_SCENARIOS))
    return results, average_accuracy


def run_command_scenarios(runtime: RobotRuntime) -> Tuple[List[Dict[str, str]], float]:
    tool_exec = runtime.assistant.tools
    runtime.safety.set_privilege("informational")
    tool_exec.revoke_consent("issue_command")
    results: List[Dict[str, str]] = []

    # Scenario 1: missing consent
    result = tool_exec.run("issue_command", {"command": "diagnostics"}, {})
    status = result.output["status"] if isinstance(result.output, dict) and "status" in result.output else "error"
    results.append({"name": "no_consent", "status": status, "error": result.error or ""})

    # Scenario 2: consent granted but safety paused
    tool_exec.grant_consent("issue_command")
    runtime.safety.pause()
    result = tool_exec.run("issue_command", {"command": "diagnostics"}, {})
    status = result.output["status"] if isinstance(result.output, dict) and "status" in result.output else "error"
    results.append({"name": "paused", "status": status, "error": result.error or ""})

    # Scenario 3: fully authorized execution
    runtime.safety.resume()
    runtime.safety.set_privilege("command")
    tool_exec.config.allow_control_commands = True
    result = tool_exec.run("issue_command", {"command": "diagnostics"}, {})
    status = result.output["status"] if isinstance(result.output, dict) and "status" in result.output else "error"
    results.append({"name": "authorized", "status": status, "error": result.error or ""})

    success_rate = sum(1 for entry in results if entry["status"] == "accepted") / len(results)
    return results, success_rate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs",
        nargs="*",
        default=["docs/technical_prototype.md", "docs/architecture.md"],
        help="Knowledge base documents to ingest before evaluation.",
    )
    parser.add_argument(
        "--json",
        help="Optional path to write JSON results.",
    )
    args = parser.parse_args()

    config_runtime = RuntimeConfig()
    config_runtime.tooling.allow_control_commands = True
    config_runtime.tooling.allow_shell_commands = True
    config_runtime.tooling.shell_allowlist = ["pwd"]

    runtime = RobotRuntime(config=config_runtime)
    runtime.assistant.ingest_documents(load_documents(args.docs))

    text_results, avg_text_latency = run_text_scenarios(runtime)
    voice_results, avg_voice_accuracy = run_voice_scenarios(runtime)
    command_results, command_success_rate = run_command_scenarios(runtime)

    runtime.shutdown()

    summary = {
        "text": {"scenarios": text_results, "average_latency_ms": avg_text_latency},
        "voice": {"scenarios": voice_results, "average_accuracy": avg_voice_accuracy},
        "commands": {"scenarios": command_results, "success_rate": command_success_rate},
    }

    print("=== Text Scenarios ===")
    for entry in text_results:
        print(f"- {entry['name']}: latency={entry['latency_ms']:.2f} ms")
    print(f"Average latency: {avg_text_latency:.2f} ms\n")

    print("=== Voice Scenarios ===")
    for entry in voice_results:
        print(
            f"- {entry['name']}: accuracy={entry['accuracy']:.2f}, latency={entry['latency_ms']:.2f} ms"
        )
    print(f"Average accuracy: {avg_voice_accuracy:.2f}\n")

    print("=== Command Scenarios ===")
    for entry in command_results:
        print(f"- {entry['name']}: status={entry['status']} error={entry['error']}")
    print(f"Success rate: {command_success_rate:.2f}")

    if args.json:
        output_path = Path(args.json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
