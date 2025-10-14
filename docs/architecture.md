# Architectural Overview

## Core Principles

- **Layered isolation**: Keep hardware access separate from decision logic, protecting high-level autonomy from device-specific failures.
- **State propagation**: Centralize world state in the runtime layer so perception, planning, and control stay synchronized.
- **Skill composition**: Encapsulate tasks as reusable skills that compose planning outputs with control policies.

## Subsystems

### Hardware Abstraction (`src/robot_assistant/hardware`)

- `interfaces.py` defines abstract sensor and actuator contracts.
- `drivers/` holds concrete device drivers or simulators.
- Provides deterministic behavior for the rest of the stack through calibration, safety checks, and latency smoothing.

### Perception (`src/robot_assistant/perception`)

- `pipeline.py` hosts sensor fusion, filtering, and environment modeling.
- Maintains the robot state estimate that downstream modules consume.

### Planning (`src/robot_assistant/planning`)

- `planner.py` covers deliberative reasoning, task decomposition, and sequencing.
- Interacts with skills to generate executable plans.

### Control (`src/robot_assistant/control`)

- `controller.py` converts plans into actuator commands with feedback loops and safety limits.
- Ensures the robot follows trajectories while respecting hardware constraints.

### Skills (`src/robot_assistant/skills`)

- `registry.py` maps skill identifiers to implementations and metadata.
- Skills orchestrate planners and controllers to deliver assistant-level behavior.

### Interface (`src/robot_assistant/interface`)

- `protocol.py` hosts communication protocols for human interaction, APIs, or other systems.
- Normalizes inputs and outputs before they touch planning or skills.

### Runtime (`src/robot_assistant/runtime`)

- `system.py` wires together hardware, perception, planning, control, skills, and interface modules.
- Owns lifecycle management, scheduling, and telemetry.

### Configuration (`src/robot_assistant/config`)

- `defaults.py` stores configuration baselines and parameter schemas.
- Centralizes tuning knobs for hardware, perception, and control.

## Execution Flow

1. Runtime initializes hardware drivers and loads default configuration.
2. Perception ingests sensor streams and updates the world state.
3. Planning synthesizes plans based on goals, constraints, and state.
4. Skills wrap planning outputs into actionable routines.
5. Control executes routines through actuator commands and feedback.
6. Interface captures new intents or feedback, updating goals and closing the loop.
