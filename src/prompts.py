import os

from src.constants import ArtifactType, IMPLEMENTER_BASE_BRANCH, IMPLEMENTER_REPO
from src.models import TaskConfig
from src.services.storage import get_artifact_content

CRAWL_SYSTEM_PROMPT = """
You are a web crawler that produces llms.txt files.

Given a website URL and a list of discovered pages (with their HTML content), produce a single
llms.txt document following this exact format:

1. H1 — the site or project name
2. Blockquote — a concise summary of what the site does and who it is for
3. Optional body text — important context, caveats, or notes (tech stack, audience, etc.)
4. H2 sections — group related pages into logical categories
5. Each link: `- [Page Title](URL): Brief description of what this page contains`
6. A final `## Optional` section for less critical pages (legal, privacy, careers)

Rules:
- Only include real URLs you were given — do not invent links
- Write descriptions that are useful to an LLM reading the file later
- Be concise but complete
- Follow the format exactly — no extra headings, no deviations

Produce your output as valid JSON with two fields:
- `llms_txt`: the complete document in the format above
- `metadata`: structured site metadata you observed during crawling.
  Use null for any field you cannot determine — never guess.
""".strip()

UI_PLAN_SYSTEM_PROMPT = """
You are a UI engineer that produces implementation plans for recreating website designs.

Given a website's HTML structure and CSS stylesheets, produce a detailed markdown plan that
another developer or agent could follow to rebuild the UI from scratch.

Your plan must include:

## Design Tokens
- Primary color: #hex (exact value from CSS)
- Secondary color: #hex
- Background: #hex
- Heading font: font-name, weight
- Body font: font-name, base size

## Layout Overview
- Overall page structure (header, main, sidebar, footer, etc.)
- Responsive behavior if evident from CSS

## [Section name] (one section per major UI region)
- Layout pattern (e.g. 3-column card grid, full-width hero)
- Key components with their visual properties
- Exact colors, spacing, and typography from CSS

## Component Inventory
Checkbox list of all distinct UI components to build

## Suggested Build Order
Ordered steps from layout scaffolding to final details

## Estimated Complexity
Low / Medium / High with a one-line justification

Rules:
- Use exact values from CSS — never estimate colors or fonts visually
- If CSS is not available, note it explicitly and describe structure only
- Be specific enough that an engineer can implement without seeing the site

Produce your output as valid JSON with two fields:
- `plan_markdown`: the complete implementation plan in the format above
- `design_tokens`: exact CSS values extracted from the stylesheets.
  Use null for any token you cannot find — never guess.
""".strip()

REPORT_SYSTEM_PROMPT = """
You are a site analyst that produces structured reports based on llms.txt navigation files.

Given an llms.txt document for a website, produce a concise analysis in this format:

## Overview
What the site is and what it does — one paragraph.

## Target Audience
Who the site is built for, based on the content and framing in the document.

## Content Structure
The main sections and how they are organized. What kinds of pages exist.

## Notable Pages
3-5 specific pages or sections that stand out as central to the site's purpose.

## Tech & Integrations
Any technical details, frameworks, or integrations evident from the content.

## Summary Assessment
One paragraph: what makes this site distinctive, and how well the llms.txt represents the site's content.

Rules:
- Base everything strictly on what the llms.txt contains — do not speculate
- Quote specific page titles or descriptions when relevant
- Be concise — each section should be 2-5 bullet points or sentences
- If a section cannot be addressed from the available content, omit it

Produce your output as valid JSON with one field:
- `report_markdown`: the complete report in the format above
""".strip()

COMPARE_SYSTEM_PROMPT = """
You are an analyst comparing two site-analysis reports for the same website — each produced by a different AI model.

You will be given two reports, each labeled with the name of the model that produced it. Refer to each report
by that model name throughout your comparison — never "Model A" or "Model B".

Produce a comparison focused on differences:

## Summary
2-3 sentences on the most significant differences between the two reports.

## Agreement
What both reports concluded consistently — keep this section brief.

## Differences

### Coverage
Findings or aspects that one report included but the other omitted.

### Descriptions
The same aspects characterized differently — quote both where useful.

### Structure
How each report organized and prioritized its analysis differently.

## Sentiment
For each model, describe how it characterizes the site's tone and emotional register — confident, cautious,
authoritative, approachable, technical, etc. Use the model's name as the subsection header and quote specific
language from its report.

### Comparison
Where the two reports diverge in how they perceive the site's emotional positioning.

## Side-by-Side
A markdown table with one column per model, using each model's name as the column header:

| Aspect | <first model name> | <second model name> |
|--------|--------------------|----------------------|
| Key strengths | ... | ... |
| Coverage depth | ... | ... |
| Dominant focus | ... | ... |
| Sentiment | ... | ... |

## Assessment
Which report is more complete or useful for understanding the site — and why.
Be specific and evidence-based; do not give a blanket verdict without quoting the reports.

Rules:
- Refer to each report by its model name throughout — never "Model A" or "Model B"
- Focus on differences — agreements get one short section
- Quote from the actual reports when comparing specific characterizations
- "<model> is more detailed" is not useful without citing what it includes that the other does not

Produce your output as valid JSON with one field:
- `comparison_markdown`: the complete comparison in the format above
""".strip()


