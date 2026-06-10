import uuid
from collections.abc import Callable
from threading import Thread

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from mangum import Mangum

from src.agents.comparer import run_comparer
from src.agents.reporter import run_reporter
from src.constants import (
    AgentType,
    ArtifactStatus,
    ArtifactType,
    JobStatus,
    JobType,
    ModelName,
)
from src.models import (
    CompareRequest,
    CrawlRequest,
    ImplementRequest,
    ReportRequest,
    SearchResponse,
)
from src.services.fargate import trigger_task
from src.services.logger import get_logger
from src.services.recrawl import handle_schedule, handle_sqs
from src.services.search import run_search
from src.services.storage import (
    create_job,
    fail_artifact,
    get_artifact_content,
    get_job,
    get_site,
    list_jobs,
    list_jobs_for_url,
)

logger = get_logger(__name__)

app = FastAPI(title="llms.txt Crawler")
router = APIRouter(prefix="/api")


@router.post("/crawl", status_code=202, summary="Start a crawl job")
def crawl(req: CrawlRequest) -> dict:
    """Creates a crawl job and dispatches crawler and UI planner tasks to Fargate."""
    job_id = str(uuid.uuid4())
    create_job(job_id, req.url, req.model, JobType.CRAWL)
    try:
        trigger_task(AgentType.CRAWL, job_id, req.url, req.model.value)
        trigger_task(AgentType.UI_PLAN, job_id, req.url, req.model.value)
    except Exception as exc:
        logger.error(
            {"event": "crawl_dispatch_failed", "jobId": job_id, "error": str(exc)}
        )
        fail_artifact(job_id, ArtifactType.LLMS_TXT, str(exc))
        fail_artifact(job_id, ArtifactType.PLAN, str(exc))
        raise
    return {"jobId": job_id, "status": "processing"}


