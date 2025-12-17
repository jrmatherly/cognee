# Cognee Flux Variables

This document describes all variables required for the Cognee Flux deployment templates.

## Required Variables

These variables **must** be defined in your `cluster.yaml` configuration:

| Variable | Type | Description |
|----------|------|-------------|
| `cognee_enabled` | boolean | Enable/disable Cognee deployment |
| `cognee_db_password` | string | PostgreSQL database password (SOPS encrypted) |
| `cognee_neo4j_password` | string | Neo4j graph database password (SOPS encrypted) |
| `cognee_jwt_secret` | string | **JWT secret for authentication (SOPS encrypted, min 32 chars)** |

### Security Secrets (v0.5.2+)

| Variable | Type | Description |
|----------|------|-------------|
| `cognee_jwt_secret` | string | **REQUIRED** - JWT secret (SOPS encrypted, 64+ chars recommended) |
| `cognee_reset_password_token_secret` | string | Reset password token secret (defaults to `cognee_jwt_secret`) |
| `cognee_verification_token_secret` | string | Verification token secret (defaults to `cognee_jwt_secret`) |

**Generate secrets with:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Optional Variables (with defaults)

### Deployment Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_version` | `main` | Backend container image tag |
| `cognee_backend_replicas` | `1` | Number of backend replicas |
| `cognee_frontend_enabled` | `true` | Enable frontend deployment |
| `cognee_frontend_version` | `main` | Frontend container image tag |
| `cognee_frontend_replicas` | `1` | Number of frontend replicas |
| `cognee_app_template_version` | `4.5.0` | bjw-s app-template chart version |

### Networking

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_gateway` | `envoy-internal` | Gateway for frontend traffic |
| `cognee_api_gateway` | `envoy-internal` | Gateway for API traffic |
| `cognee_frontend_hostname` | `cognee.example.com` | Frontend hostname |
| `cognee_api_hostname` | `cognee-api.example.com` | Backend API hostname |
| `cognee_frontend_url` | `https://cognee.example.com` | Full frontend URL (for OAuth) |

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_llm_model` | `gpt-4o-mini` | LLM model name |
| `cognee_embedding_model` | `text-embedding-3-large` | Embedding model name |
| `cognee_litellm_api_key` | `${litellm_master_key}` | LiteLLM API key |

### Security Settings (v0.5.2+)

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_auth_rate_limit_enabled` | `true` | Enable auth rate limiting |
| `cognee_auth_rate_limit_login_requests` | `5` | Login attempts per window |
| `cognee_auth_rate_limit_login_window` | `300` | Login rate limit window (seconds) |
| `cognee_ssrf_protection_enabled` | `true` | Enable SSRF protection |
| `cognee_allow_private_urls` | `false` | Allow fetching private IPs |
| `cognee_oauth_state_redis_url` | `` | Redis URL for OAuth state (multi-pod) |

### OIDC/Keycloak Authentication (v0.5.2+)

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_oidc_enabled` | `false` | Enable OIDC authentication |
| `cognee_oidc_provider_name` | `keycloak` | OIDC provider name |
| `cognee_oidc_client_id` | `` | OIDC client ID (SOPS encrypted) |
| `cognee_oidc_client_secret` | `` | OIDC client secret (SOPS encrypted) |
| `cognee_oidc_server_metadata_url` | `` | OIDC discovery URL |
| `cognee_oidc_scopes` | `openid profile email` | OIDC scopes |
| `cognee_oidc_default_role` | `viewer` | Default role for new users |

### Auth0 Configuration (Legacy Frontend)

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_auth0_domain` | `` | Auth0 domain |
| `cognee_auth0_client_id` | `` | Auth0 client ID |
| `cognee_auth0_client_secret` | `` | Auth0 client secret (SOPS encrypted) |
| `cognee_auth0_secret` | `` | Auth0 session secret (SOPS encrypted) |

### Backend Resources

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_backend_resources_requests_cpu` | `200m` | CPU request |
| `cognee_backend_resources_requests_memory` | `512Mi` | Memory request |
| `cognee_backend_resources_limits_cpu` | `2000m` | CPU limit |
| `cognee_backend_resources_limits_memory` | `4Gi` | Memory limit |

### Frontend Resources

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_frontend_resources_requests_cpu` | `100m` | CPU request |
| `cognee_frontend_resources_requests_memory` | `256Mi` | Memory request |
| `cognee_frontend_resources_limits_cpu` | `500m` | CPU limit |
| `cognee_frontend_resources_limits_memory` | `512Mi` | Memory limit |

### Database Configuration (CloudNativePG)

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_db_instances` | `3` | Number of PostgreSQL replicas |
| `cognee_db_storage_size` | `10Gi` | Storage size per instance |
| `cognee_db_storage_class` | `proxmox-csi` | Storage class name |
| `cognee_db_shared_buffers` | `256MB` | PostgreSQL shared_buffers |
| `cognee_db_effective_cache_size` | `768MB` | PostgreSQL effective_cache_size |
| `cognee_db_monitoring_enabled` | `true` | Enable PodMonitor for Prometheus |

### Database Resources

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_db_resources_requests_cpu` | `500m` | CPU request |
| `cognee_db_resources_requests_memory` | `1Gi` | Memory request |
| `cognee_db_resources_limits_cpu` | `2000m` | CPU limit |
| `cognee_db_resources_limits_memory` | `4Gi` | Memory limit |