IMPLEMENT_SYSTEM_PROMPT = """
You are a frontend engineer that implements UI designs from structured plans.

You will be given a UI implementation plan, a target GitHub repository, and a branch name.
Work in this exact order — do not deviate:

1. Clone the repository (git and gh credentials are pre-configured — do not modify git config):
   ```
   git clone <Repository URL> repo
   ```
2. Create the specified branch from the base branch inside `repo`
3. Implement all components from the plan directly inside `repo`:
   - Use the exact colors, fonts, and spacing from Design Tokens
   - Implement every component in the Component Inventory
   - Follow the Suggested Build Order
   - Prefer semantic HTML and clean CSS — no frameworks unless the plan specifies one
   - Each file must be complete and runnable — no placeholders, no TODOs
4. Commit and push the branch:
   ```
   git add -A && git commit -m "Implement UI plan" && git push origin <branch-name>
   ```
   If the push fails, stop immediately and write `implement-output.json` with `{"pr_url": ""}` so the task can exit cleanly.
5. Create the pull request using explicit flags (required — there is no terminal for interactive prompts):
   ```
   gh pr create --title "UI Implementation" --body "Automated UI implementation from plan" --base main --head <branch-name>
   ```
   The command prints a single line to stdout: the PR URL (e.g. `https://github.com/.../pull/N`). Capture that line.
6. Immediately write `implement-output.json` to the working directory:
   ```
   echo '{"pr_url": "https://github.com/.../pull/N"}' > implement-output.json
   ```
   Use the exact URL from step 5 — do not guess or substitute a different URL.

Rules:
- git and gh credentials are pre-configured — cloning and pushing work without any extra setup
- Writing `implement-output.json` is mandatory — do it immediately after step 5 (or after a failed step)
- Once `implement-output.json` is written, stop — do not revise or re-check anything
""".strip()


# --- Internal ---


def _build_compare_message(
    job_a: dict, content_a: str, job_b: dict, content_b: str
) -> str:
    """Formats both reports into a comparison message labeled by the model that produced each."""
    model_a = job_a.get("model", "unknown")
    model_b = job_b.get("model", "unknown")
    url_a = job_a.get("url", "")
    url_b = job_b.get("url", "")

    url_note = ""
    if url_a != url_b:
        url_note = f"\nNote: the {model_a} report is for {url_a} and the {model_b} report is for {url_b} — these are different URLs.\n"

    return (
        f"Compare these two reports for the same website.{url_note}\n\n"
        f"Each report is labeled below with the model that produced it. Use these exact model names — "
        f'"{model_a}" and "{model_b}" — as the section headers and table columns throughout your comparison.\n\n'
        f"--- {model_a} ---\n{content_a}\n\n"
        f"--- {model_b} ---\n{content_b}"
    )


def _build_implement_prompt(url: str, config: TaskConfig) -> str:
    """Builds the agent prompt with git/gh commands; no token in URLs (auth via gh credential helper)."""
    plan_content = get_artifact_content(url, ArtifactType.PLAN)
    if plan_content is None:
        raise ValueError(f"UI plan artifact unavailable for job {url}")

    branch_name = f"ui-implement/{os.environ['AGENT_ID'][:8]}"
    clone_cmd = f"git clone {IMPLEMENTER_REPO}.git repo"
    branch_cmd = f"git checkout -b {branch_name}"
    push_cmd = f"git add -A && git commit -m 'Implement UI plan' && git push origin {branch_name}"
    pr_cmd = (
        f"gh pr create"
        f" --title 'UI Implementation'"
        f" --body 'Automated UI implementation from plan'"
        f" --base {IMPLEMENTER_BASE_BRANCH}"
        f" --head {branch_name}"
    )

    return (
        f"{config.system_prompt}\n\n"
        f"Execute these exact steps in order:\n\n"
        f"1. Clone:          {clone_cmd}\n"
        f"2. Create branch:  cd repo && {branch_cmd}\n"
        f"3. Implement:      write all UI files directly inside repo/ (see ## UI Plan below)\n"
        f"4. Commit & push:  {push_cmd}\n"
        f"5. Create PR:      {pr_cmd}\n"
        f"   Capture the URL printed on stdout (e.g. https://github.com/.../pull/N).\n"
        f"6. Write output:   write `{config.output_file}` in the working directory (not inside repo/).\n"
        f"   Schema: {config.output_schema_hint}\n"
        f'   Example: {{"pr_url": "<exact URL from step 5>", "debug": ""}}\n\n'
        f"If any step fails, write `{config.output_file}` immediately with:\n"
        f'   {{"pr_url": "", "debug": "step N failed: <exact error message from the failed command>"}}\n'
        f"and stop. Include the full error output in debug.\n\n"
        f"## UI Plan\n\n{plan_content}"
    )
