import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

const rawBaseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
// Normalize root URL so callers using either "/api/v1/..." or "/..." never double-prefix "/api/v1"
const baseURL = rawBaseURL.replace(/\/+$/, "").replace(/\/api\/v1$/, "");

// IN-MEMORY access token storage (Do NOT store in localStorage for XSS protection)
let inMemoryAccessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

// Utility to read cookies by name
function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop()?.split(";").shift() || null;
  }
  return null;
}

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true, // Send and receive HttpOnly cookies
});

// Request Interceptor: Normalize /api/v1 prefix, attach in-memory bearer token & double-submit CSRF token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (config.url && config.url.startsWith("/") && !config.url.startsWith("/api/v1")) {
      config.url = `/api/v1${config.url}`;
    }

    // Attach in-memory access token
    if (inMemoryAccessToken && config.headers) {
      config.headers.Authorization = `Bearer ${inMemoryAccessToken}`;
    }

    // Attach CSRF token on mutating requests
    const mutatingMethods = ["post", "put", "patch", "delete"];
    if (config.method && mutatingMethods.includes(config.method.toLowerCase())) {
      const csrfToken = getCookie("cargopulse_csrf_token");
      if (csrfToken && config.headers) {
        config.headers["X-CSRF-Token"] = csrfToken;
      }
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Track ongoing refresh promise to prevent stampedes
let refreshPromise: Promise<string | null> | null = null;

// Response Interceptor: Automatic token refresh on 401
apiClient.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If 401 Unauthorized and not already retrying, attempt silent refresh
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/refresh") &&
      !originalRequest.url?.includes("/auth/login") &&
      !originalRequest.url?.includes("/auth/register")
    ) {
      originalRequest._retry = true;

      try {
        if (!refreshPromise) {
          refreshPromise = (async () => {
            try {
              const csrf = getCookie("cargopulse_csrf_token");
              const res = await axios.post(
                `${baseURL}/api/v1/auth/refresh`,
                {},
                {
                  withCredentials: true,
                  headers: csrf ? { "X-CSRF-Token": csrf } : {},
                }
              );
              const newToken = res.data?.access_token || null;
              setAccessToken(newToken);
              return newToken;
            } catch (refreshErr) {
              setAccessToken(null);
              return null;
            } finally {
              refreshPromise = null;
            }
          })();
        }

        const newAccessToken = await refreshPromise;
        if (newAccessToken) {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
          }
          const retryRes = await axios(originalRequest);
          return retryRes.data;
        }
      } catch (retryErr) {
        return Promise.reject(retryErr);
      }
    }

    const errorData = error.response?.data as any;
    const formattedError = {
      status: error.response?.status || 500,
      code: errorData?.error?.code || "ERROR",
      message: errorData?.detail || errorData?.error?.message || error.message || "An unexpected error occurred",
      details: errorData?.error?.details || [],
    };
    return Promise.reject(formattedError);
  }
);
