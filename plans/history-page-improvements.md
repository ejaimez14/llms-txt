# Plan: History Page Improvements

Improve the **History** tab of the web UI (`src/index.html`) with richer filters, a clean dedicated
job-detail view, and clickable PR/preview links on implement jobs.

This is almost entirely a front-end change to the single static `src/index.html` (served from S3 via
CloudFront), plus one small backend tweak for Part C. **No Pinecone, no Fargate, no new infra.**

---

## Current state (what to build on)

- The UI is one self-contained `src/index.html` (inline CSS + JS; `marked.js` + `DOMPurify` already loaded).
  No framework or router.
- History tab markup: `#tab-history` contains `.history-controls` (one `#history-model-filter` select) and
  `#history-content`.
- JS flow (all in the inline `<script>`):
  - `loadHistory()` → `GET /api/jobs` → stores `allHistoryJobs` → `renderHistory(modelFilter)`.
  - `renderHistory(modelFilter)` builds a `.history-table`; each row has `data-jobId` and an on-click →
    `toggleHistoryRow(tr, job)`, which **expands an inline detail row** in the table and fetches artifact
    content via `buildArtifactDefsForJob(job)` + `callApi('/api/job/<id>/<path>')` + `buildArtifactCard(...)`.
  - Helpers to reuse: `buildArtifactDefsForJob(job)` (maps a job's artifact keys → fetch path/title/filename),
    `buildArtifactCard(title, content, filename)` (markdown card with Download), `statusBadge(status)`,
    `renderMarkdown(md)`, `callApi`, `escapeHtml`.
- `GET /api/jobs` returns lightweight records: `{ jobId, url, model, createdAt, status, artifacts }` where
  `artifacts` is `{ <key>: { status } }` only — `_slim_job` in `src/services/storage.py` strips everything
  but `status` (no `s3Key`, `error`, `prUrl`, `previewUrl`).
- Implement jobs (`type === "implement"`) carry a `prUrl` artifact whose full record holds `prUrl` and
  `previewUrl` (see `store_implement_result`); these are reachable via `GET /api/job/{id}/pr-url` or the full
  `GET /api/job?id=<id>` record, but **not** in the slimmed `/api/jobs` list.

---

## Part A — Richer History filters

Add two more client-side filters alongside the existing model filter. All filtering is in-memory over the
already-fetched `allHistoryJobs` — no refetch, no backend change.

1. **Status** — All / processing / complete / partial / failed (from `job.status`).
2. **Artifact present** — All / llms.txt / UI plan / report / comparison / PR
   (from the keys in `job.artifacts`: `llmsTxt`, `plan`, `report`, `comparison`, `prUrl`).
3. **Model** — keep the existing select.

Implementation:
- Add two `<select>`s to `.history-controls`, styled exactly like `#history-model-filter`. Give them ids
  `#history-status-filter` and `#history-artifact-filter`. Wire `change` listeners that call `renderHistory()`.
- Replace `renderHistory(modelFilter)` with a no-arg `renderHistory()` that reads all three selects and applies
  a combined predicate (logical AND) over `allHistoryJobs`. A job passes the artifact filter if the chosen
  artifact key exists in `job.artifacts`.
- Show a result count line (e.g. "Showing N of M jobs"). Keep the existing empty state when none match.

Acceptance: selecting any combination of model + status + artifact narrows the table instantly and correctly;
clearing all returns to "All".

---

## Part B — Dedicated job-detail view (replace inline expand)

Replace `toggleHistoryRow`'s cramped inline expansion with a clean, full-width detail **view**.

**Chosen approach: in-app hash-routed view** (recommended over a separate `job.html`, which would duplicate the
app shell/CSS). It reuses the existing design system and `marked.js`, and yields shareable, back-button-friendly
URLs.

Implementation:
- Add a hidden top-level `#job-detail` section (sibling of `.app-card`) with a "← Back to history" control.
- Clicking a history row sets `location.hash = '#job/' + job.jobId` (instead of calling `toggleHistoryRow`).
- Add a `hashchange` (and initial `load`) handler:
  - If hash matches `#job/<id>`: hide the tab UI (`.app-card`), show `#job-detail`, and render the job.
  - Otherwise: show the tab UI, hide `#job-detail`.
- Rendering the detail view:
  - Header: site URL, `model`, job `type`, `statusBadge(job.status)`, and created-at (localized).
  - Body: for each artifact from `buildArtifactDefsForJob(job)` that is complete, fetch via
    `GET /api/job/<id>/<path>` and render full-width with `buildArtifactCard(...)` (reuse it; the roomy layout
    comes from being outside the table). Show a tasteful per-artifact loading + error state.
  - Fetch the full job with `GET /api/job?id=<id>` (so you have `type` and, for Part C, the URLs) rather than
    relying only on the slimmed list record.
- Remove `toggleHistoryRow` (and its inline-detail CSS) once the routed view replaces it.

Acceptance: clicking a job opens a full-width detail view; Back (button or browser back) returns to the
filtered history; loading `/#job/<id>` directly deep-links to that job.

> Alternative (NOT chosen unless the reviewer prefers it): a separate `src/job.html` page reading `?id=<id>`.
> More literally a "new page" but duplicates the shell and needs its own CSS/JS bundle.

---

## Part C — Clickable PR / preview links on implement jobs

Surface the implement job's GitHub PR and live `/experimental` preview as clickable links, both in the history
list and the detail view.

- **Backend (`src/services/storage.py`, `_slim_job`):** keep `prUrl` and `previewUrl` on an artifact when
  present, in addition to `status`. Only implement jobs' `prUrl` artifact has them, so the payload stays tiny.
  ```python
  slim = {"status": artifact.get("status")}
  if "prUrl" in artifact:
      slim["prUrl"] = artifact["prUrl"]
  if "previewUrl" in artifact:
      slim["previewUrl"] = artifact["previewUrl"]
  ```
- **History list (UI):** in the artifact cell, when an artifact has a `prUrl`/`previewUrl`, render
  `<a href=... target="_blank" rel="noopener">PR ↗</a>` and `Preview ↗` (use the existing link styling) instead
  of just a status badge.
- **Detail view (UI):** show the same links prominently in the header for implement jobs.
- **Test:** extend the `list_jobs` test in `tests/test_storage.py` to assert `prUrl`/`previewUrl` survive
  `_slim_job` for an implement job (and that other jobs are unaffected).

Acceptance: an implement job in History shows clickable PR + Preview links that open in a new tab.

---

## Out of scope
- No search/Pinecone changes (metadata filters / "Option C" are a separate, deferred task).
- No new endpoints. No Fargate or implement-flow changes.

## Testing & rollout
- **Local:** `make lint` and `make test` (or `uv run pytest -q`) must pass. Render the History view (with each
  filter) and a job-detail view headless (Chrome `--headless --screenshot`) to confirm layout.
- **Deploy:** Part A & B are UI-only → `aws s3 cp src/index.html s3://<frontend-bucket>/index.html` +
  CloudFront invalidation. Part C also changes the Lambda (`_slim_job`) → `make build` + `make tf-apply` as well.
- **AWS validation:** load the History tab behind basic auth; exercise the three filters; open a job detail via
  `/#job/<id>`; confirm an implement job shows working PR + Preview links.

## Files touched
- `src/index.html` — filters (A), routed detail view (B), link rendering (C).
- `src/services/storage.py` — `_slim_job` keeps `prUrl`/`previewUrl` (C).
- `tests/test_storage.py` — `list_jobs` slimming assertion (C).

## PR
- One PR off `main`, opened as **draft**. Title: `[UI] - History Page Filters, Job Detail View, And PR Links`.
- Independent of any other open PR (touches `index.html` + `_slim_job` only).
