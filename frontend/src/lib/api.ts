import axios from 'axios';
import { clearSession, getAuthToken } from './auth';
import { buildApiUnavailableMessage, isNetworkTransportError } from './errorMessage';

const DEFAULT_API_BASE_URL = '/api';
export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL;
const AUTH_EXCLUDED_PATHS = new Set(['/auth/login', '/auth/signup']);

export const hasAuthorizationHeader = (headers: unknown): boolean => {
  if (!headers || typeof headers !== 'object') {
    return false;
  }

  return Object.keys(headers as Record<string, unknown>).some(
    (key) => key.toLowerCase() === 'authorization'
  );
};

export const shouldAttachStoredToken = (url?: string, headers?: unknown): boolean => {
  if (hasAuthorizationHeader(headers)) {
    return false;
  }

  if (!url) {
    return true;
  }

  const normalizedUrl = url.startsWith('http') ? new URL(url).pathname : url;
  return !AUTH_EXCLUDED_PATHS.has(normalizedUrl);
};

export const normalizeApiTransportError = (error: unknown, baseUrl = apiBaseUrl): unknown => {
  if (isNetworkTransportError(error) && error instanceof Error) {
    error.message = buildApiUnavailableMessage(baseUrl);
  }
  return error;
};

const api = axios.create({
  baseURL: apiBaseUrl,
});

api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token && shouldAttachStoredToken(config.url, config.headers)) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    normalizeApiTransportError(error, api.defaults.baseURL);
    if (error?.response?.status === 401) {
      clearSession();
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.replace('/login');
      }
    }
    return Promise.reject(error);
  }
);

export default api;
