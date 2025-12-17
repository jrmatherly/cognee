# Cognee Flux GitOps Templates

This directory contains Flux GitOps templates for deploying Cognee to a Talos-based Kubernetes cluster.

## Template Syntax

These templates use **Jinja2** with custom delimiters to avoid conflicts with Helm/Go templates:

| Purpose | Delimiter | Example |
|---------|-----------|---------|
| Variables | `#{...}#` | `#{ cognee_version \| default('main') }#` |
| Blocks | `#%...%#` | `#% if cognee_enabled %#` |
| Comments | `#\|...\|#` | `#\| This is a comment \|#` |

## Files

| File | Description |
|------|-------------|
| `ks.yaml.j2` | Flux Kustomization (entry point) |
| `variables.md` | Required cluster variables documentation |
| `app/ocirepository.yaml.j2` | bjw-s app-template OCI source |
| `app/helmrelease.yaml.j2` | HelmRelease using app-template |
| `app/secret.sops.yaml.j2` | SOPS-encrypted secrets |
| `app/postgresql.yaml.j2` | CloudNativePG database cluster |
| `app/httproute.yaml.j2` | Gateway API HTTPRoutes |
| `app/networkpolicy.yaml.j2` | Network security policies |
| `app/kustomization.yaml.j2` | Kustomize resource list |

## Integration Steps

### 1. Copy Templates

Copy the Flux templates to your cluster repository:

```bash
# In your talos-k8s-cluster repository
mkdir -p templates/config/kubernetes/apps/ai-system/cognee/
cp -r flux/* templates/config/kubernetes/apps/ai-system/cognee/
```

### 2. Configure Variables

Add Cognee variables to your `cluster.yaml`:

```yaml
# Enable Cognee
cognee_enabled: true
cognee_frontend_enabled: true

# Hostnames
cognee_frontend_hostname: "cognee.internal.example.com"
cognee_api_hostname: "cognee-api.internal.example.com"
cognee_frontend_url: "https://cognee.internal.example.com"

# LLM Configuration
cognee_llm_model: "gpt-5-mini"
cognee_embedding_model: "text-embedding-3-large"

# Secrets (encrypt with SOPS)
cognee_db_password: "your-secure-password"
cognee_neo4j_password: "your-neo4j-password"
```

See [variables.md](variables.md) for all available options.

### 3. Encrypt Secrets

Encrypt sensitive values using SOPS with age:

```bash
# Get your age public key
age-keygen -y ~/.config/sops/age/keys.txt

# Edit cluster.yaml and encrypt secrets
sops --encrypt --age AGE_PUBLIC_KEY cluster.yaml > cluster.sops.yaml
```

### 4. Render Templates

Run your Jinja2 template rendering pipeline:

```bash
# Example using your cluster's rendering script
./scripts/render-templates.sh
```

### 5. Commit and Push

```bash
git add kubernetes/apps/ai-system/cognee/
git commit -m "feat(cognee): add Cognee deployment"
git push
```

### 6. Verify Deployment

```bash
# Check Flux reconciliation
flux get kustomization cognee -n flux-system

# Check pods
kubectl get pods -n ai-system -l app.kubernetes.io/part-of=cognee

# Check HelmRelease
flux get helmrelease cognee -n ai-system
```

## Dependencies

The Kustomization declares dependencies on:

- `cilium` (kube-system) - CNI
- `cloudnative-pg` (cnpg-system) - PostgreSQL operator
- `envoy-gateway` (network) - Gateway API
- `neo4j` (storage) - Graph database (optional)
- `litellm` (ai-system) - LLM proxy (optional)

Ensure these are deployed before enabling Cognee.

## Customization

### Using Different Gateways

```yaml
# External access via Cloudflare Tunnel
cognee_gateway: "envoy-external"
cognee_api_gateway: "envoy-external"

# AI-specific gateway (if configured)
cognee_gateway: "envoy-ai"
```

### Scaling

```yaml
# Backend replicas
cognee_backend_replicas: 3

# Frontend replicas
cognee_frontend_replicas: 2

# Database instances (CloudNativePG)
cognee_db_instances: 3
```

### Resource Limits

```yaml
# Backend resources
cognee_backend_resources_requests_cpu: "500m"
cognee_backend_resources_requests_memory: "1Gi"
cognee_backend_resources_limits_cpu: "4000m"
cognee_backend_resources_limits_memory: "8Gi"

# Frontend resources
cognee_frontend_resources_requests_cpu: "200m"
cognee_frontend_resources_requests_memory: "512Mi"
```

### Database Backup

```yaml
# Enable S3-compatible backups
cognee_db_backup_enabled: true
cognee_db_backup_destination: "s3://cognee-backups/cluster-1/"
cognee_db_backup_retention: "30d"
```

## Troubleshooting

### Template Rendering Issues

Check the Jinja2 output:

```bash
# Render templates manually for debugging
jinja2 -D cognee_enabled=true ks.yaml.j2
```

### Flux Reconciliation

```bash
# Force reconciliation
flux reconcile kustomization cognee -n flux-system

# Check events
kubectl events -n ai-system --for=helmrelease/cognee
```

### HelmRelease Issues

```bash
# Get HelmRelease status
kubectl describe helmrelease cognee -n ai-system

# Check Helm history
helm history cognee -n ai-system
```

### Database Issues

```bash
# Check CNPG cluster status
kubectl get cluster cognee-db -n ai-system

# View PostgreSQL logs
kubectl logs -n ai-system -l cnpg.io/cluster=cognee-db
```

## Image Sources

| Component | Image |
|-----------|-------|
| Backend | `ghcr.io/jrmatherly/cognee:main` |
| Frontend | `ghcr.io/jrmatherly/cognee-frontend:main` |
| PostgreSQL | `ghcr.io/cloudnative-pg/postgresql:18-minimal-trixie` |
| pgvector | `ghcr.io/cloudnative-pg/pgvector:0.8.1-18-trixie` |

For upstream images, change `jrmatherly` to `topoteretes`.
