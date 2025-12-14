/**
 * Onboarding form constants
 * 
 * TODO: Keep these lists in sync with our "20 macro-industries + examples" documentation
 * and any business model/area definitions we maintain.
 */

/**
 * Economic sectors
 * Used for the Sector dropdown in onboarding
 */
export const ECONOMIC_SECTORS = [
  { value: "primary", label: "Primary — Extracts raw materials (farming, fishing, mining)." },
  { value: "secondary", label: "Secondary — Processes raw materials into finished goods (manufacturing, construction)." },
  { value: "tertiary", label: "Tertiary — Provides services (retail, banking, healthcare, hospitality, entertainment)." },
  { value: "quaternary", label: "Quaternary — Focuses on knowledge and information (IT, research, education, consulting)." },
  { value: "quinary", label: "Quinary — High-level decision-making (government, research, non-profits)." },
] as const;

/**
 * Industries (alphabetized by label)
 * Used for the Industry dropdown in onboarding
 */
export const INDUSTRIES = [
  { value: "agriculture_food", label: "Agriculture & Food" },
  { value: "construction", label: "Construction" },
  { value: "education_research", label: "Education & Research" },
  { value: "energy", label: "Energy" },
  { value: "finance_banking", label: "Finance & Banking" },
  { value: "government_nonprofit", label: "Government & Nonprofits" },
  { value: "healthcare_medical", label: "Healthcare & Medical" },
  { value: "home_services", label: "Home Services" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "retail_ecommerce", label: "Retail & E-commerce" },
  { value: "technology_ict", label: "Technology (ICT)" },
  { value: "transportation_logistics", label: "Transportation & Logistics" },
] as const;

/**
 * Sector -> industries (filtered)
 * Maps each economic sector to its relevant industries
 */
export const INDUSTRIES_BY_SECTOR: Record<string, string[]> = {
  primary: ["agriculture_food"],
  secondary: ["manufacturing", "construction", "energy"],
  tertiary: ["retail_ecommerce", "finance_banking", "healthcare_medical", "home_services", "transportation_logistics"],
  quaternary: ["technology_ict", "education_research"],
  quinary: ["government_nonprofit", "education_research"],
};

/**
 * Common business models
 * Used for the Business Model multi-select in onboarding
 */
export const BUSINESS_MODELS = [
  { value: 'advertising_supported', label: 'Advertising Supported' },
  { value: 'affiliate_commission', label: 'Affiliate Commission' },
  { value: 'direct_high_ticket', label: 'Direct/High-Ticket Sales' },
  { value: 'franchise', label: 'Franchise' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'licensing_ip', label: 'Licensing/IP-Based' },
  { value: 'marketplace_platform', label: 'Marketplace/Platform' },
  { value: 'product', label: 'Product' },
  { value: 'service', label: 'Service' },
  { value: 'subscription_saas', label: 'Subscription/SaaS' },
] as const;

/**
 * Areas of business focus
 * Used for the Areas of Business multi-select in onboarding
 */
export const AREAS_OF_BUSINESS = [
  // Pinned first
  { value: 'everything', label: 'Everything — I wear all the hats' },
  // All remaining options, sorted alphabetically by label
  { value: 'customer-success-support', label: 'Customer Success / Support' },
  { value: 'finance-metrics', label: 'Finance / Metrics' },
  { value: 'marketing-growth', label: 'Marketing / Growth' },
  { value: 'operations-systems', label: 'Operations / Systems' },
  { value: 'other', label: 'Other' },
  { value: 'people-hiring', label: 'People / Hiring' },
  { value: 'product-offer', label: 'Product / Offer' },
  { value: 'sales', label: 'Sales' },
  { value: 'technology-engineering', label: 'Technology / Engineering' },
] as const;

