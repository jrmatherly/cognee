# Cognee Kubernetes Deployment

This directory contains Kubernetes deployment manifests for the Cognee knowledge graph platform.

## Directory Structure

```
deployment/kubernetes/
├── README.md                    # This file
├── base/                        # Raw Kubernetes manifests (Kustomize base)
│   ├── kustomization.yaml
│   ├── backend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   ├── networkpolicy.yaml
│   │   └── serviceaccount.yaml
│   ├── frontend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   ├── networkpolicy.yaml
│   │   └── serviceaccount.yaml
│   └── database/
│       └── postgresql.yaml      # CloudNativePG Cluster
│
└── flux/                        # Flux GitOps templates (Jinja2)
    ├── README.md                # Flux integration guide
    ├── ks.yaml.j2               # Flux Kustomization
    ├── variables.md             # Required cluster.yaml variables
    └── app/
        ├── kustomization.yaml.j2
        ├── ocirepository.yaml.j2
        ├── helmrelease.yaml.j2
        ├── secret.sops.yaml.j2
        ├── postgresql.yaml.j2
        ├── httproute.yaml.j2
        └── networkpolicy.yaml.j2
```

## Deployment Options

### Option 1: Kustomize (Direct)

For clusters without Flux GitOps, use the base manifests directly:

```bash
# Create namespace
kubectl create namespace ai-system

# Generate JWT secrets (REQUIRED - v0.5.2+)
JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
RESET_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
VERIFY_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(64))")

# Create secrets (manually)
kubectl create secret generic cognee-secrets \
  --namespace ai-system \
  --from-literal=DB_PASSWORD='your-password' \
  --from-literal=GRAPH_DATABASE_PASSWORD='your-neo4j-password' \
  --from-literal=LLM_API_KEY='your-llm-key' \
  --from-literal=FASTAPI_USERS_JWT_SECRET="${JWT_SECRET}" \
  --from-literal=FASTAPI_USERS_RESET_PASSWORD_TOKEN_SECRET="${RESET_SECRET}" \
  --from-literal=FASTAPI_USERS_VERIFICATION_TOKEN_SECRET="${VERIFY_SECRET}"

# Apply base manifests
kubectl apply -k deployment/kubernetes/base/
```

> **⚠️ IMPORTANT (v0.5.2+)**: The JWT secrets are **required**. The backend will fail to start without them.

### Option 2: Flux GitOps (Recommended)

For Talos-based clusters using Flux GitOps with Jinja2 templating:

1. Copy the `flux/` templates to your cluster repository
2. Configure variables in `cluster.yaml` (see `flux/variables.md`)
3. Let Flux reconcile the manifests

See [flux/README.md](flux/README.md) for detailed instructions.

## Components

### Backend API

- **Image**: `ghcr.io/jrmatherly/cognee:main`
- **Port**: 8000
- **Health Check**: `/health`
- **Dependencies**:
  - PostgreSQL (CloudNativePG)
  - Neo4j (graph database)
  - LiteLLM (LLM proxy)

### Frontend

- **Image**: `ghcr.io/jrmatherly/cognee-frontend:main`
- **Port**: 3000
- **Health Check**: `/api/health`
- **Security**: Runs as UID 10001 (non-root)
- **Dependencies**:
  - Backend API
  - Auth0 (optional authentication)

### Database (PostgreSQL)

- **Operator**: CloudNativePG
- **Extensions**: pgvector, pg_trgm
- **Replicas**: 3 (default)
- **Storage**: 10Gi (default)

## Prerequisites

- Kubernetes 1.28+
- CloudNativePG operator
- Envoy Gateway (for Gateway API)
- Neo4j (in `storage` namespace)
- LiteLLM proxy (optional but recommended)

## Configuration

### Environment Variables

See the ConfigMap files for available configuration options:

- `base/backend/configmap.yaml` - Backend configuration
- `base/frontend/configmap.yaml` - Frontend configuration

### Secrets

Required secrets in `cognee-secrets`:

