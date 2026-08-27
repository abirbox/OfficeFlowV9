import axios from 'axios';

// Always prefer relative /api when running inside a browser. Kubernetes ingress
// on every Emergent-hosted environment (preview + production) rewrites /api/*
// to the FastAPI backend on the SAME origin, so we avoid CORS entirely and the
// build works identically on preview.emergentagent.com and prod.emergent.host.
// The REACT_APP_BACKEND_URL fallback only kicks in for SSR / non-browser calls.
function resolveBaseUrl() {
  if (typeof window !== 'undefined') return '/api';
  const envUrl = process.env.REACT_APP_BACKEND_URL;
  return envUrl ? `${envUrl}/api` : '/api';
}

export const api = axios.create({
  baseURL: resolveBaseUrl(),
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

export function formatApiErrorDetail(detail) {
  if (detail == null) return 'Something went wrong. Please try again.';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === 'string' ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(' ');
  if (detail && typeof detail.msg === 'string') return detail.msg;
  return String(detail);
}

export default api;
