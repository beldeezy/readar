import axios, { AxiosInstance } from 'axios';
import type {
  User,
  Token,
  OnboardingPayload,
  OnboardingProfile,
  Book,
  RecommendationItem,
  RecommendationsResponse,
  UserBookInteraction,
  BookPreferenceStatus,
  CheckoutSessionRequest,
  CheckoutSessionResponse,
} from './types';
import { getAccessToken, clearAccessToken } from '../auth/auth';

// Require VITE_API_BASE_URL and make it deterministic
const envApiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_BASE_URL = envApiBaseUrl.endsWith("/api") ? envApiBaseUrl : `${envApiBaseUrl}/api`;
console.log("[API] baseURL =", API_BASE_URL);

// Debug helper for error messages
export function getApiBaseUrlDebug() {
  return {
    VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
    API_BASE_URL,
  };
}

// Helper to get auth header from stored token
function getAuthHeader(): Record<string, string> | null {
  const token = getAccessToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return null;
}

// Prevent redirect storms on repeated 401s
let redirectingToLogin = false;

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true,
      // Optional: avoid hanging forever
      timeout: 15000,
    });

    // Add request interceptor to include auth token
    this.client.interceptors.request.use(
      (config) => {
        const authHeader = getAuthHeader();
        if (authHeader) {
          config.headers.Authorization = authHeader.Authorization;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Add response interceptor to handle errors
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // Axios timeout (backend reachable but not responding fast enough OR connection never completes)
        if (error.code === 'ECONNABORTED' || String(error.message || '').includes('timeout')) {
          const debug = getApiBaseUrlDebug();
          return Promise.reject(
            new Error(
              `Backend request timed out (15s). This usually means the backend is down, stuck, or waiting on the database. API_BASE_URL=${debug.API_BASE_URL}`
            )
          );
        }

        // Network-layer errors (no response). This includes true network down
        // and also browser-blocked responses (CORS / aborted / etc.)
        if (
          !error.response &&
          (error.message?.includes('Network Error') ||
            error.code === 'ERR_NETWORK' ||
            error.code === 'ECONNREFUSED')
        ) {
          const debug = getApiBaseUrlDebug();
          return Promise.reject(
            new Error(
              `Backend is unreachable. Confirm FastAPI is running and VITE_API_BASE_URL points to it (API_BASE_URL=${debug.API_BASE_URL}).`
            )
          );
        }

        // If backend answered with 401, clear token + redirect once
        if (error.response?.status === 401) {
          clearAccessToken();

          const path = window.location.pathname;
          const isAuthPage = path === '/login' || path === '/auth' || path === '/auth/callback';

          if (!isAuthPage && !redirectingToLogin) {
            redirectingToLogin = true;
            window.location.href = '/login';
          }
        }

        // Handle 409 email conflict errors
        if (error.response?.status === 409) {
          const detail = error.response?.data?.detail;
          const errorCode = typeof detail === 'string' ? detail : 
                           (typeof detail === 'object' && detail?.code) ? detail.code : null;
          
          if (errorCode === 'email_already_linked_to_different_account' || 
              errorCode === 'email_mismatch') {
            // Clear onboarding draft state and localStorage
            localStorage.removeItem('pending_onboarding');
            localStorage.removeItem('readar_preview_recs');
            
            // Clear auth token and redirect to login
            clearAccessToken();
            
            // Redirect to login with helpful message
            const path = window.location.pathname;
            const isAuthPage = path === '/login' || path === '/auth' || path === '/auth/callback';
            
            if (!isAuthPage && !redirectingToLogin) {
              redirectingToLogin = true;
              // Store error message in sessionStorage to show on login page
              sessionStorage.setItem('auth_error', 
                'Your email is linked to a different account. Please log in with the correct account.');
              window.location.href = '/login';
            }
          }
        }

        return Promise.reject(error);
      }
    );
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<User>('/me');
    return response.data;
  }

  async saveOnboarding(payload: OnboardingPayload): Promise<OnboardingProfile> {
    // Debug logging (only in dev or when VITE_DEBUG=true)
    const DEBUG = import.meta.env.DEV || import.meta.env.VITE_DEBUG === 'true';
    const url = `${API_BASE_URL}/onboarding`;
    const hasAuth = !!getAuthHeader();
    
    if (DEBUG) {
      console.log('[DEBUG saveOnboarding]', {
        method: 'POST',
        url,
        payloadKeys: Object.keys(payload),
        hasAuthorization: hasAuth,
      });
    }

    const attempt = async () => {
      const response = await this.client.post<OnboardingProfile>("/onboarding", payload);
      
      if (DEBUG) {
        console.log('[DEBUG saveOnboarding response]', {
          status: response.status,
          statusText: response.statusText,
          body: JSON.stringify(response.data),
        });
      }
      
      return response.data;
    };

    try {
      return await attempt();
    } catch (error: any) {
      if (DEBUG) {
        console.log('[DEBUG saveOnboarding error]', {
          status: error?.response?.status,
          statusText: error?.response?.statusText,
          body: error?.response?.data ? JSON.stringify(error.response.data) : 'no body',
          message: error?.message,
        });
      }
      const status = error?.response?.status as number | undefined;

      // Handle 409 email conflict - don't retry, let interceptor handle logout
      if (status === 409) {
        const detail = error.response?.data?.detail;
        const errorCode = typeof detail === 'string' ? detail : 
                         (typeof detail === 'object' && detail?.code) ? detail.code : null;
        
        if (errorCode === 'email_already_linked_to_different_account' || 
            errorCode === 'email_mismatch') {
          // Let the interceptor handle the logout/redirect
          throw error;
        }
      }

      // Do NOT retry auth/permission/validation-style failures
      if (status === 401 || status === 403 || status === 422) {
        if (error.response?.data?.detail) throw new Error(error.response.data.detail);
        throw new Error(error.message || "Failed to save onboarding");
      }

      // Retry once for transient/server/network issues
      const isNetwork = !error?.response;
      const isTransient = status === 500 || status === 502 || status === 503 || status === 504;

      if (isNetwork || isTransient) {
        await new Promise((r) => setTimeout(r, 600)); // short backoff
        try {
          return await attempt();
        } catch (error2: any) {
          if (error2.response?.data?.detail) throw new Error(error2.response.data.detail);
          throw new Error(error2.message || "Failed to save onboarding");
        }
      }

      if (error.response?.data?.detail) throw new Error(error.response.data.detail);
      throw new Error(error.message || "Failed to save onboarding");
    }
  }

  async getOnboarding(): Promise<OnboardingProfile> {
    // Debug logging (only in dev or when VITE_DEBUG=true)
    const DEBUG = import.meta.env.DEV || import.meta.env.VITE_DEBUG === 'true';
    const url = `${API_BASE_URL}/onboarding`;
    const hasAuth = !!getAuthHeader();
    
    if (DEBUG) {
      console.log('[DEBUG getOnboarding]', {
        method: 'GET',
        url,
        hasAuthorization: hasAuth,
      });
    }

    try {
      const response = await this.client.get<OnboardingProfile>('/onboarding');
      
      if (DEBUG) {
        console.log('[DEBUG getOnboarding response]', {
          status: response.status,
          statusText: response.statusText,
          body: JSON.stringify(response.data),
        });
      }
      
      return response.data;
    } catch (error: any) {
      // Enhanced error logging (only when VITE_DEBUG=true in production, or in dev)
      const shouldLog = DEBUG || import.meta.env.VITE_DEBUG === 'true';
      if (shouldLog) {
        console.error('[DEBUG getOnboarding error]', {
          url,
          method: 'GET',
          status: error?.response?.status,
          statusText: error?.response?.statusText,
          headers: error?.response?.headers ? {
            'content-type': error.response.headers['content-type'],
          } : 'no headers',
          responseData: error?.response?.data ? JSON.stringify(error.response.data) : 'no response data',
          responseText: error?.response?.data ? String(error.response.data) : 'no response text',
          message: error?.message,
          stack: error?.stack,
        });
      }
      throw error;
    }
  }

  async getBooks(params?: {
    q?: string;
    sort?: string;
    order?: string;
    year_min?: number;
    year_max?: number;
    has_cover?: boolean;
    category?: string;
    stage?: string;
    limit?: number;
    offset?: number;
  }): Promise<Book[]> {
    const response = await this.client.get<Book[]>('/books', { params });
    return response.data;
  }

  async getBook(bookId: string): Promise<Book> {
    const response = await this.client.get<Book>(`/books/${bookId}`);
    return response.data;
  }

  async getRecommendations(maxResults?: number): Promise<RecommendationsResponse> {
    // Debug logging (only when VITE_DEBUG=true in production, or in dev)
    const DEBUG = import.meta.env.DEV || import.meta.env.VITE_DEBUG === 'true';
    const url = `${API_BASE_URL}/recommendations`;
    const hasAuth = !!getAuthHeader();
    
    if (DEBUG) {
      console.log('[DEBUG getRecommendations]', {
        method: 'POST',
        url,
        hasAuthorization: hasAuth,
        maxResults,
      });
    }

    try {
      const response = await this.client.post<RecommendationsResponse>('/recommendations', {
        max_results: maxResults,
      });
      
      if (DEBUG) {
        console.log('[DEBUG getRecommendations response]', {
          status: response.status,
          statusText: response.statusText,
        });
      }
      
      return response.data;
    } catch (error: any) {
      if (DEBUG) {
        console.error('[DEBUG getRecommendations error]', {
          url,
          method: 'POST',
          status: error?.response?.status,
          statusText: error?.response?.statusText,
          headers: error?.response?.headers ? {
            'content-type': error.response.headers['content-type'],
          } : 'no headers',
          responseData: error?.response?.data ? JSON.stringify(error.response.data) : 'no response data',
          responseText: error?.response?.data ? String(error.response.data) : 'no response text',
          message: error?.message,
        });
      }
      throw error;
    }
  }

  async getPreviewRecommendations(payload: OnboardingPayload): Promise<RecommendationItem[]> {
    // Debug logging (only when VITE_DEBUG=true in production, or in dev)
    const DEBUG = import.meta.env.DEV || import.meta.env.VITE_DEBUG === 'true';
    const url = `${API_BASE_URL}/recommendations/preview`;
    const hasAuth = !!getAuthHeader();
    
    if (DEBUG) {
      console.log('[DEBUG getPreviewRecommendations]', {
        method: 'POST',
        url,
        hasAuthorization: hasAuth,
      });
    }

    try {
      const response = await this.client.post<RecommendationItem[]>('/recommendations/preview', payload);
      return response.data;
    } catch (error: any) {
      if (DEBUG) {
        console.error('[DEBUG getPreviewRecommendations error]', {
          url,
          method: 'POST',
          status: error?.response?.status,
          statusText: error?.response?.statusText,
          headers: error?.response?.headers ? {
            'content-type': error.response.headers['content-type'],
          } : 'no headers',
          responseData: error?.response?.data ? JSON.stringify(error.response.data) : 'no response data',
          responseText: error?.response?.data ? String(error.response.data) : 'no response text',
          message: error?.message,
        });
      }
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error(error.message || 'Failed to get preview recommendations');
    }
  }

  async updateUserBook(
    bookId: string,
    status: BookPreferenceStatus,
    rating?: number,
    notes?: string
  ): Promise<UserBookInteraction> {
    const response = await this.client.post<UserBookInteraction>('/user-books', {
      book_id: bookId,
      status,
      rating,
      notes,
    });
    return response.data;
  }

  async getUserBooks(): Promise<UserBookInteraction[]> {
    const response = await this.client.get<UserBookInteraction[]>('/user-books');
    return response.data;
  }

  async createCheckoutSession(
    priceId: string,
    successUrl: string,
    cancelUrl: string
  ): Promise<CheckoutSessionResponse> {
    const response = await this.client.post<CheckoutSessionResponse>(
      '/billing/create-checkout-session',
      {
        price_id: priceId,
        success_url: successUrl,
        cancel_url: cancelUrl,
      }
    );
    return response.data;
  }

  async uploadReadingHistoryCsv(params: {
    file: File;
  }): Promise<{ imported_count: number; skipped_count: number }> {
    const formData = new FormData();
    formData.append('file', params.file);

    try {
      const response = await this.client.post<{ imported_count: number; skipped_count: number }>(
        `/reading-history/upload-csv`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return response.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error(error.message || 'Failed to upload reading history');
    }
  }

  async setBookStatus(payload: {
    book_id: string;
    status: string;
    request_id?: string;
    position?: number;
    source?: string;
  }): Promise<{ ok: boolean }> {
    // Map frontend "not_interested" to backend "not_for_me"
    const backendStatus = payload.status === 'not_interested' ? 'not_for_me' : payload.status;
    
    const response = await this.client.post<{ ok: boolean }>('/book-status', {
      book_id: payload.book_id,
      status: backendStatus,
      request_id: payload.request_id,
      position: payload.position,
      source: payload.source || 'recommendations',
    });
    return response.data;
  }

  async getBookStatusList(status?: string): Promise<Array<{
    book_id: string;
    status: string;
    updated_at: string;
    title?: string;
    author_name?: string;
  }>> {
    const params = status ? { status } : {};
    const response = await this.client.get<
      Array<{
        book_id: string;
        status: string;
        updated_at: string;
        title?: string;
        author_name?: string;
      }>
    >('/profile/book-status', { params });
    return response.data;
  }

  async getAdminRecommendationsDebug(limit: number, debug: boolean): Promise<RecommendationsResponse> {
    const response = await this.client.get<RecommendationsResponse>('/recommendations', {
      params: {
        limit,
        debug: debug ? 'true' : 'false',
      },
    });
    return response.data;
  }
}

