/**
 * Chat Onboarding Configuration — Consultative Sales Flow
 *
 * 6-stage consultative flow designed to deeply understand the user's
 * situation before making recommendations. Stages:
 *   1. Connection    — set expectations
 *   2. Situation     — understand context
 *   3. Problem       — surface pain points
 *   4. Solution      — gauge awareness
 *   5. Consequences  — create urgency
 *   6. Qualifying    — confirm motivation
 *   + Fallback       — structured rec engine signals if not inferred
 */

// Question types
export type QuestionType =
  | 'select'
  | 'multi-select'
  | 'text'
  | 'textarea'
  | 'book-calibration'
  | 'file-upload';

export type OnboardingStage =
  | 'connection'
  | 'situation'
  | 'problem'
  | 'solution'
  | 'consequences'
  | 'qualifying'
  | 'fallback';

export interface ChatQuestion {
  id: string;
  question: string;
  type: QuestionType;
  required: boolean;
  stage: OnboardingStage;
  options?: { value: string; label: string }[];
  condition?: (answers: Record<string, any>) => boolean;
  order: number;
  helpText?: string;
  /** If true, show a stage label banner above this question */
  stageLabel?: string;
}

/**
 * All onboarding questions in order
 */
export const CHAT_QUESTIONS: ChatQuestion[] = [

  // ── SITUATION STAGE ────────────────────────────────────────────────────────
  {
    id: 'business_name',
    question: 'What business do you have?',
    type: 'text',
    required: true,
    stage: 'situation',
    stageLabel: 'Your Situation',
    order: 1,
    helpText: 'Give us a quick description — e.g. "a digital marketing agency" or "a SaaS for restaurants"',
  },
  {
    id: 'business_age',
    question: 'How long have you owned the business?',
    type: 'text',
    required: false,
    stage: 'situation',
    order: 2,
    helpText: 'e.g. "6 months", "3 years", "just started"',
  },
  {
    id: 'business_origin',
    question: 'What caused you to choose that business?',
    type: 'textarea',
    required: false,
    stage: 'situation',
    order: 3,
  },

  // ── PROBLEM AWARENESS STAGE ────────────────────────────────────────────────
  {
    id: 'primary_problems',
    question: 'What are your biggest problems right now?',
    type: 'textarea',
    required: true,
    stage: 'problem',
    stageLabel: 'Your Problems',
    order: 4,
  },
  {
    id: 'root_cause',
    question: "What do you think is the root cause of those problems?",
    type: 'textarea',
    required: false,
    stage: 'problem',
    order: 5,
  },
  {
    id: 'personal_impact',
    question: 'How are those problems affecting you personally?',
    type: 'textarea',
    required: false,
    stage: 'problem',
    order: 6,
  },
  {
    id: 'secondary_problems',
    question: 'Besides those, what other challenges are you experiencing?',
    type: 'textarea',
    required: false,
    stage: 'problem',
    order: 7,
  },
  {
    id: 'why_book_not_random',
    question: 'Why do you want to find the right book, rather than just getting random recommendations from friends or social media?',
    type: 'textarea',
    required: false,
    stage: 'problem',
    order: 8,
  },

  // ── SOLUTION AWARENESS STAGE ───────────────────────────────────────────────
  {
    id: 'solutions_tried',
    question: 'What have you already tried to solve these problems?',
    type: 'textarea',
    required: false,
    stage: 'solution',
    stageLabel: 'What You\'ve Tried',
    order: 9,
  },
  {
    id: 'book_preferences',
    question: "Here are some popular business books. Tell me which ones you've read or are interested in!",
    type: 'book-calibration',
    required: true,
    stage: 'solution',
    helpText: 'Rate at least 4 books to continue',
    order: 10,
  },
  {
    id: 'reading_history_csv',
    question: "Do you use Goodreads? You can upload your reading history so I can give you better recommendations.",
    type: 'file-upload',
    required: false,
    stage: 'solution',
    order: 11,
  },
  {
    id: 'ideal_book_description',
    question: 'What would your ideal book include?',
    type: 'textarea',
    required: false,
    stage: 'solution',
    order: 12,
    helpText: 'e.g. "practical frameworks I can apply immediately", "case studies from similar businesses"',
  },
  {
    id: 'future_vision',
    question: 'How would things be different if your problems were solved?',
    type: 'textarea',
    required: false,
    stage: 'solution',
    order: 13,
  },

  // ── CONSEQUENCES STAGE ────────────────────────────────────────────────────
  {
    id: 'consequence_if_unsolved',
    question: 'What could happen to your business if you don\'t find the right information?',
    type: 'textarea',
    required: false,
    stage: 'consequences',
    stageLabel: 'The Stakes',
    order: 14,
  },

  // ── QUALIFYING STAGE ──────────────────────────────────────────────────────
  {
    id: 'why_now',
    question: 'Why is finding the right book important to you right now specifically?',
    type: 'textarea',
    required: false,
    stage: 'qualifying',
    stageLabel: 'Why Now',
    order: 15,
  },

  // ── FALLBACK STRUCTURED SIGNALS (shown only if not already inferred) ───────
  {
    id: 'business_stage',
    question: "Just to make sure I match you with the right books — where would you say your business is right now?",
    type: 'select',
    required: true,
    stage: 'fallback',
    stageLabel: 'One last thing...',
    condition: (answers) => !answers.business_stage,
    options: [
      { value: 'idea', label: 'Just an idea (planning stage)' },
      { value: 'pre-revenue', label: 'Started but not making money yet' },
      { value: 'early-revenue', label: 'Making some money' },
      { value: 'scaling', label: 'Growing and scaling up' },
    ],
    order: 16,
  },
  {
    id: 'business_model',
    question: 'How does your business make money? (Pick all that apply)',
    type: 'multi-select',
    required: true,
    stage: 'fallback',
    condition: (answers) => !answers.business_model,
    options: [
      { value: 'product', label: 'Selling products' },
      { value: 'service', label: 'Providing services' },
      { value: 'subscription_saas', label: 'Monthly subscriptions' },
      { value: 'advertising_supported', label: 'Showing ads' },
      { value: 'marketplace_platform', label: 'Connecting buyers and sellers' },
      { value: 'affiliate_commission', label: 'Getting paid when people buy through my links' },
      { value: 'direct_high_ticket', label: 'Selling expensive items or courses' },
      { value: 'licensing_ip', label: 'Licensing my ideas or brand' },
      { value: 'franchise', label: 'Running a franchise' },
      { value: 'hybrid', label: 'A mix of different ways' },
    ],
    order: 17,
  },
  {
    id: 'industry',
    question: 'Which industry best describes your business?',
    type: 'select',
    required: false,
    stage: 'fallback',
    condition: (answers) => !answers.industry,
    options: [], // Dynamically populated based on economic_sector if known, else full list
    order: 18,
  },
];

