# Automated Robot Assistant Foundation

This repository outlines the base structure for an automated robot that will mature into an AI assistant. The layout separates hardware integration, perception, decision-making, control, and human-facing interaction, allowing each capability to evolve independently while remaining cohesive.

```
.
├── docs/                     Documentation and design references
├── src/
│   └── robot_assistant/
│       ├── config/           Runtime configuration defaults
│       ├── control/          Low-level controllers and safety loops
│       ├── hardware/         Hardware interfaces and drivers
│       ├── interface/        Human and system interface logic
│       ├── perception/       Sensor fusion and state estimation
│       ├── planning/         Task and motion planning modules
│       ├── runtime/          System orchestration, lifecycle, and services
│       └── skills/           High-level task skills built on planning/control
└── tests/                    Test harnesses and simulation stubs
```

### Getting Started

1. Extend `docs/architecture.md` with platform-specific requirements.
2. Implement hardware stubs in `src/robot_assistant/hardware` to model actuators and sensors.
3. Evolve the runtime loop in `src/robot_assistant/runtime/system.py` to coordinate perception, planning, and control.
4. Persist runtime configuration with `src/robot_assistant/config/runtime_store.py`; defaults write to `var/runtime_config.json`.

### Configuration Service & Dashboard

- **API**: `scripts/config_server.py` launches a FastAPI surface that exposes `/config` CRUD, section-specific patches, session preference helpers, tooling consent metadata, and safety log inspection. Protect it by exporting `ROBOT_ASSISTANT_CONFIG_TOKEN`; adjust allowed origins via `ROBOT_ASSISTANT_CONFIG_CORS`.
- **Run**:
  ```bash
  # install python deps
  pip install fastapi uvicorn pydantic

  # start the api
  python3 scripts/config_server.py --port 8080
  ```
- **UI**: `ui/config-dashboard` is a Vite + React experience (React Query + Axios). Configure `.env.local` with `VITE_CONFIG_API_URL` and optional `VITE_CONFIG_API_TOKEN`.
  ```bash
  cd ui/config-dashboard
  npm install
  npm run dev
  ```
- The dashboard provides controls for loop cadence, model routing, retrieval mix, tooling guardrails, voice preferences, memory sizing, session preferences, and a live safety audit log feed.

### Next Steps

- Add simulation tooling to validate controllers without physical hardware.
- Introduce persistent storage and state logging for diagnostics.
- Integrate policy learning modules once the deterministic pipeline is stable.

### macOS Voice Dependencies

To enable live microphone transcription and on-device speech synthesis, install the Apple framework bridges:

```bash
python3 -m pip install pyobjc pyobjc-framework-AVFoundation pyobjc-framework-Speech
```

Optional cross-platform audio capture helper:

```bash
python3 -m pip install sounddevice
```

After installing, run `python3 scripts/voice_demo.py` and approve the microphone permission prompt to try realtime voice interactions.
