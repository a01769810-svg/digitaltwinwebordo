# Web Simulation Implementation Plan

## Goal

Prepare `Celda 3D` to behave like the ROS/RViz Schneider plant simulation, with HMI as the normal automatic simulation mode and Debug as a separate manual/diagnostic mode.

This plan keeps the existing visual scene and Raspberry gateway contract intact. The implementation should be incremental and testable.

## Proposed architecture

Add a pure TypeScript cell state machine and make React/Three.js render its snapshot.

Recommended modules:

- `components/cellStateTypes.ts`
  - Shared enums, entity interfaces, DI/DO snapshot, operator events.

- `components/cellStateMachine.ts`
  - Pure reducer/tick simulation.
  - No React, no Three.js, no DOM.
  - Source of truth for CAFIs, sensor, conveyor, robot task, table, riveting, vision, bins, HMI mode.

- `components/useCellSimulation.ts`
  - React hook that owns the state machine instance.
  - Calls `tick(dt)` from `requestAnimationFrame`.
  - Exposes `snapshot` and operator/debug actions.

- `components/OperatorHMI.tsx`
  - Stays mostly visual.
  - Consumes `CellSnapshot`.
  - Sends operator events only.

- `components/CellViewer3D.tsx`
  - Renders scene from `CellSnapshot`.
  - Renders multiple CAFIs by id/state.
  - Separates HMI and Debug tabs/modes.

Keep `components/turntableSim.ts` compatible until the new state machine replaces its HMI role. The Raspberry live path should continue using the existing turntable contract.

## Proposed state machine

### Cell states

- `IDLE`
- `RUNNING`
- `PAUSED`
- `FAULT`

### Cycle stages

- `WAIT_FOR_CAFI`
- `PICK_CONV`
- `PLACE_LOAD`
- `SEAT`
- `INDEX_TO_RIVET`
- `RIVETING`
- `INDEX_BACK`
- `PICK_RIVETED`
- `PLACE_VISION`
- `INSPECT`
- `PICK_VISION`
- `PLACE_BIN`
- `DONE`

### CAFI states

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

### Table states

- `HOME`
- `INDEXING_TO_RIVET`
- `AT_RIVET`
- `RIVETING`
- `RIVET_DONE`
- `INDEXING_TO_LOAD`
- `ERROR`

### Riveting states

- `IDLE`
- `ARMED`
- `ACTIVE`
- `DONE`
- `FAULT`

### Vision states

- `IDLE`
- `PRESENT`
- `INSPECTING`
- `PASS`
- `FAIL`
- `FAULT`

### HMI/Debug modes

- `HMI`
- `DEBUG`

Mode ownership:

- HMI owns automatic simulation.
- Debug owns manual poses and inspection.
- Entering Debug while running should pause HMI or require STOP first.
- Debug manual writes must not run while HMI tick is advancing robot/table/object state.

## Operator actions

### START

Allowed when:

- `mode === 'HMI'`
- `cell.state === 'IDLE'`

Effect:

- `cell.state = 'RUNNING'`
- `cycle.stage = 'WAIT_FOR_CAFI'`
- Does not spawn a CAFI by itself.

### Colocar CAFI

Allowed when:

- `mode === 'HMI'`
- `cell.state === 'RUNNING'`
- sensor is free
- waiting CAFIs count is less than 2
- supply/spawn zone is free
- no fault
- stage is not blocked for spawn

Blocked when:

- sensor occupied
- waiting count is already 2
- cell is not running
- mode is Debug
- stage is `SEAT`, `INDEX_TO_RIVET`, or `INDEX_BACK`
- fault/accumulation exists

Effect:

- Create a CAFI with id and initial state.
- If sensor is free, move to `AT_SENSOR` after conveyor/supply timing.
- If a separate supply buffer is implemented, second CAFI can be `QUEUED`; otherwise require sensor free before each click.

### STOP

Allowed when:

- `cell.state === 'RUNNING'`

Effect:

- `cell.state = 'PAUSED'`
- Freeze timers and state progression.

### RESET

Allowed when:

- `cell.state === 'PAUSED' || cell.state === 'FAULT'`

Initial web implementation:

- Return to safe `IDLE`.
- Clear active timers, fault, queued objects, gripper, table target, vision result.