/**
 * Industries organized by economic sector (used for dynamic industry filtering)
 */
export const INDUSTRIES_BY_SECTOR: Record<string, { value: string; label: string }[]> = {
  primary: [
    { value: 'agriculture_food', label: 'Agriculture & Food' },
    { value: 'energy', label: 'Energy & Natural Resources' },
  ],
  secondary: [
    { value: 'manufacturing', label: 'Manufacturing & Production' },
    { value: 'construction', label: 'Construction & Real Estate' },
  ],
  tertiary: [
    { value: 'retail_ecommerce', label: 'Retail & E-commerce' },
    { value: 'hospitality', label: 'Hospitality & Tourism' },
    { value: 'transportation_logistics', label: 'Transportation & Logistics' },
  ],
  quaternary: [
    { value: 'technology_ict', label: 'Technology & Software' },
    { value: 'finance_banking', label: 'Finance & Insurance' },
    { value: 'consulting', label: 'Consulting & Professional Services' },
  ],
  quinary: [
    { value: 'healthcare_medical', label: 'Healthcare & Wellness' },
    { value: 'education_research', label: 'Education & Training' },
    { value: 'government_nonprofit', label: 'Government & Nonprofit' },
  ],
};

/** All industries flat list (used when sector is unknown) */
export const ALL_INDUSTRIES = Object.values(INDUSTRIES_BY_SECTOR).flat();

/**
 * Calibration books for book preference step
 */