@router.get("/job", summary="Get job status")
def get_job_status(id: str = Query(...)) -> dict:
    """Returns the job record with per-artifact statuses. Poll this endpoint to track crawl, report, or compare progress."""
    job = get_job(id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {id} not found")
    return job


@router.get("/job/{id}/llms-txt", summary="Get llms.txt artifact")
def get_llms_txt(id: str) -> dict:
    """Returns the raw llms.txt content for a completed crawl job. Returns 404 if the artifact is not ready."""
    content = get_artifact_content(id, ArtifactType.LLMS_TXT)
    if content is None:
        raise HTTPException(status_code=404, detail="llms.txt artifact not ready")
    return {"jobId": id, "content": content}


@router.get("/job/{id}/plan", summary="Get UI plan artifact")
def get_plan(id: str) -> dict:
    """Returns the raw UI implementation plan markdown for a completed crawl job. Returns 404 if the artifact is not ready."""
    content = get_artifact_content(id, ArtifactType.PLAN)
    if content is None:
        raise HTTPException(status_code=404, detail="plan artifact not ready")
    return {"jobId": id, "content": content}


@router.get("/job/{id}/report", summary="Get report artifact")
def get_report(id: str) -> dict:
    """Returns the structured site analysis report markdown. Returns 404 if the artifact is not ready."""
    content = get_artifact_content(id, ArtifactType.REPORT)
    if content is None:
        raise HTTPException(status_code=404, detail="report artifact not ready")
    return {"jobId": id, "content": content}


@router.get("/job/{id}/comparison", summary="Get comparison artifact")
def get_comparison(id: str) -> dict:
    """Returns the llms.txt comparison markdown for a completed compare job. Returns 404 if the artifact is not ready."""
    content = get_artifact_content(id, ArtifactType.COMPARISON)
    if content is None:
        raise HTTPException(status_code=404, detail="comparison artifact not ready")
    return {"jobId": id, "content": content}


@router.get("/job/{id}/pr-url", summary="Get PR URL for implement job")
def get_pr_url(id: str) -> dict:
    """Returns the GitHub PR URL for a completed implement job. Returns 404 if not ready."""
    job = get_job(id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {id} not found")
    artifact = job.get("artifacts", {}).get(ArtifactType.PR_URL.value, {})
    if artifact.get("status") != ArtifactStatus.COMPLETE.value:
        raise HTTPException(status_code=404, detail="PR URL artifact not ready")
    pr_url = artifact.get("prUrl")
    if not pr_url:
        raise HTTPException(status_code=404, detail="PR URL not available")
    return {"jobId": id, "prUrl": pr_url}


@router.get("/jobs", summary="List all jobs")
def list_all_jobs(model: str | None = None) -> dict:
    """Returns a lightweight list of all jobs without artifact content. Optionally filter by model."""
    return {"jobs": list_jobs(model)}


@router.get("/site", summary="Get site record and history")
def get_site_record(url: str = Query(...)) -> dict:
    """Returns the latest site metadata and full crawl history for a given URL."""
    site = get_site(url)
    if site is None:
        raise HTTPException(status_code=404, detail=f"No crawl found for {url}")
    return {"site": site, "history": list_jobs_for_url(url)}


@router.get("/search", summary="Search crawled sites", response_model=SearchResponse)
def search(q: str = Query(...)) -> SearchResponse:
    """Embeds the query and searches Pinecone for semantically similar llms.txt content. Synchronous — no polling needed."""
    return run_search(q)


@router.post("/report", status_code=202, summary="Generate a site report")
def report(req: ReportRequest) -> dict:
    """Looks up the latest crawl for the URL and generates a structured analysis report in the background."""
    if get_site(req.url) is None:
        raise HTTPException(
            status_code=404,
            detail=f"No crawl found for {req.url}. Crawl the site first.",
        )
    job_id = str(uuid.uuid4())
    create_job(job_id, req.url, req.model, JobType.REPORT)
    _run_in_thread(run_reporter, job_id, req.url, req.model)
    return {"jobId": job_id, "status": "processing"}


@router.post("/compare", status_code=202, summary="Compare two crawl jobs")
def compare(req: CompareRequest) -> dict:
    """Fetches llms.txt from two complete crawl jobs and generates a diff-focused comparison in the background."""
    if req.job_id_a == req.job_id_b:
        raise HTTPException(
            status_code=400, detail="job_id_a and job_id_b must be different"
        )

    job_a = get_job(req.job_id_a)
    if job_a is None:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id_a} not found")

    job_b = get_job(req.job_id_b)
    if job_b is None:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id_b} not found")

    if job_a.get("status") != JobStatus.COMPLETE:
        raise HTTPException(
            status_code=400, detail=f"Job {req.job_id_a} is not complete"
        )
    if job_b.get("status") != JobStatus.COMPLETE:
        raise HTTPException(
            status_code=400, detail=f"Job {req.job_id_b} is not complete"
        )

    job_id = str(uuid.uuid4())
    create_job(job_id, job_a["url"], req.model, JobType.COMPARE)
    _run_in_thread(run_comparer, job_id, req.job_id_a, req.job_id_b, req.model)
    return {"jobId": job_id, "status": "processing"}


@router.post("/implement", status_code=202, summary="Implement a UI plan")
def implement(req: ImplementRequest) -> dict:
    """Reads the UI plan from a completed crawl job and dispatches a Fargate task to open a GitHub PR."""
    job = get_job(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found")
    plan_artifact = job.get("artifacts", {}).get(ArtifactType.PLAN.value, {})
    if plan_artifact.get("status") != ArtifactStatus.COMPLETE.value:
        raise HTTPException(status_code=400, detail="UI plan artifact is not complete")

    job_id = str(uuid.uuid4())
    create_job(job_id, req.job_id, ModelName.CLAUDE, JobType.IMPLEMENT)
    trigger_task(AgentType.IMPLEMENT, job_id, req.job_id, ModelName.CLAUDE.value)
    return {"jobId": job_id, "status": "processing"}


@app.get("/")
def serve_frontend() -> FileResponse:
    # In prod CloudFront serves index.html from S3 — this route is for local dev only.
    return FileResponse("src/index.html")


# --- Internal ---


def _run_in_thread(fn: Callable[..., object], *args: object) -> None:
    """Starts fn(*args) in a daemon thread for single-agent background jobs."""
    Thread(target=fn, args=args, daemon=True).start()


app.include_router(router)

_mangum = Mangum(app)


def handler(event: dict, context: object) -> dict:
    """Lambda entrypoint — dispatches to the correct handler path by event shape."""
    if event.get("type") == "REQUEST":
        return {"isAuthorized": True}
    records = event.get("Records", [])
    if records and records[0].get("eventSource") == "aws:sqs":
        return handle_sqs(event, context)
    if event.get("source") == "aws.events":
        return handle_schedule(event, context)
    return _mangum(event, context)
