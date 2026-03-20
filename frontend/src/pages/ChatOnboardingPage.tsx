import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { apiClient } from '../api/client';
import type { OnboardingPayload } from '../api/types';
import {
  CHAT_QUESTIONS,
  INDUSTRIES_BY_SECTOR,
  ALL_INDUSTRIES,
  CONNECTION_MESSAGES,
  calculateProgress,
  getNextQuestion,
  validateOnboardingComplete,
  mapAnswersForBackend,
  ChatQuestion,
} from '../config/chatOnboarding';
import ChatMessage from '../components/Onboarding/ChatMessage';
import ChatInput from '../components/Onboarding/ChatInput';
import TransitionStage from '../components/Onboarding/TransitionStage';
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

type PageMode = 'questions' | 'transition' | 'complete';

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

  // Transition stage state
  const [pageMode, setPageMode] = useState<PageMode>('questions');
  const [transitionSummary, setTransitionSummary] = useState('');
  const [transitionLoading, setTransitionLoading] = useState(false);

  // Guard to prevent double execution in React StrictMode
  const initializedRef = useRef(false);

  // Scroll to bottom when new messages appear
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, pageMode]);

  // Load saved progress from localStorage and initialize chat
  useEffect(() => {
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

    // Connection stage — show intro messages before first question
    addBotMessage(CONNECTION_MESSAGES[0], 'system_welcome');

    setTimeout(() => {
      addBotMessage(CONNECTION_MESSAGES[1], 'system_welcome_2');
      setTimeout(() => {
        addBotMessage(CONNECTION_MESSAGES[2], 'system_welcome_3');
        setTimeout(() => {
          showNextQuestion(loadedAnswers);
        }, 800);
      }, 700);
    }, 800);
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
      // All questions answered — move to Transition Stage
      enterTransitionStage(currentAnswers);
      return;
    }

    // Update industry options: use sector-filtered list if known, else all industries
    if (nextQuestion.id === 'industry') {
      const sector = currentAnswers.economic_sector;
      nextQuestion.options = sector && INDUSTRIES_BY_SECTOR[sector]
        ? INDUSTRIES_BY_SECTOR[sector]
        : ALL_INDUSTRIES;
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

    if (displayText) {
      addUserMessage(displayText);
    }

    const updatedAnswers = { ...answers, [questionId]: answer };
    setAnswers(updatedAnswers);

    // Save to backend incrementally using the UPDATED answers snapshot
    try {
      await saveToBackend(questionId, answer, updatedAnswers);
    } catch (err: any) {
      setError(`Failed to save: ${err.message}`);
      const question = CHAT_QUESTIONS.find((q) => q.id === questionId);
      if (question?.required) {
        setIsProcessing(false);
        return;
      }
    }

    setTimeout(() => {
      addBotMessage(getAcknowledgment(questionId));
      setTimeout(() => {
        showNextQuestion(updatedAnswers);
        setIsProcessing(false);
      }, 800);
    }, 300);
  };

  const getAcknowledgment = (questionId: string): string => {
    const acknowledgments: Record<string, string[]> = {
      business_name: ['Great, thanks!', 'Got it!', 'Noted!'],
      business_age: ['Got it', 'Thanks', 'Noted'],
      business_origin: ['That makes sense', 'Thanks for sharing that', 'Understood'],
      primary_problems: ['Thanks for being so open about that', 'Noted', 'I hear you'],
      root_cause: ['That\'s a really important insight', 'Understood', 'Thanks'],
      personal_impact: ['I appreciate you sharing that', 'Noted', 'Thanks for your honesty'],
      secondary_problems: ['Got it, thanks', 'Noted', 'Understood'],
      why_book_not_random: ['That\'s a great reason', 'Totally makes sense', 'Got it'],
      solutions_tried: ['Good to know what you\'ve tried', 'Thanks', 'Noted'],
      book_preferences: ['Great taste!', 'Thanks', 'Noted'],
      reading_history_csv: ['Thanks', 'Got it', 'Noted'],
      ideal_book_description: ['Good to know', 'Noted', 'Got it'],
      future_vision: ['That\'s a great goal', 'Noted', 'Thanks for sharing'],
      consequence_if_unsolved: ['That\'s a real risk worth addressing', 'Noted', 'Understood'],
      why_now: ['Got it — timing matters', 'Noted', 'Understood'],
      business_stage: ['Got it', 'Noted', 'Thanks'],
      business_model: ['Got it', 'Thanks', 'Understood'],
      industry: ['Noted', 'Got it', 'Thanks'],
    };

    const options = acknowledgments[questionId] || ['Got it'];
    return options[Math.floor(Math.random() * options.length)];
  };

  /**
   * Ensures profile exists by creating it once all required fields are collected.
   * Required fields: business_model, business_stage, biggest_challenge
   */
  const ensureProfileExists = async (currentAnswers?: Record<string, any>): Promise<boolean> => {
    if (profileCreated || !user) return profileCreated;

    const answersToCheck = currentAnswers || answers;
    const mapped = mapAnswersForBackend(answersToCheck);

    const hasBusinessModel = mapped.business_model &&
      (Array.isArray(mapped.business_model) ? mapped.business_model.length > 0 : mapped.business_model);
    const hasBusinessStage = mapped.business_stage;
    const hasBiggestChallenge = mapped.biggest_challenge;

    if (!hasBusinessModel || !hasBusinessStage || !hasBiggestChallenge) return false;

    try {
      let normalizedBusinessModel = mapped.business_model;
      if (Array.isArray(normalizedBusinessModel)) {
        normalizedBusinessModel = normalizedBusinessModel.map(String).map((s: string) => s.trim()).filter(Boolean).join(',');
      }

      const payload: any = {
        business_model: normalizedBusinessModel,
        business_stage: mapped.business_stage,
        biggest_challenge: mapped.biggest_challenge,
      };

      const newOptionalFields = [
        'full_name', 'age', 'occupation', 'entrepreneur_status', 'location',
        'economic_sector', 'industry', 'business_experience', 'areas_of_business',
        'org_size', 'is_student', 'vision_6_12_months', 'blockers',
        'current_gross_revenue', 'has_prior_reading_history',
        // New consultative fields
        'business_name', 'business_age', 'business_origin', 'primary_problems',
        'root_cause', 'personal_impact', 'secondary_problems', 'why_book_not_random',
        'solutions_tried', 'ideal_book_description', 'future_vision',
        'consequence_if_unsolved', 'why_now',
      ];

      for (const field of newOptionalFields) {
        if (mapped[field] !== undefined && mapped[field] !== null && mapped[field] !== '') {
          let value = mapped[field];
          if (field === 'current_gross_revenue' && typeof value === 'string') {
            const revenueMap: Record<string, string> = { 'pre-revenue': 'pre_revenue' };
            value = revenueMap[value.trim()] ?? value;
          }
          payload[field] = value;
        }
      }

      await apiClient.saveOnboarding(payload);
      setProfileCreated(true);
      return true;
    } catch (err: any) {
      console.error('[Onboarding] Failed to create profile:', err.message || err);
      return false;
    }
  };

  const saveToBackend = async (questionId: string, value: any, currentAnswers?: Record<string, any>) => {
    if (!user) return;
    if (value === null || value === undefined || value === '' || value === 'skipped') return;

    if (questionId === 'book_preferences') {
      const bookInteractions = Object.entries(value).map(([externalId, status]) => ({
        external_id: externalId,
        status: status as string,
      }));
      await apiClient.saveBookInteractions(bookInteractions);
      return;
    }

    if (questionId === 'reading_history_csv') return;

    const payload: any = {};
    let normalizedValue = value;

    if (questionId === 'business_model') {
      if (Array.isArray(value)) {
        normalizedValue = value.map(String).map((s: string) => s.trim()).filter(Boolean).join(',');
      } else if (typeof value !== 'string') {
        normalizedValue = String(value ?? '');
      }
    }

    if (questionId === 'current_gross_revenue' && typeof normalizedValue === 'string') {
      const revenueMap: Record<string, string> = { 'pre-revenue': 'pre_revenue' };
      normalizedValue = revenueMap[normalizedValue.trim()] ?? normalizedValue;
    }

    // Map primary_problems → biggest_challenge for backend compat
    if (questionId === 'primary_problems') {
      payload['biggest_challenge'] = normalizedValue;
    }

    // Map future_vision → vision_6_12_months for backend compat
    if (questionId === 'future_vision') {
      payload['vision_6_12_months'] = normalizedValue;
    }

    payload[questionId] = normalizedValue;

    const profileCreatedNow = await ensureProfileExists(currentAnswers);

    if (profileCreated || profileCreatedNow) {
      const result = await apiClient.patchOnboarding(payload);
      if (result === null) {
        console.log(`[Onboarding] PATCH returned null for question: ${questionId}`);
      }
    }
  };

  /**
   * Enter the Transition Stage — call Claude to generate a personalized summary.
   */
  const enterTransitionStage = async (currentAnswers: Record<string, any>) => {
    setCurrentQuestion(null);
    setIsProcessing(false);
    addBotMessage("Great — I have everything I need. Let me put together what I've heard from you...");

    setTimeout(() => {
      setPageMode('transition');
      fetchTransitionSummary(currentAnswers);
    }, 1200);
  };

  const fetchTransitionSummary = async (currentAnswers: Record<string, any>, correction?: string) => {
    setTransitionLoading(true);
    setTransitionSummary('');
    try {
      const result = await apiClient.getTransitionSummary(currentAnswers, correction);
      setTransitionSummary(result.summary);

      // Persist transition summary to backend
      if (profileCreated && user) {
        await apiClient.patchOnboarding({
          transition_summary: result.summary,
          transition_correction: correction ?? undefined,
        } as any);
      }
    } catch (err) {
      console.error('[Transition] Failed to generate summary:', err);
      // Graceful fallback — proceed to recommendations without a summary
      setTransitionSummary(
        "Based on what you've shared, I've found a few books that should work well for you. Let's take a look."
      );
    } finally {
      setTransitionLoading(false);
    }
  };

  const handleTransitionConfirm = async () => {
    setPageMode('complete');

    // Save confirmed state
    if (profileCreated && user) {
      try {
        await apiClient.patchOnboarding({ transition_confirmed: true } as any);
      } catch { /* non-fatal */ }
    }

    await handleOnboardingComplete();
  };

  const handleTransitionCorrect = (correction: string) => {
    fetchTransitionSummary(answers, correction);
  };

  const handleOnboardingComplete = async () => {
    setIsProcessing(true);

    try {
      const validation = validateOnboardingComplete(answers);
      if (!validation.isComplete) {
        throw new Error('Please answer all required questions');
      }

      const mapped = mapAnswersForBackend(answers);

      const filteredAnswers = Object.entries(mapped).reduce((acc, [key, value]) => {
        if (key === 'book_preferences' || key === 'reading_history_csv') return acc;
        if (value !== null && value !== undefined && value !== '' && value !== 'skipped') {
          acc[key] = value;
        }
        return acc;
      }, {} as Record<string, any>) as OnboardingPayload;

      // Normalize business_model to CSV string
      if (Array.isArray(filteredAnswers.business_model)) {
        filteredAnswers.business_model = (filteredAnswers.business_model as string[])
          .map(String).map((s: string) => s.trim()).filter(Boolean).join(',');
      }

      // Normalize current_gross_revenue
      if (typeof filteredAnswers.current_gross_revenue === 'string') {
        const v = filteredAnswers.current_gross_revenue.trim();
        if (v === 'pre-revenue') filteredAnswers.current_gross_revenue = 'pre_revenue' as any;
      }

      if (user) {
        await apiClient.saveOnboarding(filteredAnswers);
      }

      localStorage.removeItem('readar_pending_onboarding');

      // Pass answers to recommendations page so it can generate pitches
      navigate('/recommendations/loading', {
        state: { onboardingAnswers: answers },
      });
    } catch (err: any) {
      setError(err.message);
      setIsProcessing(false);
    }
  };

  const handleSkipQuestion = () => {
    if (currentQuestion && !currentQuestion.required) {
      addUserMessage('Skip');
      addBotMessage('No problem');

      setTimeout(() => {
        const updatedAnswers = { ...answers, [currentQuestion.id]: 'skipped' };
        setAnswers(updatedAnswers);

        const nextQuestion = getNextQuestion(updatedAnswers);
        if (!nextQuestion) {
          enterTransitionStage(updatedAnswers);
        } else {
          showNextQuestion(updatedAnswers);
        }
      }, 800);
    }
  };

  return (
    <div className="chat-onboarding-page">
      <header className="chat-header">
        <div className="chat-header-content">
          <h1>Readar</h1>
          <div className="progress-container">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${pageMode === 'transition' || pageMode === 'complete' ? 100 : progress}%` }}
                role="progressbar"
                aria-valuenow={pageMode === 'transition' || pageMode === 'complete' ? 100 : progress}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <span className="progress-text">
              {pageMode === 'transition' || pageMode === 'complete'
                ? 'Almost there!'
                : `${progress}% complete`}
            </span>
          </div>
        </div>
      </header>

      <main className="chat-messages">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {error && (
          <div className="chat-error">
            <p>⚠️ {error}</p>
          </div>
        )}

        {/* Questions mode */}
        {pageMode === 'questions' && (
          <>
            {currentQuestion && !isProcessing && (
              <ChatInput
                question={currentQuestion}
                onAnswer={handleAnswer}
                onSkip={currentQuestion.required ? undefined : handleSkipQuestion}
              />
            )}

            {isProcessing && (
              <div className="chat-processing">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
          </>
        )}

        {/* Transition stage */}
        {pageMode === 'transition' && (
          <TransitionStage
            summary={transitionSummary}
            isLoading={transitionLoading}
            onConfirm={handleTransitionConfirm}
            onCorrect={handleTransitionCorrect}
          />
        )}

        {/* Complete mode — loading state while navigating */}
        {pageMode === 'complete' && (
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
