"""
CxE Care Evaluation Agent - Dataset Generator

Core logic for generating golden evaluation datasets.
Uses Kusto data + LLM to produce high-quality, scenario-specific test data.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from openai import AzureOpenAI

from .config import settings
from .kusto_client import KustoDataClient
from .models import (
    DataComplexity,
    DatasetSample,
    DatasetStatus,
    GoldenDataset,
    ScenarioCategory,
    ScenarioDescription,
)

logger = logging.getLogger(__name__)

# ── Scenario-to-keyword mapping ────────────────────────────────────────

CATEGORY_KEYWORDS: dict[ScenarioCategory, list[str]] = {
    ScenarioCategory.CASE_MANAGEMENT: ["case", "support", "ticket", "request", "queue"],
    ScenarioCategory.INCIDENT_RESPONSE: ["incident", "alert", "severity", "outage", "sev"],
    ScenarioCategory.SERVICE_DELIVERY: ["service", "delivery", "engagement", "project"],
    ScenarioCategory.CUSTOMER_ONBOARDING: ["onboarding", "customer", "tenant", "setup"],
    ScenarioCategory.ESCALATION: ["escalation", "escalate", "dtl", "manager", "priority"],
    ScenarioCategory.KNOWLEDGE_BASE: ["knowledge", "article", "kb", "documentation"],
    ScenarioCategory.SLA_COMPLIANCE: ["sla", "compliance", "response", "resolution", "time"],
    ScenarioCategory.CUSTOM: [],
}

# ── Prompt templates ───────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert evaluation-data engineer for Microsoft CxE (Customer Experience) support teams.
Your job is to generate realistic, high-quality golden evaluation datasets that can be used to test and benchmark AI agents.

Key principles:
1. Data must be realistic — use patterns from real support/case/SM data when provided.
2. Each sample must include clear input, expected output, and reasoning.
3. Include diverse customer profiles, product areas, severity levels, and resolution paths.
4. Include some difficult/ambiguous examples naturally within the dataset.
5. All generated data must be synthetic — no real customer PII.
"""

GENERATION_PROMPT_TEMPLATE = """Generate {num_samples} evaluation samples for the following scenario:

**Title:** {title}
**Description:** {description}
**Category:** {category}

{kusto_context}

Each sample MUST follow this JSON structure:
{{
  "id": "unique-id",
  "input_data": {{ ... input fields relevant to the scenario ... }},
  "expected_output": {{ ... expected correct output/response ... }},
  "context": {{ ... additional context like customer profile, product, etc. ... }},
  "metadata": {{ "tags": [...], "difficulty_score": 1-10 }},
  "reasoning": "Why this is a good test case and what it validates"
}}

Return ONLY a JSON array of {num_samples} samples. No markdown, no explanation outside the JSON.
"""

KEYWORD_EXTRACTION_PROMPT = """Extract relevant search keywords from this evaluation scenario description.
Return a JSON array of 5-10 keywords that could match Kusto table or column names.

Scenario: {description}

Return ONLY a JSON array of strings, e.g.: ["case", "incident", "severity"]
"""


