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
  terraform.tfvars.example
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
- **Error handling:** one `try/except` clause per function maximum — no nested try/except blocks. Catch the narrowest exception type possible. Only handle errors at system boundaries (external API calls, boto3 calls).
- **Imports:** always at the top of the file. Never inside functions or conditionals.
- **Internal functions:** prefix with `_` to signal they are private to the module. Place all internal functions at the bottom of the file, after public functions.
- **File organization:** group related functions with a section comment (e.g. `# --- S3 Operations ---`, `# --- DynamoDB Operations ---`, `# --- Internal ---`). Use these sparingly — only when the file has meaningfully distinct groups.
- **Variable names:** must reflect what they hold — no single-letter names, no generic names like `data`, `result`, `item` unless the context makes the meaning unambiguous.
- **Env vars:** always read via `os.environ["VAR"]` (not `.get()`). If a required var is missing, a `KeyError` is the correct failure mode — no fallback defaults.
- **boto3 clients:** instantiate at module level so they are reused across invocations. Do not instantiate inside functions unless the client config varies per call.

---

## Terraform

- All resources in `us-east-1`.
- Use `PAY_PER_REQUEST` billing for DynamoDB — no provisioned capacity.
- No hardcoded account IDs, bucket names, or ARNs in module code — pass everything via variables.
- Root `main.tf` wires modules together; modules own their resources.
- Sensitive variables (API keys, passwords) must be marked `sensitive = true`.
- `terraform.tfvars` is gitignored. Always keep `terraform.tfvars.example` up to date with all variables (empty values only).

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
- **Commits:** one logical commit per component. Message format: imperative sentence describing what changed and why, 72 chars max.
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
- [ ] `terraform.tfvars.example` updated if new variables were added (Terraform components only)
- [ ] PR opened as draft with What, Why, and Tested By sections following the format in CLAUDE.md
