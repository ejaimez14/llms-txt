# Plan: Report/Compare Endpoint Improvements + UI Markdown Rendering

## Overview

Three connected improvements to the application API and frontend:

1. **Dual-model report trigger** -- `POST /report` currently accepts a `model` field and fires
   a single reporter agent. Change it to accept only a `url`, always launch two report jobs in
   parallel (one for `claude`, one for `openai`), and return both job IDs in the response.

2. **URL-only compare trigger** -- `POST /compare` currently requires two explicit job IDs.
   Change it to accept only a `url`, auto-locate the most recent completed report job for each
   model from DynamoDB, and pass those report artifacts into the compare agent. If either model
   is missing a completed report, return a clear 404 error.

3. **UI markdown rendering upgrade** -- The existing `renderMarkdown()` in `src/index.html` is
   a hand-rolled line-by-line parser that mishandles ordered lists, nested lists, and tables.
   Replace it with `marked.js` for correct CommonMark rendering with no additional CSS needed.

---

## Phase 1: Report Endpoint -- Dual-Model Trigger

### Current behavior

POST /report accepts { url, model } (see src/handler.py:146-156 and src/models.py:17-19).
It creates one job, calls _run_in_thread(run_reporter, job_id, req.url, req.model).
Response: { jobId, status } -- a single job ID.

run_reporter in src/agents/reporter.py:10-32 accepts (job_id, url, model), looks up
the site latestJobId via get_site(url), fetches the llms.txt artifact, and runs the LLM
agent. The model value flows to create_agent() in src/services/llm.py, which branches
on the string "claude" or "openai".

### Proposed changes

**src/models.py** -- Replace ReportRequest with a URL-only model (remove model field).

**src/handler.py** -- Rewrite the report endpoint to create two jobs and fire two threads:

- Generate two UUIDs: job_id_claude and job_id_openai.
- Call create_job twice -- once with ModelName.CLAUDE.value, once with ModelName.OPENAI.value.
- Call _run_in_thread twice -- once with each model value.
- Return { "jobIdClaude": job_id_claude, "jobIdOpenai": job_id_openai, "status": "processing" }.

No changes to run_reporter -- it already handles both models through create_agent().

**src/index.html** -- Update the Report tab:

- Remove the model select element from the report form (lines 373-378).
- Update the submit handler to read res.jobIdClaude and res.jobIdOpenai.
- Poll both jobs concurrently with Promise.all([pollJob(...), pollJob(...)]).
- Display two artifact cards: "Report -- Claude" and "Report -- OpenAI".

### Acceptance criteria

- POST /report with { "url": "https://example.com" } returns HTTP 202 with both
  jobIdClaude and jobIdOpenai in the response body.
- POST /report with an uncrawled URL returns HTTP 404.
- Two report jobs are created in DynamoDB with model values "claude" and "openai".
- _run_in_thread is called exactly twice.
- test_report_starts_reporter_and_returns_202 updated: assert call_count == 2
  and that both jobIdClaude and jobIdOpenai are in the response.
- test_report_returns_404_if_not_crawled continues to pass (omit model from request body).

---

## Phase 2: Compare Endpoint -- URL-Only Input

### Current behavior

POST /compare accepts { job_id_a, job_id_b, model } (see src/handler.py:159-187
and src/models.py:22-25). It validates both jobs exist and are COMPLETE, creates a compare
job, and calls _run_in_thread(run_comparer, job_id, req.job_id_a, req.job_id_b, req.model).

run_comparer in src/agents/comparer.py:10-36 fetches ArtifactType.LLMS_TXT from both
source jobs (lines 15-16) and runs the compare agent.

### Proposed changes

**src/models.py** -- Replace CompareRequest with a URL-only model:

```python
class CompareRequest(BaseModel):
    url: str
```

**src/handler.py** -- Rewrite the compare endpoint:

1. Verify get_site(req.url) exists; return HTTP 404 if not.
2. Call get_latest_report_job_by_model(req.url) to get
   { ModelName.CLAUDE: id_or_None, ModelName.OPENAI: id_or_None }.
3. Return HTTP 404 "No completed claude report found for {url}. Run POST /report first."
   if claude is None.
4. Return HTTP 404 "No completed openai report found for {url}. Run POST /report first."
   if openai is None.
