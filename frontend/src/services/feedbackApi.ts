/**
 * Feedback API client for submitting user feedback on book recommendations.
 * 
 * This service handles feedback submission with error handling that never breaks the UI.
 */
import axios from 'axios';
import { getAccessToken } from '../auth/auth';
import { getApiBaseUrlDebug } from '../api/client';

const envApiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_BASE_URL = envApiBaseUrl.endsWith("/api") ? envApiBaseUrl : `${envApiBaseUrl}/api`;

/**
 * Submit feedback for a book recommendation.
 * 
 * @param bookId - Book UUID string
 * @param action - One of: save_interested, read_liked, read_disliked, not_for_me
 * @returns Promise that resolves to true on success, false otherwise
 */
export async function submitFeedback(
  bookId: string,
  action: string,
): Promise<boolean> {
  try {
    const token = getAccessToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await axios.post(
      `${API_BASE_URL}/feedback`,
      {
        book_id: bookId,
        action: action,
      },
      {
        headers,
        withCredentials: true,
        timeout: 10000,
      }
    );
    return response.data?.success === true;
  } catch (error: any) {
    // Swallow all errors - never break the UI
    console.warn('Failed to submit feedback:', error);
    return false;
  }
}

