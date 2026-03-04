# AGENTS.md — CxE Care Evaluation Agent

> Guidelines for AI coding agents working on this project.

## Project Overview

**CxE Care Evaluation Agent** is a Python-based tool that generates **golden evaluation datasets** for testing and benchmarking AI agents in Microsoft CxE (Customer Experience) support scenarios.

### What It Does

1. Takes a **scenario description** (e.g., "evaluate case triage agent accuracy") as input
2. **Discovers relevant data** from the CxE Data Platform Kusto cluster (table schemas, sample data)
3. Uses **Azure OpenAI** to generate realistic, diverse evaluation samples across multiple complexity levels
4. **Publishes** results to [CxE-Care-Evaluations GitHub repo](https://github.com/jinruishao/CxE-Care-Evaluations)
5. Provides a **web UI** (deployed as GitHub Pages) for interactive dataset generation and management

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   GitHub Pages UI                    │
│               (docs/index.html + JS)                │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Generate  │  │ Datasets │  │  Kusto   │           │
│  │   Form    │  │  Viewer  │  │ Explorer │           │
│  └─────┬─────┘  └─────┬────┘  └────┬─────┘           │
└────────┼───────────────┼────────────┼────────────────┘
         │               │            │
    ┌────▼────────────────▼────────────▼──────┐
    │         FastAPI Backend (Python)         │
    │                                          │
    │  ┌─────────────────┐  ┌──────────────┐  │
    │  │ DatasetGenerator │  │ KustoClient  │  │
    │  │ (LLM + Kusto)   │  │ (ADX SDK)    │  │
    │  └────────┬────────┘  └──────┬───────┘  │
    │           │                  │           │
    │  ┌────────▼──────────────────▼───────┐  │
    │  │       GitHubStorage (PyGithub)    │  │
    │  └───────────────┬───────────────────┘  │
    └──────────────────┼──────────────────────┘
                       │
    ┌──────────────────▼──────────────────────┐
    │         External Services                │
    │                                          │
    │  • Azure OpenAI  (gpt-4o)               │
    │  • Kusto Cluster (cxedataplatform...)   │
    │  • GitHub API    (jinruishao/CxE-...)   │
    └──────────────────────────────────────────┘
```

## Tech Stack

| Component     | Technology                        |
|---------------|----------------------------------|
| Backend       | Python 3.11+, FastAPI, Uvicorn   |
| Kusto SDK     | azure-kusto-data, azure-identity |
| LLM           | Azure OpenAI (openai SDK)        |
| GitHub        | PyGithub                         |
| Data          | Pandas, Pydantic                 |
| Frontend      | HTML, CSS, Vanilla JS            |
| Deployment    | GitHub Pages (UI), Local (API)   |

## File Structure

```
CxE-Care-Evaluations/
├── AGENTS.md                 ← You are here
├── README.md                 ← User-facing documentation
├── requirements.txt          ← Python dependencies
├── .env.example              ← Environment variable template
├── .gitignore
│
├── backend/                  ← Python backend
│   ├── __init__.py
│   ├── app.py               ← FastAPI application & API routes
│   ├── config.py             ← Settings from env vars
│   ├── models.py             ← Pydantic data models
│   ├── kusto_client.py       ← Azure Data Explorer integration
│   ├── dataset_generator.py  ← Core generation logic (Kusto + LLM)
│   └── github_storage.py     ← GitHub API for publishing datasets
│
├── docs/                     ← GitHub Pages frontend
│   ├── index.html            ← Single-page application
│   ├── css/styles.css        ← Microsoft Fluent-inspired theme
│   └── js/app.js             ← Frontend logic & API calls
│
├── datasets/                 ← Published golden datasets
│   └── {dataset-id}/
│       ├── {dataset-id}.json ← The golden dataset
│       └── README.md         ← Auto-generated dataset summary
│
├── tests/                    ← Unit tests
│   └── test_generator.py
│
└── .github/workflows/
    └── deploy-pages.yml      ← GitHub Pages deployment
```

## Key Coding Conventions

1. **Python**: Follow PEP 8. Use type hints everywhere. Use `from __future__ import annotations` for forward refs.
2. **Models**: Use Pydantic `BaseModel` for all data structures. Define enums for fixed categories.
3. **Error handling**: Log errors via `logging` module. Never expose raw stack traces to the API consumer.
4. **Kusto queries**: Always parameterize. Never use f-strings with user input directly in KQL.
5. **Frontend**: Vanilla JS only (no framework). Use `async/await` for all API calls. Show loading states.
6. **Secrets**: Never commit `.env`. Use `.env.example` as template.

## Dataset Generation Pipeline

```
User Input (ScenarioDescription)
        │
        ▼
  Extract Keywords (LLM)
        │
        ▼
  Discover Kusto Tables (keyword → table match)
        │
        ▼
  Get Table Schemas + Sample Data
        │
        ▼
  For each complexity level:
    │
    ▼
    Generate Samples (LLM + Kusto context)
        │
        ▼
  Compile GoldenDataset
        │
        ▼
  Store in-memory / Publish to GitHub
```

## API Endpoints

| Method | Endpoint                              | Description                    |
|--------|---------------------------------------|--------------------------------|
| GET    | `/api/health`                         | Health check                   |
| POST   | `/api/datasets/generate`              | Generate a golden dataset      |
| GET    | `/api/datasets`                       | List all datasets              |
| GET    | `/api/datasets/{id}`                  | Get dataset by ID              |
| DELETE | `/api/datasets/{id}`                  | Delete a dataset               |
| POST   | `/api/datasets/{id}/publish`          | Publish dataset to GitHub      |
| GET    | `/api/github/datasets`                | List published datasets        |
| GET    | `/api/kusto/databases`                | List Kusto databases           |
| GET    | `/api/kusto/tables/{db}`              | List tables in database        |
| GET    | `/api/kusto/table/{db}/{table}`       | Get table info                 |
| POST   | `/api/kusto/query`                    | Execute KQL query              |

## Environment Variables

| Variable                   | Required | Description                               |
|---------------------------|----------|-------------------------------------------|
| `KUSTO_CLUSTER_URL`       | Yes      | Kusto cluster URL                         |
| `KUSTO_DATABASE`          | Yes      | Default Kusto database                    |
| `AZURE_OPENAI_ENDPOINT`   | Yes      | Azure OpenAI endpoint                     |
| `AZURE_OPENAI_API_KEY`    | Yes      | Azure OpenAI API key                      |
| `AZURE_OPENAI_DEPLOYMENT` | No       | Model deployment name (default: gpt-4o)   |
| `GITHUB_TOKEN`            | Yes      | GitHub PAT with repo write access         |
| `GITHUB_REPO`             | No       | Target repo (default: jinruishao/CxE-...) |

## Testing

- Use `pytest` for all tests
- Mock external services (Kusto, OpenAI, GitHub) in tests
- Test data generation logic with fixture scenarios

## Common Tasks for Agents

1. **Adding a new scenario category**: Update `ScenarioCategory` enum in `models.py` and `CATEGORY_KEYWORDS` in `dataset_generator.py`
2. **Adding a new API endpoint**: Add route in `app.py`, create request/response models in `models.py`
3. **Improving generation quality**: Modify prompts in `dataset_generator.py` (`SYSTEM_PROMPT`, `GENERATION_PROMPT_TEMPLATE`)
4. **Adding new Kusto data sources**: Update candidate table lists in `kusto_client.py`
5. **UI changes**: Edit `docs/index.html`, `docs/css/styles.css`, `docs/js/app.js`
