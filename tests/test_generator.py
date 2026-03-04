"""
CxE Care Evaluation Agent - Tests

Unit tests for the dataset generator.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from backend.models import (
    DataComplexity,
    DatasetStatus,
    GoldenDataset,
    ScenarioCategory,
    ScenarioDescription,
    DatasetSample,
)


class TestScenarioDescription:
    """Tests for ScenarioDescription model validation."""

    def test_valid_scenario(self):
        scenario = ScenarioDescription(
            title="Test Case Triage",
            description="Evaluate an agent that triages incoming support cases by severity.",
            category=ScenarioCategory.CASE_MANAGEMENT,
            num_samples=10,
        )
        assert scenario.title == "Test Case Triage"
        assert scenario.category == ScenarioCategory.CASE_MANAGEMENT
        assert scenario.num_samples == 10
        assert len(scenario.complexity_levels) == 3  # default: simple, moderate, complex

    def test_default_values(self):
        scenario = ScenarioDescription(
            title="Default Test",
            description="A minimal scenario description",
        )
        assert scenario.category == ScenarioCategory.CUSTOM
        assert scenario.num_samples == 20
        assert scenario.include_edge_cases is True
        assert scenario.kusto_database is None

    def test_min_samples_validation(self):
        with pytest.raises(Exception):
            ScenarioDescription(
                title="Too few",
                description="Should fail",
                num_samples=2,  # Below minimum of 5
            )


class TestDatasetSample:
    """Tests for DatasetSample model."""

    def test_create_sample(self):
        sample = DatasetSample(
            id="test-001",
            complexity=DataComplexity.SIMPLE,
            input_data={"case_title": "Cannot login", "severity": "Sev3"},
            expected_output={"triage_result": "Identity", "team": "IAM"},
            reasoning="Tests basic case routing for identity issues",
        )
        assert sample.id == "test-001"
        assert sample.complexity == DataComplexity.SIMPLE
        assert "case_title" in sample.input_data


class TestGoldenDataset:
    """Tests for GoldenDataset model."""

    def test_to_export_dict(self):
        scenario = ScenarioDescription(
            title="Export Test",
            description="Testing export functionality",
        )
        dataset = GoldenDataset(id="test-123", scenario=scenario)
        dataset.samples.append(
            DatasetSample(
                id="s1",
                complexity=DataComplexity.SIMPLE,
                input_data={"q": "test"},
                expected_output={"a": "answer"},
            )
        )

        export = dataset.to_export_dict()
        assert export["id"] == "test-123"
        assert export["total_samples"] == 1
        assert len(export["samples"]) == 1

    def test_to_json(self):
        scenario = ScenarioDescription(
            title="JSON Test",
            description="Testing JSON serialization",
        )
        dataset = GoldenDataset(id="json-123", scenario=scenario)
        json_str = dataset.to_json()
        parsed = json.loads(json_str)
        assert parsed["id"] == "json-123"


class TestDatasetGenerator:
    """Tests for the DatasetGenerator (with mocked external calls)."""

    @patch("backend.dataset_generator.DatasetGenerator.openai_client", new_callable=lambda: property(lambda self: MagicMock()))
    def test_extract_keywords_fallback(self, _):
        """When LLM fails, keywords should be extracted via basic splitting."""
        from backend.dataset_generator import DatasetGenerator

        gen = DatasetGenerator()
        gen._openai_client = MagicMock()
        gen._openai_client.chat.completions.create.side_effect = Exception("LLM error")

        keywords = gen.extract_scenario_keywords(
            "Evaluate case triage for incoming support tickets"
        )
        # Should fall back to basic word splitting
        assert isinstance(keywords, list)
        assert len(keywords) > 0

    def test_category_keywords_mapping(self):
        """All categories should have keyword mappings."""
        from backend.dataset_generator import CATEGORY_KEYWORDS

        for category in ScenarioCategory:
            assert category in CATEGORY_KEYWORDS
