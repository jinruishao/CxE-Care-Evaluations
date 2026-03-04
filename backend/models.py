"""
CxE Care Evaluation Agent - Data Models

Pydantic models for API requests, responses, and data structures.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────

class ScenarioCategory(str, Enum):
    """Categories of evaluation scenarios."""
    CASE_MANAGEMENT = "case_management"
    INCIDENT_RESPONSE = "incident_response"
    SERVICE_DELIVERY = "service_delivery"
    CUSTOMER_ONBOARDING = "customer_onboarding"
    ESCALATION = "escalation"
    KNOWLEDGE_BASE = "knowledge_base"
    SLA_COMPLIANCE = "sla_compliance"
    CUSTOM = "custom"


class DatasetStatus(str, Enum):
    """Status of a golden dataset."""
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PUBLISHED = "published"


class DataComplexity(str, Enum):
    """Complexity level for generated data."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EDGE_CASE = "edge_case"


# ── Request Models ─────────────────────────────────────────────────────

class ScenarioDescription(BaseModel):
    """User-provided scenario description for golden dataset generation."""
    title: str = Field(..., min_length=3, max_length=200, description="Short title for the evaluation scenario")
    description: str = Field(..., min_length=10, description="Detailed description of the scenario to evaluate")
    category: ScenarioCategory = Field(default=ScenarioCategory.CUSTOM, description="Category of the scenario")
    complexity_levels: list[DataComplexity] = Field(
        default=[DataComplexity.SIMPLE, DataComplexity.MODERATE, DataComplexity.COMPLEX],
        description="Deprecated: complexity segmentation is no longer used"
    )
    num_samples: int = Field(default=20, ge=5, le=200, description="Total number of samples to generate")
    include_edge_cases: bool = Field(default=True, description="Deprecated: edge-case flag is no longer used")
    custom_fields: dict[str, str] | None = Field(default=None, description="Additional custom fields for the scenario")
    kusto_database: str | None = Field(default=None, description="Specific Kusto database to query")
    kusto_tables: list[str] | None = Field(default=None, description="Specific Kusto tables to use")


class KustoQueryRequest(BaseModel):
    """Request to explore Kusto data."""
    database: str = Field(..., description="Database name")
    query: str = Field(default="", description="Optional KQL query")
    table_name: str = Field(default="", description="Table name to explore")


class PublishRequest(BaseModel):
    """Request to publish a dataset to GitHub."""
    dataset_id: str
    commit_message: str = Field(default="", description="Custom commit message")


# ── Response / Data Models ─────────────────────────────────────────────

class KustoTableInfo(BaseModel):
    """Information about a Kusto table."""
    database: str
    table_name: str
    columns: list[dict[str, str]] = Field(default_factory=list)
    row_count: int | None = None
    sample_data: list[dict[str, Any]] = Field(default_factory=list)


class DatasetSample(BaseModel):
    """A single sample in the golden dataset."""
    id: str
    complexity: DataComplexity
    input_data: dict[str, Any]
    expected_output: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = Field(default="", description="Explanation of why this is a good test case")


class GoldenDataset(BaseModel):
    """Complete golden dataset for an evaluation scenario."""
    id: str
    scenario: ScenarioDescription
    status: DatasetStatus = DatasetStatus.GENERATING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    samples: list[DatasetSample] = Field(default_factory=list)
    kusto_queries_used: list[str] = Field(default_factory=list)
    tables_referenced: list[str] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    github_url: str | None = None

    def to_export_dict(self) -> dict:
        """Convert to a dictionary suitable for JSON export."""
        return {
            "id": self.id,
            "scenario": {
                "title": self.scenario.title,
                "description": self.scenario.description,
                "category": self.scenario.category.value,
            },
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "total_samples": len(self.samples),
            "samples": [s.model_dump() for s in self.samples],
            "kusto_queries_used": self.kusto_queries_used,
            "tables_referenced": self.tables_referenced,
            "statistics": self.statistics,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_export_dict(), indent=indent, default=str)


class GenerationProgress(BaseModel):
    """Progress update during dataset generation."""
    dataset_id: str
    step: str
    progress_pct: float = 0.0
    message: str = ""
    current_samples: int = 0
    total_samples: int = 0


class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool
    message: str = ""
    data: Any = None
    error: str | None = None
