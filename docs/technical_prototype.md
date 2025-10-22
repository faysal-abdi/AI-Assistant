# Technical Prototype Architecture

## Objectives

- Ship a production-ready AI assistant core that balances latency, quality, and cost.
- Provide pluggable model, retrieval, and tooling layers so we can adapt to new providers.
- Establish observability and guardrails from the first prototype to de-risk scale out.

## Model Strategy

- **Primary reasoning model**: OpenAI `gpt-4.1-mini` (or Anthropic Claude 3.5 Sonnet) for balanced quality + latency (<1.4 s p95 in current benchmarks).
- **Fallback fast-path**: OpenAI `gpt-4o-mini` (or Mistral Small hosted) targeting <650 ms p95 for short-form intents, feature-flagged via config.
- **Offline/self-hosted option**: Mixtral 8x7b (via vLLM) earmarked for jurisdictions requiring data residency. Needs GPU pool; keep behind feature flag.
- **Embeddings**: `text-embedding-3-large` for semantic recall, with `bgem3` as fallback when offline.
- **Moderation**: Provider-native moderation (e.g., OpenAI Omni Moderation) plus keyword heuristics in the interface layer.

Model selection happens through the `ModelGateway` (prototype implemented in `src/robot_assistant/runtime/ai/models.py`) which encapsulates provider-specific clients, retries, and circuit breakers.

## Retrieval & Knowledge

- **Document store**: Pluggable interface with three modes
  - In-memory vector store (prototype)
  - Disk-backed SQLite + embedding index
  - External (e.g., Weaviate/Pinecone) via adapters
- **Chunking**: Markdown-aware chunker with 512 token windows and 64 token overlap.
- **Ranking pipeline**
  1. Sparse lexical scoring (BM25-lite) for quick pruning.
  2. Dense cosine similarity via embedding provider.
  3. Optional re-rank using a cross-encoder model (future).
- **Freshness**: Retrieval layer can attach runtime tool outputs as ephemeral documents with TTL.

Prototype classes live under `src/robot_assistant/runtime/ai/retrieval.py`. The retriever exposes async-friendly `retrieve(query, k)` returning scored `Document` objects.

## Tooling Surface

- **Tool registry**: Declarative registration with metadata (permissions, rate limits, expected latency).
- **Execution**: Tools run inside the `ToolExecutor` which publishes timing + success metrics and sanitizes outputs before sending to the model.
- **Default tools**
  - `search_docs`: queries internal knowledge base via retriever.
  - `get_runtime_state`: introspects perception/planning state for embodied tasks.
  - `issue_command`: dispatches structured actions to the control subsystem with safety checks.
  - `search_files`: scans allowlisted directories for relevant files.
  - `run_shell_command`: executes allowlisted shell commands once consent is granted.
  - `create_calendar_event`: (optional) scaffolds calendar entries through EventKit.
  - `summarize_inbox`: (optional) summarizes recent email threads.
  - `run_home_automation`: (optional) bridges into HomeKit for smart home actions.

Refer to `src/robot_assistant/runtime/ai/tools.py` for the prototype implementation.

### Tool Plugin Strategy

- **Calendar & email**: Use macOS EventKit and MailKit via PyObjC wrappers; expose intent-specific helpers (`create_event`, `summarize_inbox`) that require explicit user consent tokens before execution.
- **Shell actions**: Offer a constrained shell tool that only executes allowlisted commands and requires per-session confirmation; sandbox outputs (truncate, redact sensitive paths).
- **File search**: Index local files via Spotlight/metadata APIs for speed, with a pure-Python fallback that walks allowlisted directories.
- **Home automation**: Bridge HomeKit using the Home Control framework or third-party hubs; keep behind a feature flag so non-home users aren't impacted.
- **Safety model**: Track consent + scope per tool, enforce rate limits, and emit structured audit logs so high-privilege tools remain transparent and revocable.

## Memory & Preferences

- **Short-term buffer**: The assistant automatically loads the last few turns from the SQLite store so each reply maintains conversational context.
- **Persistent store**: Conversations and user preferences are stored under `var/memory.db` (configurable via `RuntimeConfig.memory`).
- **Preference management**: Shell commands (`/prefs`, `/pref <key> <value>`) update the persistent store, letting the assistant tailor responses to user settings.
- **Session IDs**: Multiple named sessions can run in parallel—supply `--session <id>` to the shell to resume earlier conversations.

## Orchestration Flow

1. **Interface** collects intent payloads (NL text, context, safety tag).
2. **Guardrails** run light moderation, intent classification, and determine required tools.
3. **ModelGateway** selects the target model based on policy (SLA, user tier, region).
4. **Planner** builds a control or conversational plan; for textual responses it calls into the `AssistantPipeline` (prototype).
5. **Retriever** enriches prompts via the chosen tools; results are packed into a prompt template with provenance tags.
6. **LLM call** executes with streaming, tool call inspection, and automatic retries (exponential backoff + circuit breaker).
7. **Post-processing** normalizes outputs, extracts structured actions, logs metrics, and sends responses to the interface & controller.

## Observability & Latency Targets

