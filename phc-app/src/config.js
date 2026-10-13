// Hosted API configuration for PHC Offline-First PWA
// Localhost is only permitted in local development (DEV mode).
// Production falls back to the hosted Railway deployment unless configured via VITE_API_URL / VITE_API_BASE_URL.

const envApiUrl = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL = (
  envApiUrl && envApiUrl.trim() !== ''
    ? envApiUrl.replace(/\/+$/, '')
    : (import.meta.env.DEV ? 'http://localhost:8000' : 'https://smarthealth-production.up.railway.app')
);

export const ENDPOINTS = {
  stockMovements: `${API_BASE_URL}/api/v1/stock-movements`,
  inventoryUpdate: `${API_BASE_URL}/api/v1/inventory/update`,
  facilityList: `${API_BASE_URL}/api/v1/facility/`,
  inventoryCatalogue: `${API_BASE_URL}/api/v1/inventory/`,
  facilityBeds: `${API_BASE_URL}/api/v1/facility/beds`,
  facilityAttendance: `${API_BASE_URL}/api/v1/facility/attendance`,
};