### Database Backup (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `cognee_db_backup_enabled` | `false` | Enable S3-compatible backups |
| `cognee_db_backup_destination` | - | S3 backup destination path |
| `cognee_db_backup_retention` | `30d` | Backup retention period |

### Dependencies

| Variable | Default | Description |
|----------|---------|-------------|
| `neo4j_enabled` | `false` | Wait for Neo4j dependency |
| `litellm_enabled` | `false` | Wait for LiteLLM dependency |

## Example cluster.yaml Configuration

```yaml
# Cognee Knowledge Graph Platform
cognee_enabled: true
cognee_version: "main"
cognee_frontend_enabled: true
cognee_frontend_version: "main"

# Hostnames
cognee_frontend_hostname: "cognee.internal.example.com"
cognee_api_hostname: "cognee-api.internal.example.com"
cognee_frontend_url: "https://cognee.internal.example.com"

# Gateway (use envoy-internal for LAN, envoy-external for internet)
cognee_gateway: "envoy-internal"
cognee_api_gateway: "envoy-internal"

# LLM Configuration (via LiteLLM proxy)
cognee_llm_model: "gpt-4o-mini"
cognee_embedding_model: "text-embedding-3-large"

#############################################################################
# Security Settings (v0.5.2+ - REQUIRED)
#############################################################################

# JWT Secrets - REQUIRED for backend to start
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"
cognee_jwt_secret: "ENC[AES256_GCM,data:...]"  # SOPS encrypted
cognee_reset_password_token_secret: "ENC[AES256_GCM,data:...]"  # Optional, defaults to jwt_secret
cognee_verification_token_secret: "ENC[AES256_GCM,data:...]"  # Optional, defaults to jwt_secret

# OAuth State Storage (REQUIRED for multi-replica deployments)
# Without Redis, OAuth login will fail when requests hit different pods
cognee_oauth_state_redis_url: "redis://redis.ai-system.svc.cluster.local:6379/0"

# Rate Limiting (defaults shown, adjust as needed)
cognee_auth_rate_limit_enabled: true
cognee_auth_rate_limit_login_requests: 5
cognee_auth_rate_limit_login_window: 300

# SSRF Protection (enabled by default for security)
cognee_ssrf_protection_enabled: true
cognee_allow_private_urls: false

#############################################################################
# OIDC/Keycloak Authentication (Optional)
#############################################################################
cognee_oidc_enabled: false
# cognee_oidc_provider_name: "keycloak"
# cognee_oidc_client_id: "ENC[AES256_GCM,data:...]"
# cognee_oidc_client_secret: "ENC[AES256_GCM,data:...]"
# cognee_oidc_server_metadata_url: "https://keycloak.example.com/realms/cognee/.well-known/openid-configuration"

# Auth0 (Legacy - leave empty to disable)
cognee_auth0_domain: ""
cognee_auth0_client_id: ""

# Database
cognee_db_instances: 3
cognee_db_storage_size: "20Gi"

# Secrets (SOPS encrypted in cluster-secrets)
cognee_db_password: "ENC[AES256_GCM,data:...]"
cognee_neo4j_password: "ENC[AES256_GCM,data:...]"
cognee_auth0_client_secret: "ENC[AES256_GCM,data:...]"
cognee_auth0_secret: "ENC[AES256_GCM,data:...]"

# Dependencies
neo4j_enabled: true
litellm_enabled: true
```

## Notes

1. **Image Registry**: Images are pulled from `ghcr.io/jrmatherly/cognee[-frontend]`. For the upstream repository, change to `ghcr.io/topoteretes/cognee[-frontend]`.

2. **SOPS Encryption**: All sensitive values should be encrypted using SOPS with age encryption before committing to Git.

3. **Gateway Selection**:
   - `envoy-internal`: Internal LAN traffic only
   - `envoy-external`: Internet-facing via Cloudflare Tunnel
   - `envoy-ai`: AI/LLM-specific routing (if configured)

4. **Database**: Uses CloudNativePG operator. Ensure `cloudnative-pg` is deployed before enabling Cognee.

5. **Neo4j**: Community Edition only supports single replica. Enterprise license required for clustering.

6. **Security (v0.5.2+)**:
   - **JWT Secrets are REQUIRED** - Backend will fail to start without them
   - Generate secrets with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
   - Secrets must be at least 32 characters (64+ recommended)
   - **OAuth State Storage**: For multi-replica deployments, configure Redis (`cognee_oauth_state_redis_url`) or OAuth login will fail across pods
   - **Rate Limiting**: Enabled by default to protect against brute force attacks
   - **SSRF Protection**: Enabled by default to prevent server-side request forgery

7. **Multi-Replica Deployments**:
   - Requires Redis for OAuth state storage (`cognee_oauth_state_redis_url`)
   - Without Redis, OAuth authentication will fail when requests hit different pods
   - Recommended: Deploy Redis alongside Cognee or use an existing Redis instance
