# Build plans (historical)

These are the phased build specifications written while the system was being built — design
intent, function signatures, and acceptance criteria for each component.

**They are kept for reference and are not maintained.** The system has since shipped in full, and
some early plans (e.g. `00-overview.md` and `03-storage-service.md`) describe an earlier design
(fewer artifacts, no Fargate/SQS/reskin). For the current system, use:

- [README](../README.md) — overview, setup, and the architecture diagram
- [docs/architecture.md](../docs/architecture.md) — how jobs run (the two async lanes + lifecycle)
- [docs/endpoints.md](../docs/endpoints.md) — the API

Within this folder, the later plans (18 Codex support, 21 implement agent, 22 ECS/Fargate) are the
closest to the shipped system.
