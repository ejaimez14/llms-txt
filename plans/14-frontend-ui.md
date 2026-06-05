# Component: Frontend UI

## How to Use This Plan

You are implementing **Component 14: Frontend UI**. Your job is to produce `src/index.html` — a single self-contained HTML file with no build step and no external dependencies. It is served directly by the Lambda handler on `GET /`.

Dependencies: [04-models-constants-prompts.md](04-models-constants-prompts.md) — the JS status strings (`"processing"`, `"complete"`, `"partial"`) and model values (`"claude"`) must match the enum values defined there. No Python imports — just use the matching string literals.

Related plans:
- [02-lambda-handler.md](02-lambda-handler.md) — serves this file on `GET /`

---

## Owner

Frontend subagent

## Output Files

```
src/
  index.html
```

---

## Features

### Tab Navigation

Tabs: **Crawl**, **Search**, **History**

### Model Selector

A dropdown visible on the Crawl tab. Currently only Claude is active; Codex is shown as disabled so the structure is in place when it's added.

```html
<select id="model-select">
  <option value="claude">Claude (Bedrock)</option>
  <option value="codex" disabled>Codex (coming soon)</option>
</select>
```

The string values (`"claude"`, `"codex"`) match `ModelName` enum values from `src/constants.py`.

### Crawl Tab

- URL input field (required)
- Model selector
- Submit button — calls `POST /crawl`, gets back `jobId`
- Shows spinner while polling `GET /job?id=...` every 3 seconds
- Job is done when `job.status === "complete"` or `"partial"` (all artifacts finished)
- Displays both artifacts when ready:
  - **llms.txt** — fetched from `GET /job/{id}/llms-txt`, rendered as formatted markdown
  - **UI Plan** — fetched from `GET /job/{id}/plan`, rendered as formatted markdown
  - Each artifact has a **Download** button that saves the raw content as a file (client-side blob, no new endpoint)
  - Each artifact shows its individual status (`complete` / `failed`) with an error message if failed
- Stops polling once overall status is no longer `"processing"`

### Search Tab

- Query input field
- Submit calls `GET /search?q=...`
- Results display immediately (synchronous, no polling needed)
- Each result shows: URL, model, similarity score, download link

### History Tab

- On tab open, calls `GET /jobs`
- Displays list of all past jobs: model, URL, overall status, per-artifact status, timestamp
- Filter dropdown for model
- Each row is clickable — fetches both artifacts and displays them inline

---

## Polling Logic

