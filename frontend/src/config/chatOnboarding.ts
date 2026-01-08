/**
 * Chat Onboarding Configuration
 *
 * Simplified questions with 5th-grade reading level in active voice
 * for the conversational chat interface.
 */

// Question types
export type QuestionType =
  | 'select'
  | 'multi-select'
  | 'text'
  | 'textarea'
  | 'book-calibration'
  | 'file-upload';

export interface ChatQuestion {
  id: string;
  question: string;
  type: QuestionType;
  required: boolean;
  options?: { value: string; label: string }[];
  condition?: (answers: Record<string, any>) => boolean;
  order: number;
  helpText?: string;
}

/**
 * All onboarding questions in order
 */
export const CHAT_QUESTIONS: ChatQuestion[] = [
  {
    id: 'entrepreneur_status',
    question: 'Are you working on your business full-time, part-time, or just thinking about it?',
    type: 'select',
    required: false,
    options: [
      { value: 'considering', label: 'Just thinking about it' },
      { value: 'part_time', label: 'Part-time (I have another job)' },
      { value: 'full_time', label: 'Full-time (this is my main focus)' },
    ],
    order: 1,
  },
  {
    id: 'economic_sector',
    question: 'What type of work does your business do?',
    type: 'select',
    required: true,
    options: [
      { value: 'primary', label: 'Making physical things (farming, mining, manufacturing)' },
      { value: 'secondary', label: 'Building things (construction, utilities)' },
      { value: 'tertiary', label: 'Selling things or services (retail, hospitality)' },
      { value: 'quaternary', label: 'Information and knowledge (tech, finance, consulting)' },
      { value: 'quinary', label: 'People services (healthcare, education, government)' },
    ],
    order: 2,
  },
  {
    id: 'industry',
    question: 'Which industry best describes your business?',
    type: 'select',
    required: true,
    options: [], // Dynamically populated based on economic_sector
    order: 3,
  },
  {
    id: 'business_model',
    question: 'How does your business make money? (Pick all that apply)',
    type: 'multi-select',
    required: true,
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
    order: 4,
  },
  {
    id: 'business_stage',
    question: 'What stage is your business at right now?',
    type: 'select',
    required: true,
    options: [
      { value: 'idea', label: 'Just an idea (planning stage)' },
      { value: 'pre-revenue', label: 'Started but not making money yet' },
      { value: 'early-revenue', label: 'Making some money' },
      { value: 'scaling', label: 'Growing and scaling up' },
    ],
    order: 5,
  },
  {
    id: 'current_gross_revenue',
    question: 'How much money does your business make each year?',
    type: 'select',
    required: false,
    options: [
      { value: 'pre-revenue', label: 'Not making money yet' },
      { value: 'under_10k', label: 'Less than $10,000' },
      { value: '10k_50k', label: '$10,000 - $50,000' },
      { value: '50k_100k', label: '$50,000 - $100,000' },
      { value: '100k_250k', label: '$100,000 - $250,000' },
      { value: '250k_500k', label: '$250,000 - $500,000' },
      { value: '500k_1m', label: '$500,000 - $1 million' },
      { value: '1m_5m', label: '$1 million - $5 million' },
      { value: '5m_10m', label: '$5 million - $10 million' },
      { value: '10m_100m', label: '$10 million - $100 million' },
      { value: '100m_plus', label: 'More than $100 million' },
    ],
    condition: (answers) => answers.business_stage !== 'idea',
    order: 6,
  },
  {
    id: 'org_size',
    question: 'How many people work in your business? (Including you)',
    type: 'text',
    required: false,
    helpText: 'You can write a number like "1" or a range like "5-10"',
    order: 7,
  },
  {
    id: 'business_experience',
    question: 'Tell me about your business experience so far. What have you done? What have you learned?',
    type: 'textarea',
    required: false,
    order: 8,
  },
  {
    id: 'areas_of_business',
    question: 'Which parts of your business do you spend the most time on? (Pick all that apply)',
    type: 'multi-select',
    required: false,
    options: [
      { value: 'everything', label: 'Everything (I wear all the hats!)' },
      { value: 'product-offer', label: 'Building the product or service' },
      { value: 'marketing-growth', label: 'Marketing and getting customers' },
      { value: 'customer-success-support', label: 'Taking care of customers' },
      { value: 'finance-metrics', label: 'Managing money and finances' },
      { value: 'operations-systems', label: 'Running day-to-day operations' },
      { value: 'people-hiring', label: 'Managing people and hiring' },
      { value: 'technology-engineering', label: 'Technology and systems' },
      { value: 'other', label: 'Something else' },
    ],
    order: 9,
  },
  {
    id: 'vision_6_12_months',
    question: 'Where do you want your business to be in 6-12 months?',
    type: 'textarea',
    required: false,
    order: 10,
  },
  {
    id: 'biggest_challenge',
    question: "What's the biggest challenge holding you back right now?",
    type: 'textarea',
    required: true,
    order: 11,
  },
  {
    id: 'book_preferences',
    question: 'Here are 6 popular business books. Tell me which ones you like!',
    type: 'book-calibration',
    required: true,
    helpText: 'Pick at least 4 books',
    order: 12,
  },
  {
    id: 'reading_history_csv',
    question: 'Do you use Goodreads to track your reading? You can upload your reading history to help me recommend better books!',
    type: 'file-upload',
    required: false,
    order: 13,
  },
];

/**
 * Industries organized by economic sector
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
  { value: 'read_liked', label: '👍 Read it and loved it', emoji: '👍' },
  { value: 'read_disliked', label: '👎 Read it but didn\'t like it', emoji: '👎' },
  { value: 'interested', label: '📚 Want to read it', emoji: '📚' },
  { value: 'not_interested', label: '🚫 Not interested', emoji: '🚫' },
];

/**
 * Calculate onboarding progress based on answered questions
 */
export function calculateProgress(answers: Record<string, any>): number {
  const totalQuestions = CHAT_QUESTIONS.length;
  let answeredCount = 0;

  for (const question of CHAT_QUESTIONS) {
    const answer = answers[question.id];

    // Check if question should be shown based on condition
    if (question.condition && !question.condition(answers)) {
      continue; // Skip this question in progress calculation
    }

    // Check if answered
    if (question.id === 'book_preferences') {
      // Special case: book calibration needs at least 4 books rated
      const bookCount = answer ? Object.keys(answer).length : 0;
      if (bookCount >= 4) answeredCount++;
    } else if (Array.isArray(answer)) {
      if (answer.length > 0) answeredCount++;
    } else if (answer !== undefined && answer !== null && answer !== '') {
      answeredCount++;
    }
  }

  return Math.round((answeredCount / totalQuestions) * 100);
}

/**
 * Get the next unanswered question
 */
export function getNextQuestion(answers: Record<string, any>): ChatQuestion | null {
  for (const question of CHAT_QUESTIONS) {
    // Check condition
    if (question.condition && !question.condition(answers)) {
      continue;
    }

    // Check if already answered
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

    // Check condition
    if (question.condition && !question.condition(answers)) {
      continue;
    }

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