5. Create the compare job with ModelName.CLAUDE.value as the runner model.
6. Pass the two report job IDs into _run_in_thread(run_comparer, ...).
7. Return { "jobId": job_id, "status": "processing" }.

**src/agents/comparer.py** -- Change lines 15-16 to fetch ArtifactType.REPORT instead
of ArtifactType.LLMS_TXT. Update the fail_artifact message on lines 18-23 to say
"report content unavailable" rather than "llms.txt content unavailable".
No signature changes.

**src/prompts.py** -- Optional: update the phrase "llms.txt outputs" to "reports" in
_build_compare_message (line 209) for accuracy. COMPARE_SYSTEM_PROMPT is unchanged.

**src/index.html** -- Update the Compare tab:

- Replace the two job-ID text inputs and the model select (lines 393-408) with a single
  URL text input labeled "Website URL".
- Update the submit handler to call POST /compare with { url } only.
- The existing error display logic already surfaces backend 404 detail strings correctly.

### DynamoDB access pattern

The jobs table has GSI url-createdAt-index (hash: url, range: createdAt, projection: ALL)
-- see infra/modules/dynamodb/main.tf:23-28. The existing list_jobs_for_url() in
src/services/storage.py:234-249 queries this GSI with ScanIndexForward=False, returning
all jobs for a URL newest-first with all attributes projected.

Add a new public function get_latest_report_job_by_model to src/services/storage.py:

```python
def get_latest_report_job_by_model(url: str) -> dict[ModelName, str | None]:
```

Implementation:

1. Call list_jobs_for_url(url) -- already handles GSI pagination correctly.
2. Initialize result = { ModelName.CLAUDE: None, ModelName.OPENAI: None }.
3. Iterate results (newest-first); for each item where item["type"] == JobType.REPORT
   and item["status"] == JobStatus.COMPLETE, set the matching ModelName key if not set.
4. Break early once both values are non-None.
5. Return result.

No new GSI is needed. The projected ALL attributes include type, status, and model.
Per-URL job counts are small (tens of items), so in-memory filtering after a bounded
GSI query is correct and efficient.

Place this function in the # --- DynamoDB Operations --- section of src/services/storage.py,
above the # --- Sites Table Operations --- section. It is public (no _ prefix) since
handler.py calls it directly.

### Acceptance criteria

- POST /compare with { "url": "..." } when both models have completed reports returns
  HTTP 202 with a jobId.
- Returns HTTP 404 naming claude when the claude report is missing.
- Returns HTTP 404 naming openai when the openai report is missing.
- Returns HTTP 404 when the URL has never been crawled.
- get_latest_report_job_by_model returns the most recent complete report per model
  when multiple report jobs exist for a URL.
- run_comparer fetches ArtifactType.REPORT content, not ArtifactType.LLMS_TXT.
- tests/test_handler.py: update all test_compare_* tests to URL-only input; add
  test_compare_returns_404_when_claude_report_missing and
  test_compare_returns_404_when_openai_report_missing.
- tests/test_storage.py: add test_get_latest_report_job_by_model_returns_correct_jobs
  and test_get_latest_report_job_by_model_returns_none_when_missing.

---

## Phase 3: UI Markdown Rendering

### Current behavior

src/index.html contains a hand-rolled renderMarkdown() function (lines 480-621) and
an applyInline() helper (lines 623-634). The .markdown-body CSS block (lines 187-201)
provides adequate styles for headings, code, tables, lists, blockquotes, and links.

Known parser deficiencies:

- Ordered lists (1. item) are not handled -- fall through to plain p tags.
- Nested lists (indented - sub-item) are not handled.
- Table-closing logic (lines 534-556) walks backwards through the output array to wrap
  rows -- complex, fragile, easy to break with edge cases.
- Heading detection only handles H1-H3; H4-H6 become plain paragraphs.
- Blockquote detection relies on HTML-escaped form &gt; (line 567) -- fragile if
  the escaping order changes.

### Recommended approach (with brief rationale over alternatives)

**Recommended: drop-in replacement using marked.js + DOMPurify (CDN).**

Replace renderMarkdown() and applyInline() with a two-line wrapper around marked.parse().
Load marked.js and DOMPurify from CDN script tags in the document head. The existing
.markdown-body CSS already covers all required styles -- no additional CSS needed.
The result is correct CommonMark rendering (ordered lists, nested lists, all heading
levels, fenced code blocks) with zero maintenance burden.

