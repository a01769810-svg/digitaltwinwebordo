# ROS Logic To Web Analysis

## Scope

This document maps the current `Celda 3D` web implementation to the ROS/RViz Schneider plant simulation in `Quique2/SchneiderProjectWeb_Simulation`. It is intentionally analysis-only: no runtime behavior is changed in this branch.

Reference repositories analyzed:

- Web repo: `a01769810-svg/digitaltwinwebordo`
- ROS/RViz repo: `Quique2/SchneiderProjectWeb_Simulation`

## 1. Current logic in Celda 3D

The web already has three separate pieces of simulation logic:

1. `components/CellViewer3D.tsx`
   - Owns the 3D scene, URDF loading, cobot poses, turntable angle ref, one visible CAFI mesh, and the internal `SequencePlayer`.
   - `SHOW_DEBUG` is hardcoded to `false`, so Debug exists in code but is hidden from the UI.
   - The local `CafiState` is a single-piece visual state: `parked`, `conveyor`, `in_gripper`, `on_fixture_1`, `on_fixture_2`, `at_vision`, `in_accept_bin`, `in_reject_bin`.
   - `SEQUENCE_PRE` and verdict tails animate one CAFI through conveyor, fixture, riveting wait, vision, and bin.
   - The sequence is visual and local to the scene. It does not consume the HMI state machine as the source of truth.

2. `components/turntableSim.ts`
   - Contains a pure browser mock for the turntable contract.
   - Has cell states `IDLE`, `RUNNING`, `PAUSED`, `FAULT`.
   - Tracks only one boolean `cafiPresent`.
   - `spawnAllowed()` is `cell === 'RUNNING' && position === 'HOME' && !cafiPresent`.
   - `placeCafi()` immediately sets `cafiPresent = true` and starts the turntable cycle.
   - It simulates `HOME -> MOVING_TO_WORK -> WORK -> RIVETING -> RIVETING_DONE -> MOVING_TO_HOME -> CYCLE_DONE -> HOME`.
   - Vision verdict is currently a demo `PASS` at the end of the riveting phase.

3. `components/OperatorHMI.tsx`
   - Displays Start, CAFI, Stop, Reset and DI/DO lamps.
   - Enablement is based on `sim.snapshot`:
     - START: `cell === 'IDLE'`
     - CAFI: `s.spawnAllowed`
     - STOP: `cell === 'RUNNING'`
     - RESET: `cell === 'PAUSED' || cell === 'FAULT'`
   - DI/DO values reflect `turntableSim.ts`, not a full cell/object/robot/vision state machine.

Important current file references:

- `components/CellViewer3D.tsx:19` hides Debug with `SHOW_DEBUG = false`.
- `components/CellViewer3D.tsx:179` defines the single-piece `CafiState`.
- `components/CellViewer3D.tsx:230` defines the visual sequence.
- `components/CellViewer3D.tsx:715` runs `SequencePlayer`.
- `components/CellViewer3D.tsx:2114` has internal HMI/Debug tab state, but Debug is gated by `SHOW_DEBUG`.
- `components/CellViewer3D.tsx:2719` creates `useTurntableSim(discAngleRef)`.
- `components/CellViewer3D.tsx:2726` initializes only one `cafiStateRef`.
- `components/OperatorHMI.tsx:84` to `components/OperatorHMI.tsx:87` define button enablement.
- `components/turntableSim.ts:113` to `components/turntableSim.ts:114` track `cell` and one `cafiPresent`.
- `components/turntableSim.ts:130` defines current `spawnAllowed`.
- `components/turntableSim.ts:143` defines current `placeCafi`.
- `components/useTurntableSim.ts:46` advances `turntableSim` with `requestAnimationFrame`.

## 2. Logic missing for RViz parity

The web is missing these ROS-like concepts:

