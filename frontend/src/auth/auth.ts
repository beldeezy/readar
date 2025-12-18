/**
 * Auth helper functions for managing access tokens.
 */

const ACCESS_TOKEN_KEY = 'readar_access_token';

/**
 * Get the stored access token from localStorage.
 */
export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

/**
 * Store an access token in localStorage.
 */
export function setAccessToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

/**
 * Clear the stored access token from localStorage.
 */
export function clearAccessToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}

