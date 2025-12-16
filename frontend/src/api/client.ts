import axios, { AxiosInstance } from 'axios';
import type {
  User,
  Token,
  OnboardingPayload,
  OnboardingProfile,
  Book,
  RecommendationItem,
  UserBookInteraction,
  BookPreferenceStatus,
  CheckoutSessionRequest,
  CheckoutSessionResponse,
} from './types';
import { AUTH_DISABLED, TEST_USER_ID } from '../config/auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include auth token
    this.client.interceptors.request.use(
      (config) => {
        // TEMP: Skip token when auth is disabled
        if (AUTH_DISABLED) {
          // Optionally add test user ID as header if backend needs it
          // config.headers['X-Test-User-Id'] = TEST_USER_ID;
          return config;
        }

        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Add response interceptor to handle errors
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // TEMP: Skip 401 redirect when auth is disabled
        if (AUTH_DISABLED) {
          return Promise.reject(error);
        }

        if (error.response?.status === 401) {
          // Clear token
          localStorage.removeItem('access_token');
          // Only redirect if not already on auth page
          if (window.location.pathname !== '/auth') {
            window.location.href = '/auth';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth methods
  async signup(email: string, password: string): Promise<{ access_token: string }> {
    // TEMP: Skip real signup when auth is disabled
    if (AUTH_DISABLED) {
      return { access_token: 'test-token' };
    }

    const response = await this.client.post<Token>('/auth/signup', { email, password });
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
    }
    return { access_token: response.data.access_token };
  }

  async login(email: string, password: string): Promise<{ access_token: string }> {
    // TEMP: Skip real login when auth is disabled
    if (AUTH_DISABLED) {
      return { access_token: 'test-token' };
    }

    const response = await this.client.post<Token>('/auth/login', { email, password });
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
    }
    return { access_token: response.data.access_token };
  }

  async getCurrentUser(): Promise<User> {
    // TEMP: Return test user when auth is disabled
    if (AUTH_DISABLED) {
      return {
        id: TEST_USER_ID,
        email: 'test@readar.com',
        subscription_status: 'free',
        created_at: new Date().toISOString(),
      };
    }

    const response = await this.client.get<User>('/auth/me');
    return response.data;
  }

  logout(): void {
    localStorage.removeItem('access_token');
  }

  // Onboarding methods
  async saveOnboarding(payload: OnboardingPayload, userId: string): Promise<OnboardingProfile> {
    try {
      const response = await this.client.post<OnboardingProfile>('/onboarding', payload, {
        params: { user_id: userId },
      });
      return response.data;
    } catch (error: any) {
      // Extract backend error message if available
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      // Fall back to generic error message
      throw new Error(error.message || 'Failed to save onboarding');
    }
  }

  async getOnboarding(userId: string): Promise<OnboardingProfile> {
    const response = await this.client.get<OnboardingProfile>('/onboarding', {
      params: { user_id: userId },
    });
    return response.data;
  }

  // Book methods
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

  // Recommendation methods
  // Note: getRecommendations is deprecated. Use fetchRecommendations instead.
  async getRecommendations(maxResults?: number): Promise<RecommendationItem[]> {
    const response = await this.client.post<RecommendationItem[]>('/recommendations', {
      max_results: maxResults,
    });
    return response.data;
  }

  // User-Book interaction methods
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

  // Billing methods
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

  // Reading history methods
  async uploadReadingHistoryCsv(params: {
    userId: string;
    file: File;
  }): Promise<{ imported_count: number; skipped_count: number }> {
    const formData = new FormData();
    formData.append('file', params.file);

    try {
      const response = await this.client.post<{ imported_count: number; skipped_count: number }>(
        `/reading-history/upload-csv?user_id=${params.userId}`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return response.data;
    } catch (error: any) {
      // Extract backend error message if available
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      // Fall back to generic error message
      throw new Error(error.message || 'Failed to upload reading history');
    }
  }
}

export const apiClient = new ApiClient();

// Standalone fetch-based recommendation helper
// This is the preferred way to fetch recommendations, as it shows real error messages
export async function fetchRecommendations(params: {
  userId: string;
  limit?: number;
}): Promise<RecommendationItem[]> {
  const { userId, limit = 10 } = params;
  const url = `${API_BASE_URL}/recommendations?user_id=${userId}&limit=${limit}`;

  console.log("fetchRecommendations → url:", url, "userId:", userId);

  try {
    const res = await fetch(url, {
      method: "GET",
    });

    if (!res.ok) {
      let message = `Failed to fetch recommendations (status ${res.status}).`;
      try {
        const data = await res.json();
        if (data && typeof data.detail === "string") {
          message = data.detail;
        }
      } catch {
        // ignore JSON parse errors
      }
      throw new Error(message);
    }

    return res.json();
  } catch (err: any) {
    console.error("Network error fetching recommendations", err);
    throw new Error(err?.message || "Failed to fetch recommendations");
  }
}