**Alternative A -- server-side conversion to HTML in Lambda:** Rejected. Adding a Python
markdown library (e.g., mistune) to the Lambda package couples a presentation concern to
the backend, increases deployment weight, and adds a dependency to maintain. The artifact
endpoints correctly return raw markdown -- the frontend should own rendering.

**Alternative B -- improving the existing CSS:** Rejected as the wrong target. The CSS is
already adequate. The rendering defects are in the parser logic, not the styles. Better
CSS cannot fix missing ordered list support or the fragile table parser.

**XSS safety:** marked.js does not sanitize by default. The existing pattern of
HTML-pre-escaping input before calling renderMarkdown must be removed -- marked expects
raw markdown, and pre-escaping causes double-escaping. Instead, pipe marked.parse(md)
through DOMPurify.sanitize() before assigning to innerHTML. This is the standard safe
pattern for client-side markdown rendering with untrusted content.

### Files to change

src/index.html only -- no Python changes in Phase 3.

1. Add two CDN script tags in head before /head:
   - https://cdn.jsdelivr.net/npm/marked/marked.min.js
   - https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js

2. Replace renderMarkdown (lines 480-621) and applyInline (lines 623-634) with:
   ```js
   function renderMarkdown(md) {
     return DOMPurify.sanitize(marked.parse(md))
   }
   ```

3. The call body.innerHTML = renderMarkdown(content) in buildArtifactCard (line 684)
   requires no changes.

4. Remove the HTML pre-escaping block from the old renderMarkdown body (the .replace
   calls for &amp;, &lt;, &gt;) -- it is no longer needed.

No changes to .markdown-body CSS.

### Acceptance criteria

- Report and comparison artifacts render with correct headings (H1-H6), bold, italic,
  inline code, fenced code blocks, ordered and unordered lists (including nested),
  tables, and blockquotes.
- renderMarkdown() calls marked.parse() and returns DOMPurify-sanitized output.
- The hand-rolled parser and applyInline helper are fully deleted.
- A script tag with alert(1) in crawled content does not execute.
- The PR body notes that production hardening would add SRI hashes to CDN script tags.

---

## Test Loop

The implementing agent must run three validation stages in order before opening the PR for review.
All three must pass — do not skip a stage or proceed to the next if the current stage fails.

### Stage 1: Local API (pytest + live server)

1. Run `make test` — all tests must pass with no errors.
2. Start the FastAPI app locally: `uvicorn src.handler:app --reload`.
3. Exercise the changed endpoints manually using `curl` or the browser UI:
   - POST /report with `{ "url": "<a previously crawled URL>" }` → verify HTTP 202 and both
     `jobIdClaude` and `jobIdOpenai` appear in the response.
   - POST /compare with `{ "url": "<same URL>" }` → verify HTTP 202 with a `jobId`.
   - Verify a missing-report 404 returns the correct model name in the error message.
   - Open the UI in the browser and confirm the Report tab renders two artifact cards and that
     markdown renders correctly (headings, lists, code blocks, tables).
4. Stop the local server.

Stage 1 passes when all tests are green and all manual checks above produce the expected results.

### Stage 2: Docker image (local container run)

1. Build the Docker image: `make docker-build` (or `docker build -t llms-txt-agent .`).
2. Run the container locally, wiring in the required env vars from `.env` or `~/.aws`:
   ```
   docker run --rm \
     -e TABLE=... -e SITES_TABLE=... -e BUCKET=... \
     -e PINECONE_INDEX=... -e AWS_DEFAULT_REGION=us-east-1 \
     -e ANTHROPIC_API_KEY=... -e PINECONE_API_KEY=... \
     -p 8000:8000 llms-txt-agent
   ```
3. Repeat the same endpoint checks from Stage 1 against `http://localhost:8000`.
4. Confirm no import errors or missing-dependency failures appear in container logs.

Stage 2 passes when the container starts cleanly and all endpoint checks pass identically to Stage 1.

### Stage 3: AWS deployment (staging stack)

1. Build the Lambda zip: `make build`.
2. Deploy the updated Lambda: `make deploy` (or `aws lambda update-function-code ...`).
3. Wait for the update to propagate: `aws lambda wait function-updated --function-name <name>`.
4. Test against the deployed API Gateway URL:
   - Repeat the same endpoint checks from Stage 1 against the live API Gateway URL.
   - Verify CloudWatch logs show the correct structured log events (`report_started`,
     `report_completed`, `compare_started`, `compare_completed`) with no errors.
