import { NextResponse } from 'next/server';

/**
 * Health check endpoint for Kubernetes probes
 * GET /api/health
 */
export async function GET() {
  return NextResponse.json(
    {
      status: 'ok',
      timestamp: new Date().toISOString(),
      service: 'cognee-frontend',
    },
    { status: 200 }
  );
}

// Ensure this route is always dynamic (not cached)
export const dynamic = 'force-dynamic';