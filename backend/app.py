"""
CxE Care Evaluation Agent - FastAPI Application

REST API that powers the Evaluation Agent UI.
Provides endpoints for:
  - Generating golden datasets from scenario descriptions
  - Exploring Kusto cluster data
  - Publishing datasets to GitHub
  - Managing generated datasets
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .dataset_generator import DatasetGenerator
from .github_storage import GitHubStorage
from .kusto_client import KustoDataClient
from .models import (
    APIResponse,
    KustoQueryRequest,
    PublishRequest,
    ScenarioDescription,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Shared instances ───────────────────────────────────────────────────

generator = DatasetGenerator()
github_storage = GitHubStorage()
kusto_client = KustoDataClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CxE Care Evaluation Agent starting…")
    yield
    logger.info("CxE Care Evaluation Agent shutting down…")


app = FastAPI(
    title="CxE Care Evaluation Agent",
    description="Generate golden evaluation datasets for CxE support AI agents",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ───────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "CxE Care Evaluation Agent"}


# ── Dataset generation ─────────────────────────────────────────────────

@app.post("/api/datasets/generate", response_model=APIResponse)
async def generate_dataset(scenario: ScenarioDescription):
    """Generate a golden dataset from a scenario description."""
    try:
        dataset = generator.generate_dataset(scenario)
        return APIResponse(
            success=True,
            message=f"Dataset generated with {len(dataset.samples)} samples",
            data=dataset.to_export_dict(),
        )
    except Exception as exc:
        logger.exception("Dataset generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/datasets", response_model=APIResponse)
async def list_datasets():
    """List all generated datasets (in-memory)."""
    datasets = generator.list_datasets()
    return APIResponse(
        success=True,
        data=[d.to_export_dict() for d in datasets],
    )


@app.get("/api/datasets/{dataset_id}", response_model=APIResponse)
async def get_dataset(dataset_id: str):
    """Get a specific dataset by ID."""
    dataset = generator.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return APIResponse(success=True, data=dataset.to_export_dict())


@app.delete("/api/datasets/{dataset_id}", response_model=APIResponse)
async def delete_dataset(dataset_id: str):
    """Delete a dataset."""
    if generator.delete_dataset(dataset_id):
        return APIResponse(success=True, message="Dataset deleted")
    raise HTTPException(status_code=404, detail="Dataset not found")


# ── GitHub publishing ──────────────────────────────────────────────────

@app.post("/api/datasets/{dataset_id}/publish", response_model=APIResponse)
async def publish_dataset(dataset_id: str, req: PublishRequest | None = None):
    """Publish a dataset to the GitHub repository."""
    dataset = generator.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    try:
        msg = req.commit_message if req and req.commit_message else ""
        url = github_storage.publish_dataset(dataset, msg)
        dataset.github_url = url
        return APIResponse(
            success=True,
            message="Dataset published to GitHub",
            data={"url": url},
        )
    except Exception as exc:
        logger.exception("GitHub publish failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/github/datasets", response_model=APIResponse)
async def list_github_datasets():
    """List datasets published on GitHub."""
    try:
        datasets = github_storage.list_published_datasets()
        return APIResponse(success=True, data=datasets)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Kusto exploration ──────────────────────────────────────────────────

@app.get("/api/kusto/databases", response_model=APIResponse)
async def list_kusto_databases():
    """List available Kusto databases."""
    try:
        dbs = kusto_client.list_databases()
        return APIResponse(success=True, data=dbs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/kusto/tables/{database}", response_model=APIResponse)
async def list_kusto_tables(database: str):
    """List tables in a Kusto database."""
    try:
        tables = kusto_client.list_tables(database)
        return APIResponse(success=True, data=tables)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/kusto/table/{database}/{table_name}", response_model=APIResponse)
async def get_kusto_table_info(database: str, table_name: str):
    """Get schema and sample data for a Kusto table."""
    try:
        info = kusto_client.get_table_info(table_name, database)
        return APIResponse(success=True, data=info.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/kusto/query", response_model=APIResponse)
async def execute_kusto_query(req: KustoQueryRequest):
    """Execute a custom KQL query."""
    try:
        results = kusto_client.execute_custom_query(req.query, req.database)
        return APIResponse(success=True, data=results)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Serve static UI (for local dev) ───────────────────────────────────

try:
    app.mount("/", StaticFiles(directory="docs", html=True), name="static")
except Exception:
    logger.info("Static files directory 'docs' not found — UI will not be served.")
