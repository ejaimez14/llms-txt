# Demo

A tour of the llms.txt crawler — give it a URL and it produces an `llms.txt`, a UI plan, a
structured report, and a cross-model comparison, with semantic search over everything crawled.
All screenshots are the **live system**.

![Walkthrough](walkthrough.gif)

## Architecture

![Architecture](architecture.png)

The browser only talks to CloudFront: it serves the static UI from S3 and proxies `/api` to the
Lambda. The Lambda keeps the API fast and dispatches slow agent work (crawl, report, compare,
implement) to ECS Fargate. Agents call the Claude and OpenAI APIs; state lives in DynamoDB
(jobs & sites), S3 (artifacts + previews), and Pinecone (embeddings).

## Pages

### Crawl
Point it at any website and pick a model.

![Crawl](img/crawl.png)

### Search
Semantic search over everything crawled — `developer tools` surfaces GitHub, Vercel, and Figma, ranked by similarity (top 3).

![Search](img/search.png)

### Report
A structured site-analysis report, generated per model.

![Report](img/report.png)

### Compare
A diff-focused comparison of the two models' reports for the same site.

![Compare](img/compare.png)

### History
Every job is tracked, with filters for model, status, and artifact.

![History](img/history.png)

### Job detail
Any job opens to its artifacts — `llms.txt` and the UI plan — with per-job token usage.

![Job detail](img/job-detail.png)

## Reskin (implement)

The implement step restyles the app's **own** UI using a crawled site's design system, then serves
it live at `/experimental/<jobId>/` and opens a PR — the same app, three different identities.

| Before (original) | Restyled as Spotify | Restyled as tryprofound |
|---|---|---|
| ![before](img/reskin-before.png) | ![spotify](img/reskin-after-spotify.png) | ![tryprofound](img/reskin-after-tryprofound.png) |