Later ROS-parity implementation:

- Mimic V55 reset cleanup: dump held CAFI, remove stranded vision/fixture CAFIs, index inner fixture if needed, then return to IDLE.

## CAFI queue design

Data model:

```ts
interface CafiEntity {
  id: number;
  state: CafiState;
  riveted: boolean;
  verdict: 'PASS' | 'FAIL' | null;
  fixtureId: 'A' | 'B' | null;
  bin: 'ACCEPT' | 'REJECT' | null;
  poseKey: string;
  createdAt: number;
  updatedAt: number;
}
```

Derived values:

- `waitingCafis = cafis.filter(c => c.state === 'QUEUED' || c.state === 'AT_SENSOR' || c.state === 'ON_CONVEYOR')`
- `sensorOccupied = cafis.some(c => c.state === 'AT_SENSOR')`
- `spawnAllowed = cell.state === 'RUNNING' && !sensorOccupied && waitingCafis.length < 2 && !blockedStage`

Advancement:

1. Operator creates CAFI if allowed.
2. CAFI moves to sensor/pick.
3. `PICK_CONV` attaches CAFI to gripper.
4. Sensor releases immediately on attach.
5. Next queued CAFI may advance to sensor after belt delay.
6. First CAFI continues through fixture, rivet, vision, and bin.

## Cycle flow

Recommended event/tick flow:

1. `WAIT_FOR_CAFI`
   - If `AT_SENSOR` and robot ready, transition to `PICK_CONV`.

2. `PICK_CONV`
   - Robot moves through conveyor poses.
   - Gripper closes.
   - CAFI transitions `AT_SENSOR -> IN_GRIPPER`.
   - Sensor becomes free.
   - Transition to `PLACE_LOAD`.

3. `PLACE_LOAD`
   - Robot places CAFI at load fixture.
   - CAFI transitions `IN_GRIPPER -> IN_LOAD_FIXTURE`.
   - Transition to `SEAT`.

4. `SEAT`
   - Solenoid/seating timer runs.
   - Transition to `INDEX_TO_RIVET`.

5. `INDEX_TO_RIVET`
   - Table indexes 180 degrees.
   - Fixture assignment swaps A/B.
   - CAFI is now in rivet fixture.
   - Transition to `RIVETING`.

6. `RIVETING`
   - Riveting timer runs.
   - CAFI `riveted = true`.
   - Transition to `INDEX_BACK`.

7. `INDEX_BACK`
   - Table returns to load side.
   - Transition to `PICK_RIVETED`.

8. `PICK_RIVETED`
   - Robot picks riveted CAFI from fixture.
   - Transition to `PLACE_VISION`.

9. `PLACE_VISION`
   - Robot places CAFI at vision.
   - CAFI transitions to `IN_VISION`.
   - Transition to `INSPECT`.

10. `INSPECT`
    - Camera trigger accepted only if CAFI in vision.
    - Vision timer produces PASS/FAIL.
    - Transition to `PICK_VISION`.

11. `PICK_VISION`
    - Robot picks CAFI from vision.
    - Transition to `PLACE_BIN`.

12. `PLACE_BIN`
    - PASS -> accepted bin.
    - FAIL -> rejected bin.
    - CAFI transitions to `DONE`.
    - Transition to `DONE`.

13. `DONE`
    - If next CAFI is waiting, return to `WAIT_FOR_CAFI`.
    - Otherwise remain ready in `WAIT_FOR_CAFI`.

## DI/DO mapping

Digital Inputs:

- Conveyor: `sensor.present`
- Remachado: CAFI present in current rivet/load fixture as appropriate
- Vision: CAFI in vision zone
- Cobot ready: robot not busy

Digital Outputs:

- Conveyor motor: conveyor advancing queued/supply CAFI
- Disco: table indexing
- Remachado: riveting active
- Camara: vision inspecting or trigger pulse
- Grip Open: gripper state open
- Grip Close: gripper state closed
- Sol Left: fixture seating/holding active
- Reservado: false until a real signal exists

## Tests to add

Preferred: add `vitest` and pure state-machine tests.

Proposed files:

- `components/cellStateMachine.ts`
- `components/cellStateMachine.test.ts`

Test cases:

