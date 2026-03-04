"""
CxE Care Evaluation Agent - GitHub Storage

Manages storing generated golden datasets in the GitHub repository.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from github import Github, GithubException

from .config import settings
from .models import GoldenDataset

logger = logging.getLogger(__name__)


class GitHubStorage:
    """Handles publishing datasets to the GitHub repository."""

    def __init__(self):
        self._github: Github | None = None
        self._repo = None

    @property
    def github(self) -> Github:
        if self._github is None:
            self._github = Github(settings.GITHUB_TOKEN)
        return self._github

    @property
    def repo(self):
        if self._repo is None:
            self._repo = self.github.get_repo(settings.GITHUB_REPO)
        return self._repo

    def publish_dataset(
        self,
        dataset: GoldenDataset,
        commit_message: str = "",
    ) -> str:
        """
        Publish a golden dataset to the GitHub repository.

        Creates/updates a JSON file in the datasets/ directory.
        Returns the URL of the published file.
        """
        if not commit_message:
            commit_message = (
                f"Add golden dataset: {dataset.scenario.title} "
                f"({len(dataset.samples)} samples)"
            )

        file_path = f"datasets/{dataset.id}/{dataset.id}.json"
        content = dataset.to_json(indent=2)

        try:
            # Check if file already exists
            try:
                existing = self.repo.get_contents(file_path, ref=settings.GITHUB_BRANCH)
                # Update existing file
                self.repo.update_file(
                    file_path,
                    commit_message,
                    content,
                    existing.sha,
                    branch=settings.GITHUB_BRANCH,
                )
                logger.info("Updated dataset file: %s", file_path)
            except GithubException:
                # Create new file
                self.repo.create_file(
                    file_path,
                    commit_message,
                    content,
                    branch=settings.GITHUB_BRANCH,
                )
                logger.info("Created dataset file: %s", file_path)

            # Also publish a summary/README for the dataset
            self._publish_dataset_readme(dataset)

            url = f"https://github.com/{settings.GITHUB_REPO}/blob/{settings.GITHUB_BRANCH}/{file_path}"
            return url

        except GithubException as exc:
            logger.error("Failed to publish dataset: %s", exc)
            raise

    def _publish_dataset_readme(self, dataset: GoldenDataset) -> None:
        """Create/update a README.md for the dataset directory."""
        readme_path = f"datasets/{dataset.id}/README.md"
        stats = dataset.statistics

        readme_content = f"""# Golden Dataset: {dataset.scenario.title}

**Category:** {dataset.scenario.category.value}
**Generated:** {dataset.created_at.strftime('%Y-%m-%d %H:%M UTC')}
**Total Samples:** {stats.get('total_samples', len(dataset.samples))}

## Scenario Description

{dataset.scenario.description}
"""

        readme_content += f"""
## Kusto Tables Referenced

{chr(10).join(f'- `{t}`' for t in dataset.tables_referenced) or 'None'}

## Usage

Load the dataset JSON file for evaluation:

```python
import json

with open("{dataset.id}.json") as f:
    dataset = json.load(f)

for sample in dataset["samples"]:
    input_data = sample["input_data"]
    expected = sample["expected_output"]
    # Run your agent and compare output with expected
```
"""

        try:
            try:
                existing = self.repo.get_contents(readme_path, ref=settings.GITHUB_BRANCH)
                self.repo.update_file(
                    readme_path,
                    f"Update README for dataset {dataset.id}",
                    readme_content,
                    existing.sha,
                    branch=settings.GITHUB_BRANCH,
                )
            except GithubException:
                self.repo.create_file(
                    readme_path,
                    f"Add README for dataset {dataset.id}",
                    readme_content,
                    branch=settings.GITHUB_BRANCH,
                )
        except GithubException as exc:
            logger.warning("Could not publish dataset README: %s", exc)

    def list_published_datasets(self) -> list[dict[str, Any]]:
        """List all published datasets in the repository."""
        try:
            contents = self.repo.get_contents("datasets", ref=settings.GITHUB_BRANCH)
            datasets = []
            for item in contents:
                if item.type == "dir":
                    datasets.append({
                        "id": item.name,
                        "path": item.path,
                        "url": item.html_url,
                    })
            return datasets
        except GithubException:
            return []

    def get_published_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """Retrieve a published dataset from GitHub."""
        try:
            file_path = f"datasets/{dataset_id}/{dataset_id}.json"
            content = self.repo.get_contents(file_path, ref=settings.GITHUB_BRANCH)
            return json.loads(content.decoded_content.decode())
        except GithubException:
            return None

    def delete_published_dataset(self, dataset_id: str) -> bool:
        """Delete a published dataset from GitHub."""
        try:
            dir_path = f"datasets/{dataset_id}"
            contents = self.repo.get_contents(dir_path, ref=settings.GITHUB_BRANCH)
            for item in contents:
                self.repo.delete_file(
                    item.path,
                    f"Delete dataset {dataset_id}",
                    item.sha,
                    branch=settings.GITHUB_BRANCH,
                )
            return True
        except GithubException as exc:
            logger.error("Failed to delete dataset: %s", exc)
            return False