```javascript
async function submitCrawl(url, model) {
  // 1. POST /crawl — returns jobId immediately
  const res = await callApi('/api/crawl', 'POST', { url, model })
  const { jobId } = res

  showSpinner()

  // 2. Poll GET /api/job until status is no longer "processing"
  // Status values: "processing" | "complete" | "partial"
  const poll = setInterval(async () => {
    const job = await callApi(`/api/job?id=${jobId}`, 'GET')
    if (job.status !== 'processing') {
      clearInterval(poll)
      hideSpinner()
      displayArtifacts(jobId, job.artifacts)
    }
  }, 3000)
}

async function displayArtifacts(jobId, artifacts) {
  // Fetch each artifact individually — only if its status is "complete"
  for (const [type, info] of Object.entries(artifacts)) {
    if (info.status === 'complete') {
      const path = type === 'llmsTxt' ? 'llms-txt' : 'plan'
      const filename = type === 'llmsTxt' ? 'llms.txt' : 'ui-plan.md'
      const data = await callApi(`/api/job/${jobId}/${path}`, 'GET')
      renderArtifact(type, data.content, filename)
    } else {
      renderArtifactError(type, info.error ?? 'Failed')
    }
  }
}

function renderArtifact(type, content, filename) {
  const section = document.getElementById(`artifact-${type}`)
  section.innerHTML = `
    <div class="artifact-header">
      <h3>${type === 'llmsTxt' ? 'llms.txt' : 'UI Plan'}</h3>
      <button class="btn-download" onclick="downloadArtifact('${filename}', this)">Download</button>
    </div>
    <div class="markdown-body">${renderMarkdown(content)}</div>
  `
  // Attach content to the button for the download handler
  section.querySelector('.btn-download')._content = content
}

function downloadArtifact(filename, btn) {
  const blob = new Blob([btn._content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Minimal markdown → HTML renderer. Handles the subset produced by Claude:
 * fenced code blocks, ATX headings, blockquotes, unordered lists, bold, italic,
 * inline code, and links. No external library needed.
 */
function renderMarkdown(md) {
  let html = md
    // Escape raw HTML to prevent XSS
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // Fenced code blocks (``` ... ```)
    .replace(/```[\w]*\n([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    // ATX headings
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Blockquotes
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    // Unordered list items (- or *)
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    // Checkbox list items (- [ ] and - [x])
    .replace(/<li>\[ \] (.+)<\/li>/g, '<li><input type="checkbox" disabled> $1</li>')
    .replace(/<li>\[x\] (.+)<\/li>/gi, '<li><input type="checkbox" checked disabled> $1</li>')
    // Bold and italic
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // Paragraph breaks (double newline)
    .replace(/\n\n/g, '</p><p>')
  return `<p>${html}</p>`
}
```

**Status string constants** — these match `JobStatus` and `ArtifactStatus` enum values exactly:
```javascript
const STATUS = { PROCESSING: 'processing', COMPLETE: 'complete', PARTIAL: 'partial', FAILED: 'failed' }
```

---

## API Calls

All API calls use `/api/*` paths — CloudFront routes these to API Gateway and injects the `x-api-key` header automatically. The frontend JS never holds or sends the API key.

```javascript
async function callApi(path, method, body) {
  const res = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}
```

No `x-api-key` header, no `__API_KEY__` placeholder, no build-time substitution needed.

---

## Design Requirements

- Clean, minimal, functional
- Sans-serif font
- Max width 800px, centered
- Works on mobile (responsive)
- **No external dependencies** — no React, no CSS frameworks, no CDN imports
- Artifact content rendered as formatted markdown (headings, code blocks, blockquotes, lists, links)
- Each artifact section has a Download button in the header row
- Model selector present in the UI; Codex option visible but disabled until backend support is added
- Spinner/animation while polling to indicate progress

### CSS for Markdown

Inline styles for `.markdown-body` to keep the file self-contained:

```css
.artifact-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}
.btn-download {
  font-size: 0.8rem;
  padding: 4px 10px;
  cursor: pointer;
}
.markdown-body { line-height: 1.6; }
.markdown-body h1 { font-size: 1.5rem; margin: 1rem 0 0.5rem; }
.markdown-body h2 { font-size: 1.2rem; margin: 1rem 0 0.4rem; border-bottom: 1px solid #e0e0e0; }
.markdown-body h3 { font-size: 1rem; margin: 0.8rem 0 0.3rem; }
.markdown-body pre { background: #f5f5f5; padding: 0.75rem; border-radius: 4px; overflow-x: auto; }
.markdown-body code { background: #f0f0f0; padding: 2px 4px; border-radius: 3px; font-size: 0.9em; }
.markdown-body pre code { background: none; padding: 0; }
.markdown-body blockquote { border-left: 3px solid #ccc; margin: 0.5rem 0; padding-left: 1rem; color: #555; }
.markdown-body li { margin: 0.25rem 0; }
.markdown-body a { color: #0066cc; }
```

---

## Acceptance Criteria

- Works as a single HTML file with no build step
- All API calls use relative paths (same origin)
- Polling stops when job status is `"complete"` or `"partial"` (not just `"complete"`)
- Both artifacts fetched and displayed individually after polling ends
- Per-artifact error shown if one artifact failed while the other succeeded
- Model selector value included in POST /crawl body
- Shows spinner while polling, clears on completion or error
- No leaked `setInterval` — always cleared before returning
- History tab loads on open and displays all past jobs with per-artifact statuses
- Clicking a history row fetches and displays both artifacts
- Status string constants defined in one place to match backend enum values
- No external dependencies
- Artifact content rendered as markdown (headings, code blocks, lists, bold, italic, links)
- Download button triggers a client-side blob download of the raw content (`.txt` for llms.txt, `.md` for plan)
- `renderMarkdown` escapes HTML before processing to prevent XSS from crawled content
