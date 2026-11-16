# Testing and Validation

## 10.1 Testing Strategy

Testing follows the architecture. Because the simulation engine, the central pipeline and the recovery engine do not depend on MQTT or the database, most behaviour can be tested in-process, quickly and deterministically. A smaller set of integration tests then confirms the real broker and database paths. The strategy has five levels:

1. **Unit tests** of physics, sensors, actuator limits, the twin, authorisation, the state machine and integrity checks.
2. **Simulation tests** of reproducibility, schema conformance, every scenario, and network behaviour.
3. **Evaluation tests** of features, detectors, metrics and the grouped split.
4. **API tests** of every major endpoint through FastAPI's test client, with no broker or database.
5. **Live-stack integration tests** through real Mosquitto and PostgreSQL, marked `integration` and skipped automatically when the services are not running.

Static analysis (Ruff, mypy, ESLint, the TypeScript compiler) and a production build of the dashboard complement the tests. Manual browser checks covered the dashboard, which has no automated tests.

## 10.2 Unit Testing

@tab:tests lists the test files and their collected test counts. Parametrised tests count once per parameter set.

Table: Automated test suites {#tab:tests}

| File | Tests | Scope |
| --- | --- | --- |
| `tests/unit/test_central.py` | 34 | Telemetry validation, twin ordering and reset, authorisation, recovery state machine, integrity checks, closed-loop scenarios |
| `tests/unit/test_physics_and_sensors.py` | 18 | Wear and vibration, overheating with and without edge, leak hydraulics, power balance, tank level, sensor statistics, actuator limits, edge voting |
| `tests/simulation/test_engine.py` | 21 | Factory size, reproducibility, schema conformance, hidden-truth isolation, every scenario, outage, buffering and flush, isolation, unreachable commands |
| `tests/evaluation/test_models.py` | 13 | Window coverage, median robustness, detectors, hybrid, classifier determinism, grouped split, rules, recommendations, metrics |
| `tests/integration/test_api.py` | 11 | Endpoints, 404 handling, authorisation responses, incident approval, WebSocket |
| `tests/integration/test_live_stack.py` | 4 | All devices through the broker, persistence, command round trip, malformed messages |
| **Total** | **101** | |

Representative unit tests include:

- `test_same_seed_is_byte_identical`: two runs with seed 7 produce identical serialised output, and a run with seed 8 does not.
- `test_twin_tracks_gaps_duplicates_and_order`: sequences 1, 1, 5, 3 give one duplicate, four gaps (the missing sequence 0 before the first message, and 2 to 4 at the jump to 5) and one out-of-order message, and the reported value stays at sequence 5's.
- `test_low_confidence_waits_for_human_and_sends_nothing`: a 0.5-confidence diagnosis sends no command until approved.
- `test_out_of_limit_is_denied_even_with_human_approval`: speed 5.0 is denied despite a named approver.
- `test_edge_ignores_single_sensor_evidence`: one sensor at 200 °C causes no edge action.
- `test_sensor_noise_statistics_and_resolution`: 5,000 readings have the configured mean and standard deviation.

## 10.3 Integration Testing

The API tests construct a `Runtime` with `connect=False` and a missing model path, so the API runs in rule-based mode without a broker or database. They verify that:

- the overview reports 100 devices and 300 sensors;
- unknown resources return 404;
- a high-impact command without an approver returns 403, as does an unattributed low-impact command;
- an out-of-limit command returns 422 even when approved;
- an approved command updates the twin's desired state;
- incident approval, double approval (409) and empty operator names (422) behave correctly;
- scenario start returns 503 without a broker;
- the WebSocket pushes a snapshot.

Closed-loop tests in `test_central.py` connect the simulator directly to the pipeline. With no broker in between, they verify end-to-end behaviour: overheating is detected and mitigated without failure, sensor manipulation is caught without any machine action, a frozen sensor is caught, a normal run raises no integrity findings, and disconnection keeps edge protection while backfilling the twin.

## 10.4 MQTT Integration Testing

`test_live_stack.py` starts a real `Runtime` connected to Mosquitto and PostgreSQL, and runs a `LiveRunner` simulator at 20× speed for 45 seconds in a background thread. Its MQTT tests check that:

- all 100 devices report through the broker with no invalid messages;
- a `set_speed 0.7` command sent by the pipeline reaches the simulated conveyor, which then reports a speed below 80% of rated;
- a message for an unknown device and a non-JSON payload published directly to the broker are both counted as invalid.

## 10.5 Database Integration Testing

The same live-stack fixture checks persistence: more than 100 telemetry rows are written, and the `devices` table holds exactly 100 registered devices. The migration was also verified with `alembic current`, which reported revision `0001 (head)` on a clean copy of the project.

## 10.6 AI Model Testing

Model behaviour is tested in two ways. Unit tests in `test_models.py` check mechanisms on synthetic Gaussian data:

- each detector separates data shifted by 8 standard deviations, alarming on more than 90% of shifted points and fewer than 10% of unshifted ones;
- the hybrid score equals the element-wise maximum of its parts;
- the classifier is reproducible for a fixed seed;
- `GroupShuffleSplit` leaves no group on both sides of the split;
- a diagnosed fault never receives a "routine" recommendation.

The models' *performance* is evaluated separately on held-out simulated runs (Chapter 7). This separation is deliberate: unit tests should not depend on the exact results of a trained model.

## 10.7 Fault Scenario Testing

Every scenario in the catalogue is run for 1,800 simulated seconds by a parametrised test, which checks that each completes and produces messages. Dedicated tests check the physical effect of each fault:

- **Bearing degradation**: vibration doubles and bearing temperature rises by more than 10 K relative to a healthy motor, and the motor seizes by 3,600 s without protection.
- **Overheating**: the motor fails without the edge; with the edge, it is derated to 0.6 and stays below 105 °C.
- **Edge on a worn bearing**: the edge stops the motor before seizure.
- **Pump leak**: discharge pressure falls below 80% of the healthy pump's, delivered flow falls and suction flow rises.
- **Gateway outage**: messages are lost only on the failed gateway, which then recovers.
- **Link loss**: messages are buffered and flushed with complete per-device sequences and no overflow.
- **Network degradation**: packets are lost.
- **Central disconnection**: a command is rejected as unreachable.

## 10.8 Frontend Verification

The dashboard has **no automated tests**. It was verified by static checks, a production build and manual inspection in Chrome against the live stack:

- **First pass (before publication):** four pages were opened (Overview, 3D Factory, Recovery Operations and Telemetry). An overheating incident was approved through the user interface, the theme was switched, and a run reset and sensor quarantine were triggered.
- **Second pass (after publication):** all twelve pages were opened with live data. A machine was selected in the 3D view, which showed its readings in the side panel, and the camera was orbited by dragging. Browser console errors were checked on each page.
- **Reset behaviour:** after a simulator reset, the API returned telemetry history starting again at simulation time 0, with zero integrity findings and an empty quarantine list. This confirmed the fix that clears charts and logs on reset.
- **Defects found:** the second pass found three defects. The maintenance page showed "routine monitoring" for a machine with a diagnosed leak (Section 7.9). The network page showed stale counters after a reset (Section 6.8). The settings page capitalised the API address. All three were fixed in the working tree, and regression tests were added for the first two. The development-mode React warning from the 3D labels (Section 9.11) remains.

Manual checks are weaker evidence than automated tests. They show that each page worked once with real data, not that it keeps working.

## 10.9 Build and Static Analysis

On 16 November 2026, with the working tree described in Section 10.10, every check passed (@tab:static).

Table: Static analysis and build results, 16 November 2026 {#tab:static}

| Check | Command | Result |
| --- | --- | --- |
| Python lint and format | `ruff check .` | All checks passed |
| Python types | `mypy` (58 source files) | No issues found |
| TypeScript lint | `eslint src` | No problems |
| TypeScript types | `tsc --noEmit` | No errors |
| Dashboard build | `next build` | Compiled successfully; 13 routes prerendered |

## 10.10 Test Results

The full test suite was run on 16 November 2026 with Mosquitto and PostgreSQL running under Docker Compose. The output is saved in `docs/project-report/evidence/test-run-2026-11-16.txt`:

**101 passed, 0 failed, 0 skipped**, in 124.7 seconds, including the 4 live-stack integration tests.

One deprecation warning was reported by Starlette's test client, which recommends a different HTTP client package. It does not affect results.

The tested working tree is commit `118e362` (the published initial commit) plus five uncommitted modifications made during post-publication verification:

- the twin counter reset;
- the "diagnosed fault is never routine" recommendation rule;
- the settings-page label fix;
- the two regression tests for the first two.

The earlier verification before publication ran 99 tests (95 in-process and 4 live-stack), all passing, both in the working directory and in a clean copy of the project. After publication, the repository was cloned from GitHub into a fresh environment, and the 95 in-process tests passed there as well. The two regression tests are the difference between 99 and 101.

**Not covered by automated tests:**

- the dashboard (manual checks only);
- `scripts/dev.ps1`, which was run manually once with a successful result;
- behaviour at 500 devices beyond construction of the layout;
- long-duration live operation;
- broker or database failure in the middle of a live run.