1. `spawn is blocked when sensor occupied`
2. `spawn is allowed when sensor free`
3. `waiting queue is capped at 2`
4. `start plus one CAFI reaches DONE`
5. `start plus two CAFIs processes both in order`
6. `sensor releases on PICK_CONV attach`
7. `queued CAFI advances after sensor release`
8. `riveting stays active for configured simulated time`
9. `vision verdict is assigned from injected policy`
10. `PASS routes to accepted bin and FAIL routes to rejected bin`
11. `STOP pauses tick progression`
12. `RESET returns to safe IDLE`
13. `Debug mode pauses/disables HMI automatic tick`
14. `HMI mode does not expose manual debug controls`
15. `npx tsc --noEmit`
16. `npm run build`

If adding a test dependency is not desired yet, add `scripts/validate-ros-like-sim.mjs` as a dependency-free validation harness once the state machine exists.

## Implementation phases

### Phase 1: Pure state machine scaffold

- Add types and a pure `createCellStateMachine`.
- Implement START/STOP/RESET/spawn gates.
- Implement sensor and queue rules.
- Add basic tests/validation script.
- No 3D rendering changes except wiring optional snapshots in dev.

### Phase 2: Single CAFI full cycle

- Implement stage flow for one CAFI.
- Add table/rivet/vision timers.
- Add deterministic vision policy for tests.
- Keep current 3D visual sequence until state snapshots are stable.

### Phase 3: Multi-CAFI queue

- Add second waiting CAFI.
- Sensor release advances next CAFI.
- Ensure no teleport: add belt/supply delay or interpolation state.

### Phase 4: 3D binding

- Render CAFIs from `cafis[]`.
- Derive CAFI pose from state and fixture/table assignment.
- Remove the old single `cafiStateRef` as source of truth.
- Keep URDF/pose constants.

### Phase 5: HMI/Debug split

- Replace `SHOW_DEBUG` hard gate with a real HMI/Debug mode control.
- Debug mode is manual and diagnostic.
- HMI mode owns automatic simulation.
- Switching rules pause or reset safely.

### Phase 6: Cleanup and parity

- Align labels/stages with ROS names.
- Add fault reasons.
- Add reset cleanup closer to ROS V55.
- Broaden tests.

## Files to touch

Expected implementation files:

- `components/cellStateTypes.ts` (new)
- `components/cellStateMachine.ts` (new)
- `components/cellStateMachine.test.ts` or `scripts/validate-ros-like-sim.mjs` (new)
- `components/useTurntableSim.ts` or new `components/useCellSimulation.ts`
- `components/turntableSim.ts`
- `components/OperatorHMI.tsx`
- `components/CellViewer3D.tsx`
- `package.json` if adding a test runner
- `tsconfig.json` only if test/tooling requires it

Do not touch without approval:

- `raspberry_turntable_gateway/*`
- Raspberry HTTP/WebSocket contract
- GPIO pin mapping
- `components/useLiveTurntable.ts` behavior
- unrelated `CobotLiveView` live gateway logic

## Risks

- The current web has two separate simulation concepts: `turntableSim.ts` and `SequencePlayer`. If both remain active, HMI and scene can disagree.
- Debug controls write directly to refs. Without an ownership model, Debug can fight automatic HMI simulation.
- Current HMI `spawnAllowed` is turntable-only and would incorrectly block/allow CAFIs relative to sensor/queue behavior.
- Adding multi-CAFI rendering requires replacing single `cafiStateRef`; this touches central 3D code.
- Vision result needs deterministic injection for tests, while demo may remain probabilistic.
- Build can rewrite `dist`; implementation commits should avoid unrelated dist churn unless deployment explicitly requires it.
- Raspberry live contract must stay stable.

## Validation commands

For this documentation-only branch:

```bash
npx tsc --noEmit
npm run build
git status -sb
```

For the implementation branch after state-machine code exists:

```bash
npx tsc --noEmit
npm run test
npm run build
```

If no test runner is added:

```bash
node scripts/validate-ros-like-sim.mjs
npx tsc --noEmit
npm run build
```

## Commit plan

Branch:

```bash
feature/ros-like-hmi-state-machine-plan
```

Commit:

```bash
docs: plan ROS-like HMI simulation state machine
```

Push:

```bash
git push -u origin feature/ros-like-hmi-state-machine-plan
```

