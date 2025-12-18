export interface User {
  id: string;
  email: string;
  subscription_status: "free" | "active" | "canceled";
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export type BookPreferenceStatus = "read_liked" | "read_disliked" | "interested" | "not_interested";

export type BookPreference = {
  book_id: string;
  status: BookPreferenceStatus;
};

export type RevenueRange =
  | "pre_revenue"
  | "lt_100k"
  | "100k_300k"
  | "300k_500k"
  | "500k_1m"
  | "1m_3m"
  | "3m_5m"
  | "5m_10m"
  | "10m_30m"
  | "30m_100m"
  | "100m_plus";

export interface OnboardingPayload {
  full_name: string;
  age?: number;
  occupation?: string;
  entrepreneur_status?: string;
  location?: string;
  economic_sector?: string;
  industry: string;
  business_model: string;
  business_experience?: string;
  areas_of_business?: string[];
  business_stage: "idea" | "pre-revenue" | "early-revenue" | "scaling";
  org_size?: string;
  is_student?: boolean;
  biggest_challenge: string;
  vision_6_12_months?: string;
  blockers?: string;
  current_gross_revenue?: RevenueRange;
  book_preferences?: BookPreference[];
}

export interface OnboardingProfile extends OnboardingPayload {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface Book {
  id: string;
  title: string;
  subtitle?: string;
  author_name: string;
  description: string;
  thumbnail_url?: string;
  cover_image_url?: string;
  page_count?: number;
  published_year?: number;
  categories?: string[];
  business_stage_tags?: string[];
  functional_tags?: string[];
  theme_tags?: string[];
  difficulty?: "light" | "medium" | "deep";
  // Insight fields
  promise?: string;
  best_for?: string;
  core_frameworks?: string[];
  anti_patterns?: string[];
  outcomes?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface RecommendationItem {
  book_id: string;
  title: string;
  subtitle?: string;
  author_name?: string;
  score: number;
  relevancy_score: number;
  thumbnail_url?: string;
  cover_image_url?: string;
  page_count?: number;
  published_year?: number;
  categories?: string[];
  language?: string;
  isbn_10?: string;
  isbn_13?: string;
  average_rating?: number;
  ratings_count?: number;
  theme_tags?: string[];
  functional_tags?: string[];
  business_stage_tags?: string[];
  purchase_url?: string;
  why_this_book: string; // Always present, single compelling paragraph explaining why recommended
  why_recommended?: string[]; // Deprecated: use why_this_book instead
  why_signals?: Array<{ type: string; label: string }>;
}

export interface UserBookInteraction {
  id: string;
  user_id: string;
  book_id: string;
  status: "read_liked" | "read_disliked" | "interested" | "not_interested";
  rating?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface CheckoutSessionRequest {
  price_id: string;
  success_url: string;
  cancel_url: string;
}

export interface CheckoutSessionResponse {
  checkout_url: string;
}

export interface InsightReviewItem {
  title: string;
  challenge_fit: number;
  stage_fit: number;
  promise_match: number;
  framework_match: number;
  outcome_match: number;
  total_score: number;
}

