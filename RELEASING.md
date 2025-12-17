# Cognee Release Guide

This document describes how to release new versions of Cognee, including versioning conventions, files to update, and the release workflow.

## Versioning Strategy

Cognee uses **unified versioning** across all components. All three container images (backend, frontend, MCP) share the same version number derived from the root `pyproject.toml`.

### Version Files

When preparing a release, update the version in these files:

| File | Field | Purpose |
|------|-------|---------|
| `pyproject.toml` | `version = "X.Y.Z"` | **Primary source of truth** - release workflow reads this |
| `cognee-frontend/package.json` | `"version": "X.Y.Z"` | Frontend package version (should match) |
| `cognee-mcp/pyproject.toml` | `version = "X.Y.Z"` | MCP server package version (should match) |

### Version Format

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR** (X): Breaking API changes
- **MINOR** (Y): New features, backward compatible
- **PATCH** (Z): Bug fixes, backward compatible

Example: `0.5.8`

## Pre-Release Checklist

Before creating a release:

1. **Update version numbers** in all three files listed above
2. **Update CHANGELOG** (if maintained)
3. **Run tests**: `uv run pytest cognee/tests/unit/ -v`
4. **Run linting**: `uv run ruff check . && uv run ruff format --check .`
5. **Commit changes**: `git commit -s -m "chore: bump version to X.Y.Z"`
6. **Push to `dev` branch** for testing

## Release Workflow

### Manual Release via GitHub Actions

1. Go to **Actions** → **release.yml** → **Run workflow**
2. Select branch:
   - `dev` for pre-release/testing
   - `main` for production release
3. Click **Run workflow**

The workflow will:
- Extract version from `pyproject.toml`
- Create and push git tag `vX.Y.Z`
- Create GitHub Release with auto-generated notes
- Build and push all three container images:
  - `ghcr.io/jrmatherly/cognee-backend:X.Y.Z`
  - `ghcr.io/jrmatherly/cognee-frontend:X.Y.Z`
  - `ghcr.io/jrmatherly/cognee-mcp:X.Y.Z`
- Sign images with Cosign
- Tag `main` releases as `latest`

### Container Image Tags

| Branch | Tags Applied |
|--------|-------------|
| `main` | `X.Y.Z`, `latest` |
| `dev` | `X.Y.Z` only |

## CI/CD Build Triggers

### Automatic Builds (on push)

| Workflow | Image | Triggers |
|----------|-------|----------|
| `ghcr-backend.yml` | `cognee-backend` | Changes to `cognee/`, `Dockerfile`, `pyproject.toml`, `uv.lock` |
| `ghcr-frontend.yml` | `cognee-frontend` | Changes to `cognee-frontend/` |
| `ghcr-mcp.yml` | `cognee-mcp` | Changes to `cognee-mcp/`, `cognee/`, `alembic/`, `pyproject.toml`, `uv.lock` |

### CI Build Tags

CI builds (non-release) produce:
- `main` or `dev` (branch name)
- `main-abc1234` or `dev-abc1234` (branch + short SHA)
- `latest` (main branch only)

## MCP Server Modes

The MCP server supports two operating modes:

### API Mode (Recommended for Kubernetes)

MCP proxies all operations to the backend API:

```yaml
env:
  API_URL: "http://cognee-backend.ai-system.svc.cluster.local:8000"
```

**Benefits:**
- Smaller image size
- Single source of truth for cognee logic
- Backend handles all database operations

### Direct Mode (Default for local development)

MCP embeds the full cognee library:

```bash
# No API_URL set - uses embedded cognee
cognee-mcp --transport stdio
```

**Use cases:**
- Local development
- Single-container deployments
- IDE integrations (Claude Desktop, Cursor)

## Kubernetes Deployment

After a release, update your Kubernetes manifests:

### Kustomize (base/)

Update image tag in `deployment/kubernetes/base/backend/deployment.yaml`:
```yaml
image: ghcr.io/jrmatherly/cognee-backend:X.Y.Z
```

### Flux GitOps (flux/)

Update `cognee_version` in your `cluster.yaml`:
```yaml
cognee_version: "X.Y.Z"
```

## Rollback Procedure

If a release has issues:

1. **Kubernetes**: Update image tag to previous version
2. **GitHub**: Mark release as pre-release or delete if needed
3. **Git**: Do NOT delete tags (they're referenced in release notes)

## PyPI Publishing

PyPI publishing is **disabled** in this fork - the `cognee` package on PyPI is owned by the upstream repository (topoteretes/cognee).

## Troubleshooting

### Version Mismatch Errors

If MCP fails with version errors:
1. Check `cognee-mcp/pyproject.toml` has correct cognee dependency version
2. Rebuild MCP image: `docker build -f cognee-mcp/Dockerfile -t cognee-mcp:local .`

### Build Failures

If CI builds fail:
1. Check disk space (MCP builds need aggressive cleanup)
2. Verify `uv.lock` is committed and up-to-date
3. Check for breaking changes in cognee dependencies

### Image Not Found

If deployment can't pull image:
1. Verify image exists: `docker pull ghcr.io/jrmatherly/cognee-backend:X.Y.Z`
2. Check GHCR package visibility (should be public)
3. Verify tag matches exactly (case-sensitive)