export const apiClient = new ApiClient();

export async function fetchRecommendations(params: {
  limit?: number;
}): Promise<RecommendationsResponse> {
  const { limit = 5 } = params;
  const safeLimit = Math.min(Math.max(limit, 1), 5);
  const url = `${API_BASE_URL}/recommendations?limit=${safeLimit}`;

  try {
    const authHeader = getAuthHeader();
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (authHeader) {
      headers.Authorization = authHeader.Authorization;
    }

    const res = await fetch(url, {
      method: "GET",
      headers,
      credentials: 'include',
    });

    if (!res.ok) {
      let message = `Failed to fetch recommendations (status ${res.status}).`;
      try {
        const data = await res.json();
        if (data && typeof data.detail === "string") {
          message = data.detail;
        }
      } catch {
        // ignore
      }
      throw new Error(message);
    }

    return res.json();
  } catch (err: any) {
    console.error("Network error fetching recommendations", err);

    const errorMessage = err?.message || "";
    if ((errorMessage.includes("Failed to fetch") || err instanceof TypeError) && !(err as any).response) {
      const debug = getApiBaseUrlDebug();
      throw new Error(
        `Backend is unreachable. Confirm FastAPI is running and VITE_API_BASE_URL points to it (API_BASE_URL=${debug.API_BASE_URL}).`
      );
    }

    throw new Error(err?.message || "Failed to fetch recommendations");
  }
}

/**
 * Send a recommendation click event to the backend (best-effort, non-blocking).
 * Uses sendBeacon if available, otherwise fetch with keepalive.
 */
export async function logRecommendationClick(params: {
  book_id: string;
  request_id: string;
  position: number;
  session_id?: string;
}): Promise<void> {
  const url = `${API_BASE_URL}/events/recommendation-click`;
  const payload = {
    book_id: params.book_id,
    request_id: params.request_id,
    position: params.position,
    session_id: params.session_id,
  };

  try {
    // Prefer sendBeacon for reliability (works even if page is unloading)
    if (navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      navigator.sendBeacon(url, blob);
      return;
    }

    // Fallback to fetch with keepalive
    const authHeader = getAuthHeader();
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (authHeader) {
      headers.Authorization = authHeader.Authorization;
    }

    await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      keepalive: true,
      credentials: 'include',
    });
  } catch (err) {
    // Silently fail - we don't want to break the user experience
    console.warn('Failed to log recommendation click:', err);
  }
}