class DatasetGenerator:
    """Generates golden evaluation datasets using Kusto data and LLM."""

    def __init__(self):
        self.kusto = KustoDataClient()
        self._openai_client: AzureOpenAI | None = None
        self._datasets: dict[str, GoldenDataset] = {}  # In-memory store

    @property
    def openai_client(self) -> AzureOpenAI:
        if self._openai_client is None:
            self._openai_client = AzureOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
            )
        return self._openai_client

    # ── LLM helpers ────────────────────────────────────────────────────

    def _chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        """Send a chat completion request to Azure OpenAI."""
        deployments: list[str] = [settings.AZURE_OPENAI_DEPLOYMENT]
        deployments.extend(settings.AZURE_OPENAI_FALLBACK_DEPLOYMENTS)

        # Preserve order while removing duplicates/empties.
        seen: set[str] = set()
        ordered_deployments: list[str] = []
        for deployment in deployments:
            if deployment and deployment not in seen:
                seen.add(deployment)
                ordered_deployments.append(deployment)

        last_error: Exception | None = None

        for deployment in ordered_deployments:
            deployment_name = deployment.lower()
            request_kwargs = {
                "model": deployment,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_completion_tokens": 1400,
            }

            if not deployment_name.startswith("gpt-5") and temperature != 1:
                request_kwargs["temperature"] = temperature

            try:
                response = self.openai_client.chat.completions.create(**request_kwargs)
                message = response.choices[0].message

                if message.content:
                    if deployment != settings.AZURE_OPENAI_DEPLOYMENT:
                        logger.warning(
                            "Using fallback deployment '%s' (primary '%s' unavailable).",
                            deployment,
                            settings.AZURE_OPENAI_DEPLOYMENT,
                        )
                    return message.content

                refusal = getattr(message, "refusal", None)
                if refusal:
                    raise RuntimeError(f"Model refusal ({deployment}): {refusal}")

                raise RuntimeError(f"Model returned empty content ({deployment})")

            except Exception as exc:
                last_error = exc
                logger.warning("Deployment '%s' failed: %s", deployment, exc)

        raise RuntimeError(f"All deployments failed. Last error: {last_error}")

    def _parse_json_response(self, text: str) -> Any:
        """Parse JSON from LLM response, stripping markdown fences."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # Remove ```json ... ``` wrapping
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # GPT models may prepend/append commentary around JSON.
            # Try to extract the first JSON array/object block.
            match = re.search(r"(\[.*\]|\{.*\})", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise

    # ── Keyword extraction ─────────────────────────────────────────────

    def extract_scenario_keywords(self, description: str) -> list[str]:
        """Use LLM to extract relevant keywords from a scenario description."""
        try:
            raw = self._chat(
                "You are a keyword extraction assistant.",
                KEYWORD_EXTRACTION_PROMPT.format(description=description),
                temperature=0.3,
            )
            keywords = self._parse_json_response(raw)
            if isinstance(keywords, list):
                return [str(k).lower() for k in keywords]
        except Exception as exc:
            logger.warning("Keyword extraction failed: %s", exc)

        # Fallback: basic keyword split
        stop_words = {"the", "a", "an", "is", "are", "for", "to", "in", "of", "and", "or", "with"}
        words = description.lower().split()
        return [w for w in words if len(w) > 3 and w not in stop_words][:10]

    # ── Kusto context gathering ────────────────────────────────────────

    def _build_kusto_context(self, scenario: ScenarioDescription) -> str:
        """Gather relevant Kusto data and format it as context for the LLM."""
        context_parts: list[str] = []

        try:
            # Get keywords from category + description
            keywords = list(CATEGORY_KEYWORDS.get(scenario.category, []))
            keywords.extend(self.extract_scenario_keywords(scenario.description))
            keywords = list(set(keywords))

            # Discover relevant tables
            db = scenario.kusto_database or self.kusto.default_database
            tables = scenario.kusto_tables

            if not tables:
                table_infos = self.kusto.discover_relevant_tables(keywords, db)
            else:
                table_infos = [self.kusto.get_table_info(t, db) for t in tables]

            if table_infos:
                context_parts.append("**Available Kusto Data (real schema & samples):**\n")
                for info in table_infos[:5]:  # Limit to 5 tables
                    context_parts.append(f"Table: `{info.database}.{info.table_name}`")
                    context_parts.append(f"  Rows: {info.row_count or 'unknown'}")
                    col_desc = ", ".join(
                        f"{c['name']} ({c['type']})" for c in info.columns[:15]
                    )
                    context_parts.append(f"  Columns: {col_desc}")
                    if info.sample_data:
                        context_parts.append(
                            f"  Sample (first 3 rows): {json.dumps(info.sample_data[:3], default=str)}"
                        )
                    context_parts.append("")

            # Also try getting case / SM data
            case_data = self.kusto.get_case_data_sample(db, limit=10)
            if case_data:
                context_parts.append("**Sample Case Data:**")
                context_parts.append(json.dumps(case_data[:5], default=str))
                context_parts.append("")

            sm_data = self.kusto.get_sm_data_sample(db, limit=10)
            if sm_data:
                context_parts.append("**Sample Service Manager Data:**")
                context_parts.append(json.dumps(sm_data[:5], default=str))
                context_parts.append("")

        except Exception as exc:
            logger.warning("Could not gather Kusto context: %s", exc)
            context_parts.append(
                "(Kusto data unavailable — generating synthetic data based on scenario description only.)"
            )

        return "\n".join(context_parts) if context_parts else "(No Kusto data available for context.)"

    # ── Sample generation ──────────────────────────────────────────────

    def _generate_samples(
        self,
        scenario: ScenarioDescription,
        kusto_context: str,
        num_samples: int,
    ) -> list[DatasetSample]:
        """Generate samples for a scenario in a single pass."""
        prompt = GENERATION_PROMPT_TEMPLATE.format(
            num_samples=num_samples,
            title=scenario.title,
            description=scenario.description,
            category=scenario.category.value,
            kusto_context=kusto_context,
        )

        try:
            raw = self._chat(SYSTEM_PROMPT, prompt, temperature=0.8)
            logger.info("LLM raw response (first 200 chars): %s", raw[:200] if raw else "EMPTY")
            parsed = self._parse_json_response(raw)
            logger.info("Parsed %d items from LLM response", len(parsed) if isinstance(parsed, list) else 0)

            samples: list[DatasetSample] = []
            for item in parsed:
                raw_complexity = item.get("complexity", DataComplexity.SIMPLE.value)
                try:
                    complexity = DataComplexity(raw_complexity)
                except Exception:
                    complexity = DataComplexity.SIMPLE

                sample = DatasetSample(
                    id=item.get("id", str(uuid.uuid4())[:8]),
                    complexity=complexity,
                    input_data=item.get("input_data", {}),
                    expected_output=item.get("expected_output", {}),
                    context=item.get("context", {}),
                    metadata=item.get("metadata", {}),
                    reasoning=item.get("reasoning", ""),
                )
                samples.append(sample)
            return samples

        except Exception as exc:
            logger.error("Sample generation failed: %s", exc, exc_info=True)
            return []

    # ── Main generation pipeline ───────────────────────────────────────

    def generate_dataset(self, scenario: ScenarioDescription) -> GoldenDataset:
        """
        Main entry point: generate a complete golden dataset for a scenario.

        Steps:
        1. Gather Kusto context (schemas, sample data)
        2. Generate samples via LLM
        3. Compile and return the golden dataset
        """
        dataset_id = str(uuid.uuid4())[:12]
        dataset = GoldenDataset(
            id=dataset_id,
            scenario=scenario,
            status=DatasetStatus.GENERATING,
        )
        self._datasets[dataset_id] = dataset

        logger.info("Starting dataset generation: %s (%s)", scenario.title, dataset_id)

        # Step 1: Gather Kusto context
        kusto_context = self._build_kusto_context(scenario)

        # Step 2: Generate samples in a single pass
        logger.info("Generating %d samples…", scenario.num_samples)
        all_samples = self._generate_samples(
            scenario=scenario,
            kusto_context=kusto_context,
            num_samples=scenario.num_samples,
        )

        # Step 4: Compile statistics
        dataset.samples = all_samples
        dataset.status = DatasetStatus.COMPLETED
        dataset.updated_at = datetime.utcnow()
        dataset.statistics = {
            "total_samples": len(all_samples),
            "generated_at": datetime.utcnow().isoformat(),
        }

        logger.info("Dataset %s completed with %d samples.", dataset_id, len(all_samples))
        self._datasets[dataset_id] = dataset
        return dataset

    # ── Dataset management ─────────────────────────────────────────────

    def get_dataset(self, dataset_id: str) -> GoldenDataset | None:
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> list[GoldenDataset]:
        return list(self._datasets.values())

    def delete_dataset(self, dataset_id: str) -> bool:
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            return True
        return False