- Multi-CAFI object model with ids, per-CAFI states, pose ownership, verdict, and riveted flag.
- Conveyor model with sensor-wide presence, tight pick-ready condition, spawn zone occupancy, belt stepping, and accumulation prevention.
- Queue model: up to 2 waiting CAFIs, with at least one in the sensor/pick zone and one at supply/waiting when applicable.
- Event-driven cell state machine that orchestrates robot, gripper, conveyor, turntable, riveting, vision, and bins.
- Distinction between cell state and cycle stage. The web currently reduces most workflow to turntable states.
- Proper sensor release: sensor becomes free when the robot takes the CAFI from the pick zone, not when the turntable cycle completes.
- Realistic START behavior: START arms the cell; it should not itself teleport a CAFI or run a turntable-only cycle.
- Realistic `Colocar CAFI`: it should request a CAFI spawn/queue insert only when the conveyor/sensor/queue gates allow it.
- PASS/FAIL vision decision after the CAFI is actually at vision and camera is triggered.
- CAFI path after vision: pick from vision, then place in accept/reject bin.
- Remachado as a timed station state that marks a specific CAFI as riveted.
- Debug as a separate manual/diagnostic mode with ownership rules so it cannot fight HMI simulation.
- Tests for the state machine and queue gates.

## 3. ROS/RViz logic found

The ROS simulation is event-driven and split by domain:

- `state_manager_node.py` orchestrates the cell FSM.
- `conveyor_sim_node.py` owns spawn interlock, sensor presence, pick-ready, motor, and belt stepping.
- `object_manager_node.py` owns CAFI objects, ids, locations, rigid-body attach/detach, sensor flag, riveted flag, verdict, and bins.
- `rotary_fixture_sim_node.py` owns disc indexing, fixture A/B station assignment, solenoids, seat confirmation, riveting timer, and fixture occupancy.
- `gripper_sim_node.py` owns jaw state, geometric grasp confirmation, object attach/detach.
- `vision_sim_node.py` owns vision presence, camera trigger, timed PASS/FAIL result, and marking object verdict.
- `robot_controller_node.py` owns ordered robot trajectories and gripper wait steps.
- `hmi_node.py` is intentionally dumb: it publishes operator commands and displays state/DI/DO.

The ROS cycle is not a single animation. The state manager publishes requests and advances only when domain nodes publish done/presence/result events.

## 4. ROS files that are source of truth

Use these files as functional source of truth:

- `src/schneider_state_manager/src/state_manager_node.py`
  - Cell states at lines 122-125.
  - Cycle stages at lines 127-144.
  - Operator command callbacks at lines 358, 366, 378, 393.
  - Main FSM tick starts at line 629.
  - Stage transitions for pick/load/seat/index/rivet/vision/bin are in lines 662-1011.

- `src/schneider_conveyor_sim/src/conveyor_sim_node.py`
  - Geometry and sensor constants at lines 85-99.
  - Spawn allowed publisher at line 137.
  - Spawn gate `_spawn_can_proceed()` starts at line 210.
  - Sensor `_part_at_pick_sensor()` starts at line 247.
  - Tight pick-ready `_part_ready_for_pick()` starts at line 261.
  - Conveyor tick starts at line 287.

- `src/schneider_object_manager/src/object_manager_node.py`
  - `Cafi` object starts at line 261.
  - `snapshot()` includes `location`, `riveted`, `verdict`, and `at_sensor` at lines 322-333.
  - Spawn starts at line 402.
  - Attach starts at line 440.
  - Detach starts at line 505.
  - Mark riveted/verdict starts at lines 623 and 636.
  - Belt step starts at line 651.
  - Object tick starts at line 768.

- `src/schneider_rotary_fixture_sim/src/rotary_fixture_sim_node.py`
  - `RIVET_DURATION_S = 30.0` at line 80.
  - Fixture A/B station assignment at lines 108-117.
  - Disc command starts at line 200.
  - Rivet start starts at line 211.
  - Seat command starts at line 239.
  - Tick starts at line 311.

- `src/schneider_gripper_sim/src/gripper_sim_node.py`
  - Geometric grasp rules are documented at the top of the file.
  - Pick task list and graspable locations are around lines 76-87.
  - Grasp candidate evaluation starts at line 173.

- `src/schneider_vision_sim/src/vision_sim_node.py`
  - `INSPECT_DURATION_S = 1.6` and `PASS_PROB = 0.70` at lines 46-47.
  - Trigger gate starts at line 85.
  - Presence check starts at line 100.
  - Timed verdict publish starts at line 113.