| Key | Required | Description |
|-----|----------|-------------|
| `DB_PASSWORD` | ✅ | PostgreSQL password |
| `GRAPH_DATABASE_PASSWORD` | ✅ | Neo4j password |
| `LLM_API_KEY` | ✅ | LiteLLM/OpenAI API key |
| `FASTAPI_USERS_JWT_SECRET` | ✅ | **JWT secret (v0.5.2+, min 32 chars, 64+ recommended)** |
| `FASTAPI_USERS_RESET_PASSWORD_TOKEN_SECRET` | ✅ | Password reset token secret (v0.5.2+) |
| `FASTAPI_USERS_VERIFICATION_TOKEN_SECRET` | ✅ | Email verification token secret (v0.5.2+) |
| `OIDC_CLIENT_ID` | ❌ | OIDC client ID (if OIDC enabled) |
| `OIDC_CLIENT_SECRET` | ❌ | OIDC client secret (if OIDC enabled) |
| `AUTH0_DOMAIN` | ❌ | Auth0 domain (legacy frontend auth) |
| `AUTH0_CLIENT_ID` | ❌ | Auth0 client ID (legacy frontend auth) |
| `AUTH0_CLIENT_SECRET` | ❌ | Auth0 client secret (legacy) |
| `AUTH0_SECRET` | ❌ | Auth0 session secret (legacy) |

**Generate JWT secrets with:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Security Configuration (v0.5.2+)

Available in `cognee-config` ConfigMap:

| Key | Default | Description |
|-----|---------|-------------|
| `AUTH_RATE_LIMIT_ENABLED` | `true` | Enable auth rate limiting |
| `AUTH_RATE_LIMIT_LOGIN_REQUESTS` | `5` | Max login attempts per window |
| `AUTH_RATE_LIMIT_LOGIN_WINDOW` | `300` | Rate limit window in seconds |
| `SSRF_PROTECTION_ENABLED` | `true` | Block requests to private IPs |
| `ALLOW_PRIVATE_URLS` | `false` | Allow fetching from private networks |
| `OAUTH_STATE_TTL` | `600` | OAuth state expiry in seconds |

### Multi-Replica Deployments

For deployments with `replicas > 1`, configure Redis for OAuth state storage:

```yaml
# In ConfigMap
OAUTH_STATE_REDIS_URL: "redis://redis.ai-system.svc.cluster.local:6379/0"
```

Without Redis, OAuth authentication will fail when requests hit different pods.

## Known Issues

### Alembic Migration Bug

The backend `entrypoint.sh` runs Alembic migrations before SQLAlchemy creates base tables. The init container in the deployment works around this by pre-creating required schema objects.

### Neo4j Community Edition

Cannot run multiple replicas (Enterprise-only feature). Deploy as single replica.

## Network Policies

Network policies are included to restrict traffic:

- **Backend**: Allows ingress from frontend and gateway; egress to PostgreSQL, Neo4j, LiteLLM, and DNS
- **Frontend**: Allows ingress from gateway; egress to backend, Auth0 (external), and DNS

## Monitoring

If Prometheus is deployed, enable PodMonitor:

```yaml
cognee_db_monitoring_enabled: true
```

The backend exposes metrics at `/metrics` (if enabled).

## Troubleshooting

### Backend fails to start with JWTSecretError

If you see `JWTSecretError: FASTAPI_USERS_JWT_SECRET environment variable is required`:

```bash
# Check if secrets exist
kubectl get secret cognee-secrets -n ai-system -o yaml | grep FASTAPI

# Recreate secrets with JWT values
JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
kubectl patch secret cognee-secrets -n ai-system --type merge -p \
  "{\"stringData\":{\"FASTAPI_USERS_JWT_SECRET\":\"${JWT_SECRET}\"}}"
```

### OAuth login fails in multi-replica deployment

Without Redis, OAuth state is stored in-memory and lost when requests hit different pods:

```bash
# Configure Redis URL
kubectl patch configmap cognee-config -n ai-system --type merge -p \
  '{"data":{"OAUTH_STATE_REDIS_URL":"redis://redis.ai-system.svc.cluster.local:6379/0"}}'

# Restart backend
kubectl rollout restart deployment/cognee-backend -n ai-system
```

### Check pod status

```bash
kubectl get pods -n ai-system -l app.kubernetes.io/part-of=cognee
```

### View logs

```bash
# Backend
kubectl logs -n ai-system -l app.kubernetes.io/component=backend

# Frontend
kubectl logs -n ai-system -l app.kubernetes.io/component=frontend
```

### Check database connectivity

```bash
kubectl exec -n ai-system -it deploy/cognee-backend -- \
  psql -h cognee-db-rw -U cognee -d cognee -c "SELECT 1"
```

### Verify health endpoints

```bash
# Backend
kubectl exec -n ai-system -it deploy/cognee-backend -- \
  curl -s http://localhost:8000/health | jq

# Frontend
kubectl exec -n ai-system -it deploy/cognee-frontend -- \
  wget -qO- http://localhost:3000/api/health
```