export const CALIBRATION_BOOKS = [
  {
    id: 'the-lean-startup',
    title: 'The Lean Startup',
    author: 'Eric Ries',
    externalId: 'the-lean-startup',
    description: 'Learn how to build a successful startup using continuous innovation and validated learning.',
  },
  {
    id: 'zero-to-one',
    title: 'Zero to One',
    author: 'Peter Thiel',
    externalId: 'zero-to-one',
    description: 'Discover how to create unique businesses that go from nothing to something completely new.',
  },
  {
    id: 'the-e-myth-revisited',
    title: 'The E-Myth Revisited',
    author: 'Michael Gerber',
    externalId: 'the-e-myth-revisited',
    description: 'Understand why most small businesses fail and how to build systems that work without you.',
  },
  {
    id: 'the-psychology-of-money',
    title: 'The Psychology of Money',
    author: 'Morgan Housel',
    externalId: 'the-psychology-of-money',
    description: 'Explore how people think about money and make better financial decisions for your business.',
  },
  {
    id: 'deep-work',
    title: 'Deep Work',
    author: 'Cal Newport',
    externalId: 'deep-work',
    description: 'Master the ability to focus on difficult tasks and get more done in less time.',
  },
  {
    id: 'atomic-habits',
    title: 'Atomic Habits',
    author: 'James Clear',
    externalId: 'atomic-habits',
    description: 'Build small habits that compound into remarkable results for yourself and your business.',
  },
];

/**
 * Book status options
 */
export const BOOK_STATUS_OPTIONS = [
  { value: 'read_liked', label: "👍 Read it and loved it", emoji: '👍' },
  { value: 'read_disliked', label: "👎 Read it but didn't like it", emoji: '👎' },
  { value: 'interested', label: '📚 Want to read it', emoji: '📚' },
  { value: 'not_interested', label: '🚫 Not interested', emoji: '🚫' },
];

/**
 * Connection stage intro messages (shown before questions start)
 */
export const CONNECTION_MESSAGES = [
  "Before I make any recommendations, I want to understand your situation.",
  "The more honest detail you share, the better I can match you with the right book.",
  "Let's start with the basics about your business.",
];

/**
 * Calculate onboarding progress based on answered questions
 */
export function calculateProgress(answers: Record<string, any>): number {
  // Count only non-fallback questions for progress (fallback is a bonus step)
  const mainQuestions = CHAT_QUESTIONS.filter(q => q.stage !== 'fallback');
  let answeredCount = 0;

  for (const question of mainQuestions) {
    if (question.condition && !question.condition(answers)) continue;

    const answer = answers[question.id];

    if (question.id === 'book_preferences') {
      const bookCount = answer ? Object.keys(answer).length : 0;
      if (bookCount >= 4) answeredCount++;
    } else if (Array.isArray(answer)) {
      if (answer.length > 0) answeredCount++;
    } else if (answer !== undefined && answer !== null && answer !== '') {
      answeredCount++;
    }
  }

  return Math.round((answeredCount / mainQuestions.length) * 100);
}

/**
 * Get the next unanswered question
 */
export function getNextQuestion(answers: Record<string, any>): ChatQuestion | null {
  for (const question of CHAT_QUESTIONS) {
    if (question.condition && !question.condition(answers)) continue;

    const answer = answers[question.id];

    if (question.id === 'book_preferences') {
      const bookCount = answer ? Object.keys(answer).length : 0;
      if (bookCount < 4) return question;
    } else if (Array.isArray(answer)) {
      if (answer.length === 0) return question;
    } else if (answer === undefined || answer === null || answer === '') {
      return question;
    }
  }

  return null; // All questions answered
}

/**
 * Validate if all required questions are answered
 */
export function validateOnboardingComplete(answers: Record<string, any>): {
  isComplete: boolean;
  missingRequired: string[];
} {
  const missingRequired: string[] = [];

  for (const question of CHAT_QUESTIONS) {
    if (!question.required) continue;
    if (question.condition && !question.condition(answers)) continue;

    const answer = answers[question.id];

    if (question.id === 'book_preferences') {
      const bookCount = answer ? Object.keys(answer).length : 0;
      if (bookCount < 4) missingRequired.push(question.id);
    } else if (Array.isArray(answer)) {
      if (answer.length === 0) missingRequired.push(question.id);
    } else if (answer === undefined || answer === null || answer === '') {
      missingRequired.push(question.id);
    }
  }

  return {
    isComplete: missingRequired.length === 0,
    missingRequired,
  };
}

/**
 * Map primary_problems → biggest_challenge for backward compat with rec engine
 */
export function mapAnswersForBackend(answers: Record<string, any>): Record<string, any> {
  const mapped = { ...answers };

  // biggest_challenge is required by rec engine — map from primary_problems if not set
  if (!mapped.biggest_challenge && mapped.primary_problems) {
    mapped.biggest_challenge = mapped.primary_problems;
  }

  // vision_6_12_months — map from future_vision if not set
  if (!mapped.vision_6_12_months && mapped.future_vision) {
    mapped.vision_6_12_months = mapped.future_vision;
  }

  return mapped;
}