- `src/schneider_robot_controller/src/robot_controller_node.py`
  - Trajectories start at line 123.
  - `TRAJ_PICK_VISION` exists at line 178 and prevents the V27 bug where the robot moved to bin with an empty gripper.
  - Request subscribers start around lines 325-346.

- `src/schneider_hmi/src/hmi_node.py`
  - HMI button semantics are documented at the top.
  - START, spawn, STOP, RESET handlers start at lines 171, 181, 199, 211.
  - Button enablement matrix is in the refresh loop around line 338.

Version notes:

- The local reference repo includes summary docs for V58 and V60.
- Source code comments also capture V55, V56, V57, V60 behavior.
- I did not find separate V62, V67, V69, or V71 source folders in the local checkout. The web comments mention V62 HMI, but the ROS local source of truth appears to be V55/V57/V60-era files plus V58/V60 summaries.

## 5. CAFI queue behavior

The web should model CAFIs as objects, not a single `cafiPresent` boolean.

Recommended web queue model:

- `cafis: CafiEntity[]`
- Each CAFI has:
  - `id`
  - `state`
  - `pose`
  - `riveted`
  - `verdict`
  - `createdAt`
  - `updatedAt`
  - optional `fixtureId`
  - optional `bin`
- Queue capacity: maximum 2 waiting CAFIs.
- "Waiting" means CAFIs not yet picked by the robot:
  - `AT_SENSOR`
  - `QUEUED`
  - optionally `ON_CONVEYOR` before tight pick-ready
- At least one CAFI should be visible at sensor/pick when occupied.
- If a second CAFI is allowed, it should appear in supply/queue and advance only when sensor/pick is free.

Recommended queue rules:

- If no CAFI is at sensor and queued count is 0, `Colocar CAFI` creates a CAFI at `AT_SENSOR` or creates at supply then moves to sensor through a conveyor step.
- If sensor is occupied and total waiting count is less than 2, the ROS rule from the user's brief says spawn should still be blocked because sensor is occupied. Therefore the web should not allow another click while sensor is occupied unless the implementation models a physically separate supply buffer. For this project, expose "up to 2 waiting" by allowing the second CAFI only when sensor has been released and the first CAFI is already downstream but queue count can still represent a piece waiting at supply.
- If the final desired UX is "sensor occupied + one behind it visible", that is a supply-buffer feature and must be explicitly separate from the button gate: the HMI button remains blocked while sensor is occupied, but automatic feeder advancement can stage the second piece when safe.

## 6. Sensor behavior

The sensor is occupied when a CAFI is physically in the conveyor pick/sensor window.

ROS distinguishes:

- `part_present_pick`: wide SICK sensor presence.
- `part_ready_for_pick`: tight center-at-pick readiness.

The web should expose both internally:

- `sensor.present`: true if a CAFI is in the sensor/pick zone.
- `sensor.readyForPick`: true if the CAFI is aligned for robot pickup.
- `sensor.cafiId`: id of the CAFI currently detected, or null.

The HMI DI Conveyor lamp should follow `sensor.present`.

Sensor release rule:

- When the robot closes gripper and object attach succeeds, the CAFI transitions from `AT_SENSOR` or `ON_CONVEYOR` to `IN_GRIPPER`.
- At that moment `sensor.present = false`.
- If a queued CAFI exists, the conveyor may move it to sensor/pick after a simulated belt delay, then `sensor.present = true` again.

## 7. When "Colocar CAFI" is allowed

`Colocar CAFI` should be enabled when all are true:

- `cell.state === RUNNING`
- current mode is HMI, not Debug manual control
- no fault is active
- sensor/pick zone is free
- waiting CAFI count is less than 2
- spawn zone/supply buffer is free
- cycle stage is not one of the short blocked stages where ROS blocks spawn:
  - `SEAT`
  - `INDEX_TO_RIVET` / ROS `INDEX_DISC`
  - `INDEX_BACK` / ROS `INDEX_DISC_BACK`

The button should call an action like `dispatch({ type: 'OPERATOR_SPAWN_CAFI' })`, not directly mutate scene refs.

## 8. When "Colocar CAFI" is blocked

The button should be disabled and the HMI should show a reason when any are true:

