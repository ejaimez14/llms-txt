# CLAUDE.md — Agent Guidelines

This file is loaded automatically by every Claude Code agent working in this repo. Follow these conventions for all code changes across all phases.

---

## Project Structure

```
src/
  handler.py          # FastAPI app + Lambda entrypoint
  constants.py
  models.py
  prompts.py
  agents/
    crawler.py
    ui_planner.py
    search.py
  services/
    storage.py
    embeddings.py
    pinecone_client.py
    llm.py
    hooks.py
    logger.py
infra/
  main.tf
  variables.tf
  outputs.tf
  providers.tf
  modules/
    s3/
    dynamodb/
    secrets/
    lambda/         # Phase 5
    api_gateway/    # Phase 5
    observability/  # Phase 5
    cloudfront/     # Phase 5
tests/
plans/              # Read-only — implementation specs
```

---

## Python

- **Formatter/linter:** ruff. Run `make lint` and `make format` before opening a PR.
- **Python version:** 3.11+. Use `str | None` union syntax, not `Optional[str]`.
- **Type hints:** required on every function signature — parameters and return type.
- **Comments:** add only when necessary — brief, useful, and explaining WHY not WHAT. Never restate what the code already says.
- **Docstrings:** add for non-trivial functions — one concise line describing purpose and any non-obvious behavior. Skip for simple getters or wrappers where the signature is self-explanatory.
- **Abstractions:** only introduce what the current task requires. Three similar lines is better than a premature abstraction.
- **Error handling:** one `try/except` clause per function maximum — no nested try/except blocks. Catch the narrowest exception type possible. Only handle errors at system boundaries (external API calls, boto3 calls). In the except block, log with `logger.error` and re-raise — never swallow exceptions silently.
- **Logging levels:** `logger.info` for normal operational events. `logger.error` for caught exceptions that are re-raised. Log a structured dict: `{"event": "<name>", "error": str(exc)}`.
- **Imports:** always at the top of the file. Never inside functions or conditionals.
- **Internal functions:** prefix with `_` to signal they are private to the module. Place all internal functions at the bottom of the file, after public functions.
- **File organization:** group related functions with a section comment (e.g. `# --- S3 Operations ---`, `# --- DynamoDB Operations ---`, `# --- Internal ---`). Use these sparingly — only when the file has meaningfully distinct groups.
- **Variable names:** must reflect what they hold — no single-letter names, no generic names like `data`, `result`, `item` unless the context makes the meaning unambiguous.
- **Env vars:** always read via `os.environ["VAR"]` (not `.get()`). If a required var is missing, a `KeyError` is the correct failure mode — no fallback defaults.
- **boto3 clients:** instantiate at module level so they are reused across invocations. Do not instantiate inside functions unless the client config varies per call.

---

## Code Quality

These apply to every file, every agent, every phase. Correctness is the floor — quality is the standard.

- **Functions do one thing.** If a function is doing two distinct things, split it. A function that fetches and also transforms is two functions.
- **Keep functions concise.** If a function is getting long, it's a signal to split — not a requirement, but a smell worth investigating.
- **Clarity over cleverness.** If a reader would pause to figure out what a line does, rewrite it. Readable code is not slower code.
- **No dead code.** No commented-out blocks, unused variables, unreachable branches, or leftover debug statements.
- **Consistent patterns within a file.** If you handle errors one way in one function, handle them the same way in the next. Inconsistency forces readers to re-learn the pattern.
- **Top-to-bottom readability.** A file should read like a document — public interface at the top, helpers and internals at the bottom. A reader shouldn't need to jump around to follow the logic.
- **Don't optimise prematurely.** Write the clear version first. Only add complexity if there is a concrete, demonstrated reason.

---

## Terraform

- All resources in `us-east-1`.
- Use `PAY_PER_REQUEST` billing for DynamoDB — no provisioned capacity.
- No hardcoded account IDs, bucket names, or ARNs in module code — pass everything via variables.
- Root `main.tf` wires modules together; modules own their resources.
- Sensitive variables (API keys, passwords) must be marked `sensitive = true`.
- `terraform.tfvars` is gitignored — never commit it. Provider config lives in `providers.tf`, not `main.tf`.

---

## Testing

- **Framework:** pytest.
- **AWS mocking:** `moto` — import and activate the relevant decorators (`@mock_s3`, `@mock_dynamodb`, etc.) per test file.
- **External API mocking:** `pytest-mock` (`mocker` fixture).
- **Bedrock:** always mock — never call real Bedrock in tests.
- **Pinecone:** always mock — never call real Pinecone in tests.
- **File:** one test file per source module, named `tests/test_<module>.py`.
- **Test naming:** `test_<what>_<expected_outcome>` — e.g. `test_create_job_initializes_all_artifacts`.
- Cover every acceptance criterion listed in the plan for the component.

---

## Git & PRs

- **Branch naming:** `ejaimez/<feature-name>` — descriptive, no plan numbers. e.g. `ejaimez/terraform-storage`, `ejaimez/storage-service`.
- **Commits:** brief, accurate, imperative phrase — a few words that clearly describe what changed. If two distinct things were changed, separate them with ` ; ` (e.g. `Extract providers.tf ; remove tfvars example`). Never include more than two things in a single commit message — split into separate commits if needed.
- **PRs:** always open as **draft** — owner reviews before marking ready.
- **Base branch:** `main`. Do not push directly to `main`.
- **PR title format:** `[<short-feature-word>] - <Brief Title With Each First Letter Capitalized>`
  - e.g. `[Tooling] - Project Setup With Pyproject And Makefile`
  - e.g. `[Infra] - Terraform Storage Modules For S3 And DynamoDB`
- **PR body format:**

  ```
  ## What
  - <brief bullet points describing the changes made>

  ## Why
  - <brief bullet points explaining why the changes are needed>

  ## Tested By
  - <brief bullet points describing how changes were verified — test cases, manual steps, or make targets>
  ```

  Keep each section brief but useful — written for someone trying to understand the PR at a glance without reading every line of code.

---

## Self-Review Checklist

Before opening a PR, review the code critically for quality — not just correctness:

- [ ] All acceptance criteria from the plan are met
- [ ] `make lint` passes with no errors
- [ ] `make test` passes (if tests exist for this component)
- [ ] No hardcoded secrets, bucket names, table names, or ARNs
- [ ] No unused imports or variables
- [ ] All imports are at the top of the file
- [ ] Internal/private functions are prefixed with `_`
- [ ] Variable names clearly reflect what they hold
- [ ] No repeated logic that could be extracted cleanly (but don't over-abstract)
- [ ] No nested try/except — one clause per function maximum
- [ ] Type hints present on all functions
- [ ] Docstrings present on non-trivial functions
- [ ] Code is easy to read top-to-bottom without needing to jump around
- [ ] New Terraform variables added to `variables.tf` with descriptions (Terraform components only)
- [ ] PR opened as draft with What, Why, and Tested By sections following the format in CLAUDE.md
