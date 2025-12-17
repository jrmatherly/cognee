/** @type {import('next').NextConfig} */
const nextConfig = {
  // Critical for containerization - creates standalone build
  output: 'standalone',

  // Security: hide X-Powered-By header
  poweredByHeader: false,

  // Enable gzip compression
  compress: true,

  // Disable telemetry
  experimental: {
    // Improve cold start performance
    optimizePackageImports: ['@auth0/nextjs-auth0'],
  },

  // Environment variables available at build time
  env: {
    NEXT_PUBLIC_BUILD_TIME: new Date().toISOString(),
  },

  // Image optimization settings
  // Restricted to known trusted hosts for security (prevents SSRF via image optimization)
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'avatars.githubusercontent.com',
      },
      {
        protocol: 'https',
        hostname: '*.githubusercontent.com',
      },
      {
        protocol: 'https',
        hostname: 'raw.githubusercontent.com',
      },
      // Add other trusted image hosts as needed
    ],
  },

  // Proxy API calls to backend service (Kubernetes deployment)
  // BACKEND_URL is a runtime env var set in K8s deployment
  // This allows the Next.js server to proxy requests to the backend
  // while the browser only sees relative URLs (no CORS, no localhost issues)
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    const mcpUrl = process.env.MCP_URL || 'http://localhost:8001';

    return [
      // Backend API routes
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
      // Backend health check
      {
        source: '/backend/health',
        destination: `${backendUrl}/health`,
      },
      // MCP health check
      {
        source: '/mcp/health',
        destination: `${mcpUrl}/health`,
      },
      // MCP API routes (if needed)
      {
        source: '/mcp/api/:path*',
        destination: `${mcpUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