- cell is `IDLE`, `PAUSED`, or `FAULT`
- Debug mode owns manual controls
- sensor is occupied
- waiting count is already 2
- spawn/supply zone is occupied
- blocked stage is active (`SEAT`, `INDEX_TO_RIVET`, `INDEX_BACK`)
- conveyor accumulation/fault is active

The blocked state must be enforced in the state machine, not only in the button.

## 9. How to allow up to 2 waiting CAFIs

Recommended implementation:

- Keep `MAX_WAITING_CAFIS = 2`.
- Represent two visible waiting slots:
  - `AT_SENSOR`: the pick-ready CAFI.
  - `QUEUED`: supply/waiting CAFI behind the sensor.
- A new CAFI can enter `QUEUED` only when `waitingCount < 2` and the supply zone is free.
- A CAFI can move `QUEUED -> AT_SENSOR` only when sensor is free.
- If using the strict user rule "if sensor occupied, button blocked", then the second waiting CAFI should be created only after the first has been picked and the sensor has freed, or via an automatic feeder rule separate from the button.
- Do not teleport: `QUEUED -> ON_CONVEYOR -> AT_SENSOR` should have a simulated belt movement or at least a timed conveyor stage.

## 10. CAFI states

Recommended web CAFI states:

- `QUEUED`
- `AT_SENSOR`
- `ON_CONVEYOR`
- `IN_GRIPPER`
- `IN_LOAD_FIXTURE`
- `IN_RIVET_FIXTURE`
- `IN_VISION`
- `ACCEPTED_BIN`
- `REJECTED_BIN`
- `DONE`

Additional internal states may be useful:

- `SETTLING_LOAD`
- `SETTLING_VISION`
- `FALLING_TO_BIN`

Mapping from ROS:

- `on_conveyor` -> `ON_CONVEYOR` or `AT_SENSOR` depending on `at_sensor`
- `in_gripper` -> `IN_GRIPPER`
- `in_fixture_A/B` + station assignment outer -> `IN_LOAD_FIXTURE`
- `in_fixture_A/B` + station assignment inner -> `IN_RIVET_FIXTURE`
- `at_vision` -> `IN_VISION`
- `in_bin` + target/verdict -> `ACCEPTED_BIN` or `REJECTED_BIN`

## 11. Cell states

Recommended cell states:

- `IDLE`: not armed, safe/rest state.
- `RUNNING`: automatic ROS-like simulation can execute.
- `PAUSED`: STOP pressed; timers and actions freeze.
- `FAULT`: explicit fault with reason.

Rules:

- START: `IDLE -> RUNNING`
- STOP: `RUNNING -> PAUSED`
- RESET: `PAUSED/FAULT -> IDLE` after cleanup or immediate safe reset in the first web implementation.
- HMI simulation tick runs only in `RUNNING`.

## 12. Table states

Recommended table/fixture states:

- `HOME`
- `INDEXING_TO_RIVET`
- `AT_RIVET`
- `RIVETING`
- `RIVET_DONE`
- `INDEXING_TO_LOAD`
- `ERROR`

Also track:

- `angleDeg`
- `target`
- `moving`
- `limitHome`
- `limitWork`
- `outerFixtureId`
- `innerFixtureId`
- `fixtureOccupancy`
- `solenoidState`
- `cafiSeated`

This maps to ROS `rotary_fixture_sim_node.py`: disc state, A/B station assignment, fixture occupancy, seat confirmation, and 30 s rivet timer.

## 13. Riveting states

Recommended riveting states:

- `IDLE`
- `ARMED`
- `ACTIVE`
- `DONE`
- `FAULT`

Rules:

- Riveting can start only if the current inner/rivet fixture has a CAFI.
- Active duration should be configurable:
  - ROS reference: 30 s.
  - Web demo may use a speed multiplier, but the state machine should expose simulated elapsed/remaining time.
- On done:
  - set the specific CAFI `riveted = true`
  - move stage to `INDEX_BACK`
  - publish/derive HMI DO/DI equivalents

## 14. Vision states

Recommended vision states:

- `IDLE`
- `PRESENT`
- `INSPECTING`
- `PASS`
- `FAIL`
- `FAULT`

Rules:

