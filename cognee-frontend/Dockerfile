# ============================================
# Cognee Frontend - Production Dockerfile
# Multi-stage build with Next.js standalone output
# ============================================

# Stage 1: Dependencies
# ============================================
FROM node:22-alpine AS deps
WORKDIR /app

# Install ALL dependencies (including devDeps needed for build)
COPY package.json package-lock.json ./
RUN npm ci && \
    npm cache clean --force

# ============================================
# Stage 2: Builder
# ============================================
FROM node:22-alpine AS builder
WORKDIR /app

# Copy dependencies
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./

# Copy source files
COPY src ./src
COPY public ./public
COPY types ./types
COPY next.config.mjs postcss.config.mjs tsconfig.json ./

# Build Next.js in standalone mode
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN npm run build

# ============================================
# Stage 3: Runtime
# ============================================
FROM node:22-alpine AS runner
WORKDIR /app

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create non-root user for K8s security
# Using UID/GID 10001 to avoid conflicts with existing system users
RUN addgroup --system --gid 10001 nodejs && \
    adduser --system --uid 10001 nextjs --ingroup nodejs

# Set environment
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Copy built application (standalone output)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Switch to non-root user
USER nextjs

EXPOSE 3000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})" || exit 1

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "server.js"]