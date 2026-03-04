# CxE Care Evaluation Agent

Generate high-quality **golden evaluation datasets** for AI agents in Microsoft CxE support scenarios — powered by Kusto data & Azure OpenAI.

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/jinruishao/CxE-Care-Evaluations.git
cd CxE-Care-Evaluations
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your actual credentials:
#   - KUSTO_CLUSTER_URL
#   - AZURE_OPENAI_ENDPOINT / API_KEY
#   - GITHUB_TOKEN
```

### 3. Run the API Server

```bash
uvicorn backend.app:app --reload --port 8000
```

### 4. Open the UI

- **Local**: Open `docs/index.html` in your browser, or visit `http://localhost:8000`
- **GitHub Pages**: [https://jinruishao.github.io/CxE-Care-Evaluations/](https://jinruishao.github.io/CxE-Care-Evaluations/)

## How It Works

1. **Describe** your evaluation scenario (e.g., "Test case triage accuracy for Sev1 incidents")
2. **Discover** — The agent finds relevant Kusto tables and schemas
3. **Generate** — Azure OpenAI creates diverse samples (simple → complex → edge cases)
4. **Publish** — Export to JSON or push directly to this GitHub repo

## Features

- **Kusto-grounded generation** — Uses real table schemas & sample data from `cxedataplatformcluster`
- **Multi-complexity** — Generates simple, moderate, complex, and edge-case scenarios
- **Interactive UI** — Web-based interface for generating, browsing, and publishing datasets
- **GitHub integration** — One-click publish to this repo with auto-generated READMEs
- **Kusto Explorer** — Browse databases, tables, and run KQL queries from the UI

## Project Structure

```
├── backend/           # Python FastAPI backend
│   ├── app.py         # API routes
│   ├── kusto_client.py    # Kusto/ADX integration
│   ├── dataset_generator.py   # Core generation logic
│   └── github_storage.py  # GitHub publishing
├── docs/              # GitHub Pages UI
│   ├── index.html
│   ├── css/styles.css
│   └── js/app.js
├── datasets/          # Generated golden datasets
├── AGENTS.md          # AI agent guidelines
└── requirements.txt
```

## Kusto Cluster

**Cluster URL:** `https://cxedataplatformcluster.westus2.kusto.windows.net`

Requires Azure AD authentication. Run `az login` before starting the server.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/datasets/generate` | POST | Generate a golden dataset |
| `/api/datasets` | GET | List all datasets |
| `/api/datasets/{id}` | GET | Get dataset by ID |
| `/api/datasets/{id}/publish` | POST | Publish to GitHub |
| `/api/kusto/databases` | GET | List Kusto databases |
| `/api/kusto/tables/{db}` | GET | List tables |
| `/api/kusto/query` | POST | Execute KQL query |

## Contributing

See [AGENTS.md](AGENTS.md) for coding conventions and architecture details.

## License

Microsoft Internal