- Camera trigger is accepted only when a CAFI is in `IN_VISION`.
- Inspection runs for a simulated dwell.
- Verdict can be deterministic for tests by injecting a `visionPolicy`.
- Default demo can match ROS `PASS_PROB = 0.70`.
- Verdict must attach to the CAFI, not only to global HMI state.

## 15. HMI states

Recommended HMI model:

- `mode: 'HMI' | 'DEBUG'`
- `cell.state`
- `cycle.stage`
- `spawn.allowed`
- `spawn.blockReason`
- `fault.reason`
- `selectedCafiId`
- `di`
- `do`

HMI should remain a view/controller surface:

- It sends operator events.
- It does not own business logic.
- DI/DO lamps are derived from the simulation state.

## 16. HMI vs Debug separation

Current code has a hidden Debug tab behind `SHOW_DEBUG = false`, but HMI and Debug do not yet have a formal ownership model.

Recommended rules:

- Introduce `simMode: 'HMI' | 'DEBUG'`.
- HMI mode:
  - automatic state machine owns robot poses, CAFI poses, gripper, table angle.
  - manual Debug controls are hidden or disabled.
- Debug mode:
  - automatic HMI simulation is paused or detached.
  - manual pose/jog/object inspection controls are visible.
  - HMI buttons are disabled except Reset/Return-to-HMI if intentionally supported.
- Switching HMI -> Debug while running:
  - either require STOP first, or automatically transition to `PAUSED` with reason `DEBUG_MODE`.
- Switching Debug -> HMI:
  - require Reset or a reconcile step to restore safe state.

This prevents the current risk where `SequencePlayer`, HMI turntable sim, and Debug pose controls can write to the same refs.

## 17. ROS-like tests for the web

Preferred first test layer: pure TypeScript state-machine tests without React or Three.js.

Recommended tests:

1. Does not allow CAFI spawn when sensor is occupied.
2. Allows CAFI spawn when sensor is free.
3. Allows maximum 2 waiting CAFIs.
4. START runs full cycle with 1 CAFI.
5. START runs cycle with 2 CAFIs in queue.
6. Sensor releases when robot takes CAFI.
7. Next CAFI advances when sensor releases.
8. Riveting holds active for simulated duration and then marks CAFI riveted.
9. Vision assigns PASS/FAIL from injected policy.
10. CAFI ends in accepted/rejected bin according to verdict.
11. STOP pauses timers and stage progression.
12. RESET clears pause/fault and returns to safe state.
13. Debug tab/mode is not mixed into HMI mode.
14. HMI mode does not use manual Debug controls.
15. TypeScript passes.
16. `npm run build` passes.

Because the current repo has no test runner, add one in a later implementation step:

- Option A: `vitest` for pure state machine tests.
- Option B: no dependency initially; add `scripts/validate-ros-like-sim.mjs` that imports compiled JS or runs TS through `tsx`.
- Option C: document-only tests until test tooling is approved.

## 18. Exact files to touch in implementation

Likely files:

- `components/turntableSim.ts`
  - Replace or wrap the single turntable mock with a full cell state machine.
  - Keep Raspberry turntable contract stable.

- `components/useTurntableSim.ts`
  - Rename or split into `useCellSimulation`.
  - Drive state-machine ticks and expose operator actions.

- `components/OperatorHMI.tsx`
  - Keep visual layout, but bind to full cell snapshot and block reasons.

- `components/CellViewer3D.tsx`
  - Render multiple CAFIs.
  - Separate HMI/Debug mode.
  - Replace direct visual sequence ownership with state-machine-driven pose/state outputs.

- `components/CobotLiveView.tsx`
  - Do not change Raspberry contract unless explicitly approved.
  - Only update shared types if needed and backward compatible.

- New recommended files:
  - `components/cellStateMachine.ts`
  - `components/cellStateTypes.ts`
  - `components/cellStateMachine.test.ts` or `scripts/validate-ros-like-sim.mjs`

- Documentation:
  - `ROS_LOGIC_TO_WEB_ANALYSIS.md`
  - `WEB_SIMULATION_IMPLEMENTATION_PLAN.md`

Files not to touch without approval:

- `raspberry_turntable_gateway/*`
- GPIO pin mapping
- Raspberry API contract
- `components/useLiveTurntable.ts` except type-only compatibility if required
- unrelated Cobot en Vivo behavior

