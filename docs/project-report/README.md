# Project Report Structure

Skeleton for the final B.Tech report. Sections marked "To write" are not drafted. All results must be labelled as simulation results; the project has not been validated on real hardware.

| # | Section | Status and source material |
| --- | --- | --- |
| 1 | Abstract | To write, last |
| 2 | Introduction | To write |
| 3 | Literature Review | To write. See the rule on references below |
| 4 | Problem Statement | To write |
| 5 | Existing System | To write |
| 6 | Proposed System | Draw from `docs/architecture/system-architecture.md` |
| 7 | Requirements and Architecture | Draw from `docs/architecture/` |
| 8 | Simulation Methodology | Draw from `simulation-design.md` |
| 9 | AI Implementation | Draw from `ai-design.md` and ADR-005, ADR-006 |
| 10 | Resilience and Cybersecurity | Draw from `security-design.md` and the experiment results |
| 11 | Implementation | Draw from the code and `deployment-guide.md` |
| 12 | Testing and Results | Draw from `research/reports/` and the test suite |
| 13 | Conclusion | To write |
| 14 | Future Scope | Real hardware validation, OPC UA, broker authentication, 500-device benchmark |
| 15 | References | See below |
| 16 | Appendices | Configuration, schemas, seeds |

## References

No academic papers are cited yet, because none have been read and verified for this project. Add a source only after confirming it exists and says what is claimed.

Technical documentation, access date 2026-11-02:

- SimPy: https://simpy.readthedocs.io/
- Eclipse Mosquitto: https://mosquitto.org/documentation/
- Eclipse Paho Python: https://eclipse.dev/paho/files/paho.mqtt.python/html/
- Eclipse Ditto, consulted for twin concepts: https://eclipse.dev/ditto/
- scikit-learn: https://scikit-learn.org/stable/
- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy: https://docs.sqlalchemy.org/
- Next.js: https://nextjs.org/docs
- React Three Fiber: https://r3f.docs.pmnd.rs/

These URLs were recorded from knowledge of the projects and were not fetched during this session. Open each before citing it.