5. Confirm the UI served from S3/CloudFront renders markdown correctly on a real report artifact.

Stage 3 passes when all endpoint checks pass on AWS and CloudWatch shows clean logs with no errors.

Only after all three stages pass should the agent open the draft PR and notify the user for review.

---

## Guidance for the Implementing Agent

### CLAUDE.md sections that apply

**Python (all phases with Python changes):**

- Type hints on every function parameter and return type; use str | None not Optional[str].
- logger.error in every except block (always before re-raising);
  logger.info for all other operational events. Never swap them.
- One try/except per function maximum; no nesting.
- Imports at the top of the file; never inside functions.
- Internal functions prefixed _, placed after public functions.
- Enum keys: use ModelName.CLAUDE / ModelName.OPENAI as dict keys -- not raw strings.
- No dead code: remove the old model field from ReportRequest and the old job_id_a,
  job_id_b, model fields from CompareRequest entirely.

**Testing (Phases 1 and 2):**

- moto (mock_aws) for DynamoDB; pytest-mock for external calls.
- test_<what>_<expected_outcome> naming.
- Cover every acceptance criterion with at least one test.
- New env vars or SDK stubs go in tests/conftest.py.

**Git and PRs:** draft PR, [Feature] - Title format, What/Why/Tested By body.

### Non-obvious constraints

1. **create_job serializes model as a string** -- storage.py:104 puts the model value
   directly into a DynamoDB item. boto3 cannot serialize Python Enum objects. Pass
   ModelName.CLAUDE.value (the string "claude") not the enum member.

2. **run_reporter and run_comparer accept model: str** -- both function signatures take
   a plain string. Pass .value from the handler, not the enum member.

3. **Dual-job response shape** -- The new POST /report response changes from
   { jobId, status } to { jobIdClaude, jobIdOpenai, status }. Update both the API
   handler and the frontend poll/display logic. The History tab buildArtifactDefsForJob
   filters by artifact key presence and requires no changes.

4. **run_comparer fetches ArtifactType.LLMS_TXT today** -- after Phase 2 it will receive
   report job IDs and must fetch ArtifactType.REPORT. This is the only required change
   in src/agents/comparer.py. No signature changes.

5. **Compare job URL field** -- the current handler uses job_a["url"] (line 185) to
   record the compare job URL. In the new flow, use req.url directly -- it is already
   validated by the get_site() check at the top of the endpoint.

6. **get_latest_report_job_by_model return dict uses Enum keys** -- the dict must be
   keyed by ModelName.CLAUDE and ModelName.OPENAI (enum members), not raw strings.
   The handler indexes the result with enum members. This satisfies the CLAUDE.md
   enum-keys convention.

7. **Test table setup for storage tests** -- tests/test_handler.py (lines 35-44) creates
   the jobs table with the url-createdAt-index GSI. New tests in tests/test_storage.py
   for get_latest_report_job_by_model need the same table definition. Follow the same
   fixture pattern -- do not share the fixture from test_handler.py; duplicate it in
   a local aws_env fixture within test_storage.py.

8. **ArtifactStatus.COMPLETE comparison** -- storage.py:66 compares
   artifact.get("status") against ArtifactStatus.COMPLETE. Because ArtifactStatus
   extends str, this equality works when DynamoDB returns the stored string "complete".
   No changes needed here.

9. **marked.js v5+ API** -- Use marked.parse(md) explicitly. The marked(md)
   function-call alias still works but emits a deprecation warning in v5+.

10. **CDN script placement** -- The marked and DOMPurify script tags must appear before
    the inline script block at the bottom of body. Placing them in head is correct.
    Do not use async or defer since the inline script depends on them synchronously.

### Suggested PR split

All three phases have no runtime dependencies on each other and fit in one PR on branch
ejaimez/report-compare-ui-improvements.

If scope is too large for a single review cycle, split as:

- **PR A:** Phases 1 and 2 -- backend changes only (handler.py, storage.py, models.py,
  comparer.py, optionally prompts.py, all updated tests). Phase 1 frontend changes can
  be included here or deferred to PR B.
- **PR B:** Phase 3 -- src/index.html only, no Python changes.

If Phase 1 frontend changes are included in PR A, PR A must land before PR B.
If deferred to PR B, the two PRs are fully independent.
