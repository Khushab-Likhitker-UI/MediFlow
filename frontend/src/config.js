// Centralized API configuration
// Uses VITE_API_URL if configured, otherwise defaults to local backend in development
export const API_BASE_URL = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8000' : 'https://smarthealth-production.up.railway.app')
);
