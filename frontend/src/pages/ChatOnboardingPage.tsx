import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { apiClient } from '../api/client';
import {
  CHAT_QUESTIONS,
  INDUSTRIES_BY_SECTOR,
  CALIBRATION_BOOKS,
  calculateProgress,
  getNextQuestion,
  validateOnboardingComplete,
  ChatQuestion,
} from '../config/chatOnboarding';
import ChatMessage from '../components/Onboarding/ChatMessage';
import ChatInput from '../components/Onboarding/ChatInput';
import './ChatOnboardingPage.css';

interface Message {
  id: string;
  type: 'bot' | 'user';
  content: string;
  questionId?: string;
  timestamp: Date;
}

// Collision-proof message ID generator (prevents duplicate IDs in React StrictMode)
let messageSeq = 0;
const newMessageId = (prefix: string) => `${prefix}-${Date.now()}-${messageSeq++}`;

// Deduplication helper (belt + suspenders approach)
const dedupeById = (list: Message[]) => {
  const map = new Map<string, Message>();
  for (const m of list) if (!map.has(m.id)) map.set(m.id, m);
  return Array.from(map.values());
};

const ChatOnboardingPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [currentQuestion, setCurrentQuestion] = useState<ChatQuestion | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [profileCreated, setProfileCreated] = useState(false);

  // Guard to prevent double execution in React StrictMode
  const initializedRef = useRef(false);

  // Scroll to bottom when new messages appear
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load saved progress from localStorage and initialize chat
  useEffect(() => {
    // Guard to prevent double execution in React StrictMode
    if (initializedRef.current) return;
    initializedRef.current = true;

    const savedData = localStorage.getItem('readar_pending_onboarding');
    let loadedAnswers = {};

    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        loadedAnswers = parsed;
        setAnswers(parsed);
        setProgress(calculateProgress(parsed));
      } catch (err) {
        console.error('Failed to load saved progress:', err);
      }
    }

    // Start with welcome message (with deterministic questionId)
    addBotMessage(
      'Welcome to Readar. Answer a few questions to get personalized book recommendations for your business.',
      'system_welcome'
    );

    // Show first question after a brief delay
    setTimeout(() => {
      showNextQuestion(loadedAnswers);
    }, 1000);
  }, []);

  // Save progress to localStorage whenever answers change
  useEffect(() => {
    if (Object.keys(answers).length > 0) {
      localStorage.setItem('readar_pending_onboarding', JSON.stringify(answers));
      setProgress(calculateProgress(answers));
    }
  }, [answers]);

  const addBotMessage = (content: string, questionId?: string) => {
    const message: Message = {
      id: newMessageId('bot'),
      type: 'bot',
      content,
      questionId,
      timestamp: new Date(),
    };
    setMessages((prev) => dedupeById([...prev, message]));
  };

  const addUserMessage = (content: string) => {
    const message: Message = {
      id: newMessageId('user'),
      type: 'user',
      content,
      timestamp: new Date(),
    };
    setMessages((prev) => dedupeById([...prev, message]));
  };

  const showNextQuestion = (currentAnswers: Record<string, any>) => {
    const nextQuestion = getNextQuestion(currentAnswers);

    if (!nextQuestion) {
      // All questions answered
      handleOnboardingComplete();
      return;
    }

    // Update industry options based on sector selection
    if (nextQuestion.id === 'industry') {
      const sector = currentAnswers.economic_sector;
      if (sector && INDUSTRIES_BY_SECTOR[sector]) {
        nextQuestion.options = INDUSTRIES_BY_SECTOR[sector];
      }
    }

    setCurrentQuestion(nextQuestion);
    addBotMessage(nextQuestion.question, nextQuestion.id);

    if (nextQuestion.helpText) {
      setTimeout(() => {
        addBotMessage(nextQuestion.helpText!, nextQuestion.id);
      }, 500);
    }
  };

  const handleAnswer = async (questionId: string, answer: any, displayText?: string) => {
    setIsProcessing(true);
    setError(null);

    // Add user's answer to chat
    if (displayText) {
      addUserMessage(displayText);
    }

    // Update answers
    const updatedAnswers = {
      ...answers,
      [questionId]: answer,
    };
    setAnswers(updatedAnswers);

    // Save to backend incrementally with updated answers
    try {
      await saveToBackend(questionId, answer, updatedAnswers);
    } catch (err: any) {
      setError(`Failed to save: ${err.message}`);
      // Don't block progression on save errors for optional questions
      const question = CHAT_QUESTIONS.find((q) => q.id === questionId);
      if (question?.required) {
        setIsProcessing(false);
        return;
      }
    }

    // Add acknowledgment
    setTimeout(() => {
      addBotMessage(getAcknowledgment(questionId));

      // Show next question
      setTimeout(() => {
        showNextQuestion(updatedAnswers);
        setIsProcessing(false);
      }, 800);
    }, 300);
  };

  const getAcknowledgment = (questionId: string): string => {
    const acknowledgments: Record<string, string[]> = {
      entrepreneur_status: ['Got it', 'Thanks', 'Noted'],
      economic_sector: ['Understood', 'Got it', 'Thanks'],
      industry: ['Noted', 'Got it', 'Thanks'],
      business_model: ['Got it', 'Thanks', 'Understood'],
      business_stage: ['Noted', 'Got it', 'Thanks'],
      current_gross_revenue: ['Thanks', 'Got it', 'Noted'],
      org_size: ['Understood', 'Got it', 'Thanks'],
      business_experience: ['Thanks', 'Noted', 'Got it'],
      areas_of_business: ['Got it', 'Noted', 'Thanks'],
      vision_6_12_months: ['Noted', 'Thanks', 'Got it'],
      biggest_challenge: ['Thanks', 'Noted', 'Got it'],
      book_preferences: ['Thanks', 'Noted', 'Got it'],
      reading_history_csv: ['Thanks', 'Got it', 'Noted'],
    };

    const options = acknowledgments[questionId] || ['Got it'];
    return options[Math.floor(Math.random() * options.length)];
  };

  /**
   * Ensures profile exists by creating it once all required fields are collected.
   * Required fields: business_model, business_stage, biggest_challenge
   * Returns true if profile was created or already exists, false if required fields are missing.
   */
  const ensureProfileExists = async (currentAnswers?: Record<string, any>): Promise<boolean> => {
    if (profileCreated || !user) return profileCreated;

    // Use provided answers or fall back to state
    const answersToCheck = currentAnswers || answers;

    // Check if we have all required fields
    const hasBusinessModel = answersToCheck.business_model &&
      (Array.isArray(answersToCheck.business_model) ? answersToCheck.business_model.length > 0 : answersToCheck.business_model);
    const hasBusinessStage = answersToCheck.business_stage;
    const hasBiggestChallenge = answersToCheck.biggest_challenge;

    if (!hasBusinessModel || !hasBusinessStage || !hasBiggestChallenge) {
      // Not ready to create profile yet
      return false;
    }

    console.log('[Onboarding] All required fields collected, creating profile');

    try {
      // Normalize business_model (array to CSV string)
      let normalizedBusinessModel = answersToCheck.business_model;
      if (Array.isArray(normalizedBusinessModel)) {
        normalizedBusinessModel = normalizedBusinessModel.map(String).map(s => s.trim()).filter(Boolean).join(',');
      }

      // Prepare payload with all current answers
      const payload: any = {
        business_model: normalizedBusinessModel,
        business_stage: answersToCheck.business_stage,
        biggest_challenge: answersToCheck.biggest_challenge,
      };

      // Include optional fields if they exist
      // NOTE: Exclude book_preferences - already saved via /api/onboarding/book-interactions
      const optionalFields = [
        'full_name', 'age', 'occupation', 'entrepreneur_status', 'location',
        'economic_sector', 'industry', 'business_experience', 'areas_of_business',
        'org_size', 'is_student', 'vision_6_12_months', 'blockers',
        'current_gross_revenue', 'has_prior_reading_history'
      ];

      for (const field of optionalFields) {
        if (answersToCheck[field] !== undefined && answersToCheck[field] !== null && answersToCheck[field] !== '') {
          let value = answersToCheck[field];

          // Normalize current_gross_revenue
          if (field === 'current_gross_revenue' && typeof value === 'string') {
            const revenueMap: Record<string, string> = {
              'pre-revenue': 'pre_revenue',
            };
            value = revenueMap[value.trim()] ?? value;
          }

          payload[field] = value;
        }
      }

      // Create profile using POST
      console.log('[Onboarding] Creating profile via POST with payload:', Object.keys(payload));
      const response = await apiClient.saveOnboarding(payload);
      setProfileCreated(true);
      console.log('[Onboarding] Profile created successfully, status:', response ? 'success' : 'unknown');
      return true;
    } catch (err: any) {
      console.error('[Onboarding] Failed to create profile:', err.message || err);
      // Don't throw - let onboarding continue, will retry on final submit
      return false;
    }
  };

  const saveToBackend = async (questionId: string, value: any, currentAnswers?: Record<string, any>) => {
    if (!user) return;

    // Skip saving empty, null, undefined, or "skipped" values
    if (
      value === null ||
      value === undefined ||
      value === '' ||
      value === 'skipped'
    ) {
      return;
    }

    // Prepare payload based on question type
    const payload: any = {};

    if (questionId === 'book_preferences') {
      // Handle book preferences separately using apiClient
      const bookInteractions = Object.entries(value).map(([externalId, status]) => ({
        external_id: externalId,
        status: status as string,
      }));

      await apiClient.saveBookInteractions(bookInteractions);
    } else if (questionId === 'reading_history_csv') {
      // CSV upload is handled separately in the file upload component
      return;
    } else {
      // Regular field
      let normalizedValue = value;

      // Backend expects business_model as a CSV string, but UI multi-select returns string[]
      if (questionId === 'business_model') {
        if (Array.isArray(value)) {
          normalizedValue = value.map(String).map(s => s.trim()).filter(Boolean).join(',');
        } else if (typeof value !== 'string') {
          normalizedValue = String(value ?? '');
        }
      }

      // Normalize current_gross_revenue to backend RevenueRange literals (legacy-safe)
      if (questionId === 'current_gross_revenue' && typeof normalizedValue === 'string') {
        const v = normalizedValue.trim();
        const revenueMap: Record<string, string> = {
          'pre-revenue': 'pre_revenue', // legacy hyphenated value
        };
        normalizedValue = revenueMap[v] ?? v;
      }

      payload[questionId] = normalizedValue;

      // Try to create profile if we have all required fields (using updated answers)
      const profileCreatedNow = await ensureProfileExists(currentAnswers);

      // Only attempt PATCH if profile exists
      if (profileCreated || profileCreatedNow) {
        // Save incremental progress to backend using PATCH
        const result = await apiClient.patchOnboarding(payload);
        if (result === null) {
          console.log(`[Onboarding] Unexpected: PATCH returned null even though profile should exist (question: ${questionId})`);
        }
      } else {
        console.log(`[Onboarding] Profile not yet created (missing required fields), skipping PATCH for question: ${questionId}`);
      }
    }
  };

  const handleOnboardingComplete = async () => {
    addBotMessage('Perfect! You\'re all set. Let me find the best books for you...');

    setIsProcessing(true);

    try {
      // Validate all required fields
      const validation = validateOnboardingComplete(answers);
      if (!validation.isComplete) {
        throw new Error('Please answer all required questions');
      }

      // Filter answers to only include non-empty, non-skipped values
      // This prevents sending null/empty/skipped fields to the backend
      // NOTE: Exclude book_preferences and reading_history_csv - already saved via separate endpoints
      const filteredAnswers = Object.entries(answers).reduce((acc, [key, value]) => {
        // Skip book_preferences (already saved via /api/onboarding/book-interactions)
        // Skip reading_history_csv (already saved via CSV upload)
        if (key === 'book_preferences' || key === 'reading_history_csv') {
          return acc;
        }

        // Skip empty, null, undefined, and "skipped" values
        if (
          value !== null &&
          value !== undefined &&
          value !== '' &&
          value !== 'skipped'
        ) {
          acc[key] = value;
        }
        return acc;
      }, {} as Record<string, any>);

      // Normalize business_model to CSV string for backend schema
      if (Array.isArray(filteredAnswers.business_model)) {
        filteredAnswers.business_model = filteredAnswers.business_model
          .map(String).map((s) => s.trim()).filter(Boolean).join(',');
      }

      // Normalize current_gross_revenue for backend schema (legacy-safe)
      if (typeof filteredAnswers.current_gross_revenue === 'string') {
        const v = filteredAnswers.current_gross_revenue.trim();
        if (v === 'pre-revenue') filteredAnswers.current_gross_revenue = 'pre_revenue';
      }

      // Final save to backend (full profile) using apiClient
      if (user) {
        await apiClient.saveOnboarding(filteredAnswers);
      }

      // Clear localStorage
      localStorage.removeItem('readar_pending_onboarding');

      // Navigate to recommendations loading page
      setTimeout(() => {
        navigate('/recommendations/loading');
      }, 1500);
    } catch (err: any) {
      setError(err.message);
      addBotMessage("Oops! Something went wrong. Let me try to help you fix that.");
      setIsProcessing(false);
    }
  };

  const handleSkipQuestion = () => {
    if (currentQuestion && !currentQuestion.required) {
      addUserMessage('Skip');
      addBotMessage('No problem');

      setTimeout(() => {
        // Mark as skipped by setting a placeholder value
        const updatedAnswers = {
          ...answers,
          [currentQuestion.id]: 'skipped',
        };
        setAnswers(updatedAnswers);

        // Check if there are more questions after marking this one as skipped
        const nextQuestion = getNextQuestion(updatedAnswers);
        if (!nextQuestion) {
          // No more questions, complete onboarding
          handleOnboardingComplete();
        } else {
          // Show next question
          showNextQuestion(updatedAnswers);
        }
      }, 800);
    }
  };

  return (
    <div className="chat-onboarding-page">
      {/* Header with progress bar */}
      <header className="chat-header">
        <div className="chat-header-content">
          <h1>Readar</h1>
          <div className="progress-container">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${progress}%` }}
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <span className="progress-text">{progress}% complete</span>
          </div>
        </div>
      </header>

      {/* Chat messages */}
      <main className="chat-messages">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {/* Error message */}
        {error && (
          <div className="chat-error">
            <p>⚠️ {error}</p>
          </div>
        )}

        {/* Current question input */}
        {currentQuestion && !isProcessing && (
          <ChatInput
            question={currentQuestion}
            onAnswer={handleAnswer}
            onSkip={currentQuestion.required ? undefined : handleSkipQuestion}
          />
        )}

        {/* Processing indicator */}
        {isProcessing && (
          <div className="chat-processing">
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </main>
    </div>
  );
};

export default ChatOnboardingPage;
