// Centralized API configuration
// Connects to the Railway production deployment by default, or VITE_API_URL if specified in .env
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://smarthealth-production.up.railway.app';
