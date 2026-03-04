"""
CxE Care Evaluation Agent - Configuration Module

Manages all configuration settings from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # Kusto Configuration
    KUSTO_CLUSTER_URL: str = os.getenv(
        "KUSTO_CLUSTER_URL",
        "https://cxedataplatformcluster.westus2.kusto.windows.net",
    )
    KUSTO_DATABASE: str = os.getenv("KUSTO_DATABASE", "CxEDataPlatform")

    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    AZURE_OPENAI_API_VERSION: str = os.getenv(
        "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
    )

    # GitHub Configuration
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "jinruishao/CxE-Care-Evaluations")
    GITHUB_BRANCH: str = os.getenv("GITHUB_BRANCH", "main")

    # App Configuration
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,https://jinruishao.github.io"
    ).split(",")

    # Common Kusto databases that may contain relevant tables
    KUSTO_DATABASES: list[str] = [
        "CxEDataPlatform",
        "CxECareInsights",
        "SupportCases",
        "ServiceManager",
    ]


settings = Settings()
