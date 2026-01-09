import { apiClient } from "./client";
import type { User } from "./types";

// Export User type as Me for backward compatibility
export type Me = User;

export async function fetchMe(): Promise<Me> {
  return await apiClient.getCurrentUser();
}

