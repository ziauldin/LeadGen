# 0001: One FastAPI modular monolith with Celery workers

**Status:** accepted

**Context.** A small team needs to ship quickly and run reliably on one platform (Railway). Sending, sequences, inbound processing and enrichment share most of their data.

**Decision.** There is one API codebase (`services/api`), organised by domain under `app/services/*`. The same image runs three ways:
- as the HTTP API
- as a Celery worker consuming the `default`, `sending`, `inbound` and `enrichment` queues
- as a single beat scheduler

Queues isolate slow work, such as enrichment, from time-sensitive work, such as sending.

**Consequences.**
- One deploy and one migration path.
- Queues and worker replicas can be scaled independently later.
- Domain boundaries are enforced by convention and review, not by the network.
