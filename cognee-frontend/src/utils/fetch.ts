import handleServerErrors from "./handleServerErrors";
import isCloudEnvironment from "./isCloudEnvironment";

let numberOfRetries = 0;

const isAuth0Enabled = process.env.USE_AUTH0_AUTHORIZATION?.toLowerCase() === "true";

// API URLs - use relative paths for Kubernetes deployment (proxied via Next.js rewrites)
// In K8s, BACKEND_URL and MCP_URL env vars are set on the server side
// The browser makes relative requests that Next.js proxies to the backend
// For local development, these still work because rewrites fall back to localhost
const backendApiUrl = "";  // Relative URL - proxied via Next.js rewrites in next.config.mjs

const cloudApiUrl = process.env.NEXT_PUBLIC_CLOUD_API_URL || "";

let apiKey: string | null = process.env.NEXT_PUBLIC_COGWIT_API_KEY || null;
let accessToken: string | null = null;

export default async function fetch(url: string, options: RequestInit = {}, useCloud = false): Promise<Response> {
  function retry(lastError: Response) {
    if (!isAuth0Enabled) {
      return Promise.reject(lastError);
    }

    if (numberOfRetries >= 1) {
      return Promise.reject(lastError);
    }

    numberOfRetries += 1;

    return global.fetch("/auth/token")
      .then(() => {
        return fetch(url, options);
      });
  }

  const authHeaders = useCloud && (!isCloudEnvironment() || !accessToken) ? {
    "X-Api-Key": apiKey,
  } : {
    "Authorization": `Bearer ${accessToken}`,
  }

  return global.fetch(
    (useCloud ? cloudApiUrl : backendApiUrl) + "/api" + (useCloud ? url.replace("/v1", "") : url),
    {
      ...options,
      headers: {
        ...options.headers,
        ...authHeaders,
      } as HeadersInit,
      credentials: "include",
    },
  )
    .then((response) => handleServerErrors(response, retry, useCloud))
    .catch((error) => {
      // Handle network errors more gracefully
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        return Promise.reject(
          new Error("Backend server is not responding. Please check if the server is running.")
        );
      }
      
      if (error.detail === undefined) {
        return Promise.reject(
          new Error("No connection to the server.")
        );
      }

      return Promise.reject(error);
    })
    .finally(() => {
      numberOfRetries = 0;
    });
}

fetch.checkHealth = async () => {
  const maxRetries = 5;
  const retryDelay = 1000; // 1 second

  for (let i = 0; i < maxRetries; i++) {
    try {
      // Use the proxied health endpoint (routed via Next.js rewrites)
      const response = await global.fetch("/backend/health");
      if (response.ok) {
        return response;
      }
    } catch (error) {
      // If this is the last retry, throw the error
      if (i === maxRetries - 1) {
        throw error;
      }
      // Wait before retrying
      await new Promise(resolve => setTimeout(resolve, retryDelay));
    }
  }

  throw new Error("Backend server is not responding after multiple attempts");
};

fetch.checkMCPHealth = () => {
  // Use the proxied MCP health endpoint (routed via Next.js rewrites)
  return global.fetch("/mcp/health");
};

fetch.setApiKey = (newApiKey: string) => {
  apiKey = newApiKey;
};

fetch.setAccessToken = (newAccessToken: string) => {
  accessToken = newAccessToken;
};
