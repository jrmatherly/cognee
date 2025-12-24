# Cognee - AI Memory Platform

> **Fork of [topoteretes/cognee](https://github.com/topoteretes/cognee)** with Kubernetes deployment manifests and GHCR container builds.

## Overview

Cognee is an open-source platform that transforms raw data into persistent and dynamic AI memory for agents. It combines vector search with graph databases to make documents both searchable by meaning and connected by relationships. The core concept replaces traditional RAG (Retrieval-Augmented Generation) with scalable ECL (Extract, Cognify, Load) pipelines.

**Current Version**: 0.5.2 (forked from topoteretes/cognee)

## Quick Start

```bash
# Install
uv pip install cognee

# Configure (or use .env file)
export LLM_API_KEY="your-openai-key"

# Run
import cognee
await cognee.add("Your documents here")
await cognee.cognify()
await cognee.memify()
results = await cognee.search("Your query")
```

## Project Structure

```
cognee/
├── cognee/                  # Core Python library
│   ├── api/                 # FastAPI application and versioned routers
│   │   └── v1/              # API v1 (add, cognify, memify, search, delete, datasets, etc.)
│   ├── cli/                 # CLI entry points (cognee-cli)
│   ├── infrastructure/      # Databases, LLM providers, embeddings, loaders, storage adapters
│   ├── modules/             # Domain logic (graph, retrieval, ontology, users, etc.)
│   ├── tasks/               # Reusable tasks (code graph, web scraping, storage)
│   ├── shared/              # Cross-cutting helpers (logging, settings, utils)
│   └── tests/               # Unit, integration, CLI, and e2e tests
├── cognee-mcp/              # Model Context Protocol server (SSE/HTTP/stdio)
├── cognee-frontend/         # Next.js UI for local development
├── deployment/
│   ├── kubernetes/          # Kubernetes manifests (Kustomize + Flux GitOps)
│   └── helm/                # Helm charts
├── distributed/             # Distributed execution utilities (Modal, workers)
├── examples/                # Example scripts demonstrating APIs
├── notebooks/               # Jupyter notebooks for demos
└── alembic/                 # Database migrations
```

## Key Modules (`cognee/modules/`)

| Module | Purpose |
| -------- | --------- |
| `graph/` | Graph database operations and knowledge graph management |
| `retrieval/` | Information retrieval and search |
| `ontology/` | Ontology resolution and management |
| `users/` | User management and authentication |
| `ingestion/` | Data ingestion pipelines |
| `chunking/` | Document chunking strategies |
| `cognify/` | Core cognification (knowledge extraction) logic |
| `memify/` | Memory algorithms and persistence |
| `search/` | Search endpoints and algorithms |
| `storage/` | Storage adapters and management |
| `data/deletion/` | Dataset and data deletion logic |

## Development Commands

### Python Setup (requires Python 3.10-3.13)

```bash
# Install dependencies with uv (recommended)
uv sync --dev --all-extras --reinstall

# Run CLI
uv run cognee-cli add "Cognee turns documents into AI memory."
uv run cognee-cli cognify
uv run cognee-cli search "What does cognee do?"
uv run cognee-cli -ui   # Launches UI, backend API, and MCP server

# Start FastAPI server directly
uv run python -m cognee.api.client

# Run tests
uv run pytest cognee/tests/unit/ -v
uv run pytest cognee/tests/integration/ -v

# Lint and format
uv run ruff check .
uv run ruff format .
```

### MCP Server (`cognee-mcp/`)

```bash
cd cognee-mcp
uv sync --dev --all-extras --reinstall
uv run python src/server.py               # stdio (default)
uv run python src/server.py --transport sse
uv run python src/server.py --transport http --host 127.0.0.1 --port 8000 --path /mcp
```

### Frontend (`cognee-frontend/`)

```bash
cd cognee-frontend
npm install
npm run dev     # Next.js dev server
npm run build && npm start
```

### Docker

```bash
# Backend
docker build -t cognee:local .

# Frontend
docker build -t cognee-frontend:local ./cognee-frontend

# Full stack
docker-compose up
```

## Default Configuration

| Component | Default | Alternatives |
| --------- | ------- | ------------ |
| Relational DB | SQLite | PostgreSQL |
| Vector DB | LanceDB | pgvector, Qdrant, Weaviate, Milvus, ChromaDB |
| Graph DB | Kuzu | Neo4j, Neptune |
| LLM Provider | OpenAI | LiteLLM, Anthropic, Gemini, Mistral, Ollama, Bedrock |

## Container Images (GHCR)

| Component | Image |
| --------- | ----- |
| Backend | `ghcr.io/jrmatherly/cognee-backend:main` |
| Frontend | `ghcr.io/jrmatherly/cognee-frontend:main` |
| MCP Server | `ghcr.io/jrmatherly/cognee-mcp:main` |

All three images use unified versioning from the root `pyproject.toml`. See [RELEASING.md](RELEASING.md) for release procedures.

## Kubernetes Deployment

```
deployment/kubernetes/
├── base/           # Raw Kustomize manifests
│   ├── backend/
│   ├── frontend/
│   └── database/   # CloudNativePG PostgreSQL
└── flux/           # Flux GitOps templates (Jinja2)
    └── app/
```

### Quick Deploy with Kustomize

```bash
kubectl create namespace ai-system
kubectl apply -k deployment/kubernetes/base/
```

### Key Technologies

- **Helm**: bjw-s app-template via OCIRepository
- **Ingress**: Gateway API HTTPRoute (NOT legacy Ingress)
- **Database**: CloudNativePG PostgreSQL 18 with pgvector extension
- **Secrets**: SOPS encryption with age

See [`deployment/kubernetes/README.md`](deployment/kubernetes/README.md) for full documentation.

### Frontend API Proxy Architecture

The Next.js frontend uses **server-side API proxying** for Kubernetes deployment. This solves the problem that `NEXT_PUBLIC_*` environment variables are build-time only (baked into JS bundle), and browsers cannot reach internal K8s service URLs.

```
Browser → Next.js Frontend (K8s) → Backend API (K8s)
         └─ Relative URLs (/api)   └─ Internal service URL
```

**How it works:**
1. Frontend makes relative API calls (e.g., `/api/v1/datasets`, `/backend/health`)
2. Next.js `rewrites()` in `next.config.mjs` proxies requests to backend service
3. `BACKEND_URL` and `MCP_URL` are **runtime** env vars (NOT `NEXT_PUBLIC_`)
4. No CORS issues, backend URL never exposed to browser

**Frontend Environment Variables (K8s):**

| Variable | Value | Purpose |
| ---------- | ------- | --------- |
| `BACKEND_URL` | `http://cognee-backend.ai-system.svc.cluster.local:8000` | Backend API proxy target |
| `MCP_URL` | `http://cognee-mcp.ai-system.svc.cluster.local:8001` | MCP server proxy target |

**Proxy Routes:**

| Browser Path | Proxied To |
| -------------- | ------------ |
| `/api/v1/*` | `${BACKEND_URL}/api/v1/*` |
| `/backend/health` | `${BACKEND_URL}/health` |
| `/mcp/health` | `${MCP_URL}/health` |

## CI/CD Workflows

| Workflow | File | Purpose |
| ---------- | ------ | --------- |
| Backend Build | `ghcr-backend.yml` | Build/push backend container on push to main/dev |
| Frontend Build | `ghcr-frontend.yml` | Build/push frontend container on push to main/dev |
| MCP Server Build | `ghcr-mcp.yml` | Build/push MCP server container on push to main/dev |
| Release | `release.yml` | Manual release (GitHub Release + GHCR) |

Features: Multi-arch (amd64/arm64), Trivy scanning, Cosign signing, SBOM/provenance.

**Note**: PyPI publishing is disabled in this fork (package owned by upstream).

## API Endpoints

Base URL: `http://localhost:8000/api/v1`

| Endpoint | Method | Description |
| ---------- | -------- | ------------- |
| `/add` | POST | Add documents to cognee |
| `/cognify` | POST | Generate knowledge graph from added data |
| `/memify` | POST | Add memory algorithms to the graph |
| `/search` | POST | Query the knowledge graph |
| `/delete` | DELETE | Delete data from cognee |
| `/datasets` | GET/DELETE | Manage datasets |
| `/health` | GET | Health check |

### Frontend Health Endpoint

The frontend exposes `/api/health` for Kubernetes probes (added for k8s deployment).

## Coding Style

- **Python**: 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes
- **Line length**: 100 characters (configured in `pyproject.toml`)
- **Linting**: `ruff check` and `ruff format` before committing
- **Logging**: Use `cognee.shared.logging_utils`
- **Type hints**: Preferred for public APIs

## Testing Guidelines

- Unit tests: `cognee/tests/unit/`
- Integration tests: `cognee/tests/integration/`
- CLI tests: `cognee/tests/cli_tests/`
- Name test files `test_*.py`
- Use `pytest.mark.asyncio` for async tests

## Commit Guidelines

Use conventional commits:
- `feat(graph): add temporal edge weighting`
- `fix(api): handle missing auth cookie`
- `docs: update installation instructions`

Sign commits and affirm DCO (see `CONTRIBUTING.md`).

## Recent Updates

### Version 0.5.2 (2025-12-16)

- **Frontend API Proxy**: Fixed K8s deployment connectivity by implementing Next.js rewrites
  - Browser calls use relative URLs (no `localhost` hardcoded)
  - Next.js server proxies to backend via `BACKEND_URL` and `MCP_URL` runtime env vars
  - Resolves `ERR_CONNECTION_REFUSED` errors in K8s deployments
- **Updated K8s manifests**: Both Kustomize base and Flux templates now use runtime env vars

### Version 0.5.1 (2025-12-15)

- **Database init fix**: Improved entrypoint.sh database initialization

### Version 0.5.0 (2025-12-15)

Major release with significant infrastructure and feature updates.

#### Fork-Specific Changes

- **GHCR Migration**: Moved from DockerHub to GitHub Container Registry
- **Kubernetes Manifests**: Added Kustomize base and Flux GitOps templates
- **CloudNativePG**: PostgreSQL 18 with pgvector extension
- **Gateway API**: Using HTTPRoute instead of legacy Ingress
- **Frontend Health Endpoint**: Added `/api/health` for k8s probes
- **CI/CD Overhaul**: Multi-arch builds, Trivy scanning, Cosign signing

#### Upstream Changes (v0.5.0)

- **Bedrock Support**: Added AWS Bedrock as LLM provider
- **Dataset Database Handlers**: Neo4j, LanceDB, Kuzu handlers with database deletion on dataset delete
- **Pipeline Cache**: Made processing cache optional
- **Edge-Centered Payload**: New embedding structure during ingestion
- **Ontology Improvements**: Removed file size limit, single file upload endpoint
- **Custom LLM Parameters**: Support for custom parameters in LLM adapters during cognify

### Removed/Archived

- DockerHub workflows (now using GHCR)
- Discord release notification workflow
- Contributors update workflow

## Environment Variables

Key environment variables for configuration:

```bash
# LLM Configuration
LLM_API_KEY=           # Required: OpenAI/provider API key
LLM_MODEL=             # Optional: Model name
LLM_PROVIDER=          # Optional: Provider (openai, anthropic, etc.)
LLM_ENDPOINT=          # Optional: Custom endpoint
LLM_MAX_TOKENS=        # Optional: Max tokens

# Embedding Configuration
EMBEDDING_PROVIDER=    # Optional: fastembed (default), openai, etc.
EMBEDDING_MODEL=       # Optional: Model name
EMBEDDING_DIMENSIONS=  # Optional: Vector dimensions
EMBEDDING_API_KEY=     # Optional: If different from LLM key

# Database Configuration
DB_PROVIDER=           # sqlite (default), postgres
DB_HOST=               # For postgres
DB_PORT=               # For postgres
DB_NAME=               # For postgres
DB_USERNAME=           # For postgres
DB_PASSWORD=           # For postgres

# Vector Database
VECTOR_DB_PROVIDER=    # lancedb (default), pgvector, qdrant, etc.

# Graph Database
GRAPH_DATABASE_PROVIDER=   # kuzu (default), neo4j
GRAPH_DATABASE_URL=        # For neo4j
GRAPH_DATABASE_PASSWORD=   # For neo4j

# Frontend (Kubernetes deployment only)
BACKEND_URL=               # Backend API URL for Next.js proxy (e.g., http://cognee-backend:8000)
MCP_URL=                   # MCP server URL for Next.js proxy (e.g., http://cognee-mcp:8001)
```

## Important Files

| File | Purpose |
| ------ | --------- |
| `RELEASING.md` | **Release procedures and versioning guide** |
| `AGENTS.md` | Detailed build, test, and development commands |
| `CONTRIBUTING.md` | Contribution guidelines and DCO |
| `deployment/kubernetes/README.md` | Full Kubernetes deployment docs |
| `deployment/kubernetes/flux/variables.md` | Flux GitOps variable reference |
| `cognee-mcp/README.md` | MCP server documentation |

## License

Apache-2.0