- **Metrics**: Expose per-stage timing, token usage, cache hit rate, tool success/failure, moderation rejects.
- **Tracing**: Optional OpenTelemetry export (stubbed in prototype) for end-to-end spans.
- **Latency budget** (p95, production goal)
  - Moderation + routing: 80 ms
  - Retrieval + tool execution: 250 ms
  - LLM generation: model dependent (fast-path 650 ms, primary 1.4 s)
  - Post-processing: 70 ms
  - Total target: <1.8 s p95 for conversational turns.

Prototype instrumentation is provided via `LatencyProbe` in `src/robot_assistant/runtime/ai/telemetry.py`.

## Configuration & Safety

- Centralized runtime configuration extends `RuntimeConfig` with model, tool, memory, and safety sections.
- Secrets managed via environment variables or vault integration (not included in prototype).
- Safety manager enforces privilege tiers (`informational` vs `command`), supports pause/resume, and logs to `var/safety.log`.
- Safety filters run synchronously in the interface layer; escalate high-risk intents to a human review queue stub.
- Logging follows privacy policy: redact PII, attach request + user identifiers via hashed IDs.

## Next Steps

- Harden retriever (hybrid indexing, persistent store).
- Integrate streaming client adapters for chosen providers.
- Expand evaluation harness with golden conversations + hallucination detection.
- Build autoscaling knobs (token budgets, adaptive batching) for production workloads.

## Prototype Validation

Run the latency harness to ingest local documentation and measure stage timings:

```bash
python3 scripts/latency_probe.py --query "Summarize the retrieval flow" --fast-path
```

The script reports total latency, per-stage breakdown, tool execution times, and token usage, allowing quick sanity checks against the latency budgets above.

For voice experiments, simulate wake-word driven requests with the CLI harness:

```bash
python3 scripts/voice_demo.py
```

Type utterances (standing in for transcribed speech) to route them through the full assistant pipeline and receive synthesized responses on stdout.

For text-first iteration with memory and telemetry, launch the conversational shell:

```bash
python3 scripts/assistant_shell.py --stream
```

The shell supports persona tweaks, model routing commands, history inspection, `/tools` listings, consent management (`/consent` / `/revoke`), and safety controls (`/priv`, `/pause`, `/resume`, `/safety`), alongside latency + token metrics after each exchange.

For continuous evaluation across modalities, run the scenario suite:

```bash
python3 scripts/evaluation_suite.py --json var/eval_report.json
```

It reports per-scenario latency, voice transcription accuracy, and command success rates, optionally writing a JSON summary for regression tracking.

## Voice Interface Roadmap

- **Speech-to-text**: Leverage Apple Speech framework via PyObjC for online dictation, with Vosk (offline) as a fallback. Expose both through a `SpeechRecognizer` interface under `runtime/voice`.
- **Wake word**: Integrate Picovoice Porcupine (or an open-source alternative) behind a `WakeWordDetector` abstraction to keep hotword processing local and lightweight; feature-flagged to allow push-to-talk only mode.
- **Text-to-speech**: Use macOS `NSSpeechSynthesizer` for natural voice output plus a cross-platform fallback (e.g., Coqui TTS). Provide `SpeechSynthesizer` wrapper with streaming hooks for future model-based voices.
- **Audio session management**: Centralize microphone selection, audio metering, and session lifecycle to avoid conflicts with other apps.
- **Event bus**: Emit intents when the wake detector fires, transcription chunks arrive, or speech playback completes so the existing runtime can react just like it does to protocol intents.
- **Testing strategy**: Add a CLI harness that toggles wake word detection, records short utterances, and streams transcripts to the assistant pipeline, enabling latency + accuracy measurement on-device.

### macOS Voice Setup

1. Install the Apple framework bindings:

   ```bash
   python3 -m pip install pyobjc pyobjc-framework-AVFoundation pyobjc-framework-Speech
   ```

   (Optional) Install `sounddevice` if you need a cross-platform microphone fallback:

   ```bash
   python3 -m pip install sounddevice
   ```

2. Run the conversational shell or voice demo. The runtime will automatically select the macOS-native recognizer (`SFSpeechRecognizer` + `AVAudioEngine`) and pipe responses through `NSSpeechSynthesizer`.
3. On the first invocation, macOS prompts for microphone access—approve it in System Settings ▸ Privacy & Security ▸ Microphone.

## Conversational Shell Roadmap

- **Runtime wrapper**: Provide a dedicated CLI shell that owns a runtime instance, streams assistant responses, and visualizes retrieval/tool traces in real time.
- **Session memory**: Maintain rolling conversation history in memory, optionally persisted to disk to survive shell restarts.
- **Prompt shaping**: Let users adjust persona, temperature, or route via interactive commands (e.g., `/persona`, `/model fast`).
- **Observability view**: Surface per-turn latency, token usage, and tool invocations inline so developers can tune without leaving the shell.
- **Extensibility**: Make the shell pluggable for GUI integration (menu bar app later) by isolating transport (stdin/stdout today, sockets tomorrow).
- **Safety controls**: Include `/redact`, `/clear`, and `/consent` toggles so privileged actions require explicit confirmation even in local dev.
