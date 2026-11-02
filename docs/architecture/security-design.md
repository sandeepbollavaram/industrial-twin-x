# Security Design

## Scope

This is a local research prototype. Attacks are scripted changes to simulator state, used to test detection. The project contains no real attack tooling.

## Implemented

| Control | Where | Behaviour |
| --- | --- | --- |
| Schema validation | `modules/telemetry/schema.py` | Rejects and counts malformed messages |
| Registry check | `modules/digital_twin/engine.py` | Rejects unknown devices |
| Sequence tracking | `modules/digital_twin/engine.py` | Counts gaps, duplicates and reordering |
| Sensor disagreement | `modules/cybersecurity/integrity.py` | Quarantines a sensor that departs from its peers |
| Frozen sensor | `modules/cybersecurity/integrity.py` | Quarantines a sensor that repeats exact values despite expected noise |
| Median and voting | Features and edge policy | One bad sensor cannot drive decisions |
| Device isolation | `isolate` command | Stops a device's telemetry; needs approval |
| Command authorization | `modules/recovery_engine/authorization.py` | Enforces human approval and confidence rules |
| Device-side limits | `simulation/actuators/limits.py` | Applies even if central logic is wrong |
| Audit trail | `recovery_audit` table | Records every incident transition |
| Network exposure | `docker-compose.yml` | Publishes ports on 127.0.0.1 only |
| Secrets | `.gitignore`, `.env.example` | `.env` is untracked; the example holds placeholders |

## Known gaps

These matter before any deployment beyond one local machine:

1. **The broker allows anonymous access** and has no TLS. Anything local can publish telemetry or commands. This is tolerated only because the port is bound to localhost.
2. **Messages are not signed.** A local publisher could forge a device's telemetry; only plausibility checks would notice.
3. **The API has no authentication.** The approver is a typed name, so the approval flow demonstrates policy and does not prove identity. CORS is not an access control.
4. **Coordinated manipulation of most sensors on a signal is not detected.** The checks assume a majority of sensors are honest.
5. **A slow bias below the tolerance is not detected**: 4 °C for temperatures, 0.6 mm/s for vibration.
6. **Quarantine is cleared only by recording a repair.**
7. **The audit log is append-only by convention**, not by database permission or hash chaining.
