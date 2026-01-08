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

    // Save to backend incrementally
    try {
      await saveToBackend(questionId, answer);
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

  const saveToBackend = async (questionId: string, value: any) => {
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

      // Save incremental progress to backend using PATCH (allows partial updates)
      await apiClient.patchOnboarding(payload);
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
      const filteredAnswers = Object.entries(answers).reduce((acc, [key, value]) => {
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
