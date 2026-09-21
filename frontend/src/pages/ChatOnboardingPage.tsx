import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mic, X, Check } from 'lucide-react';
import { apiClient, logEvent } from '../api/client';
import ChatMessage from '../components/Onboarding/ChatMessage';
import RadarIcon from '../components/RadarIcon';
import ReadarBrand from '../components/ReadarBrand';
import { useSpeechToText } from '../hooks/useSpeechToText';
import './ChatOnboardingPage.css';

const fmtTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

interface Message {
  id: string;
  type: 'bot' | 'user';
  content: string;
  timestamp: Date;
}

type ChatTurn = { role: 'assistant' | 'user'; content: string };
type Ui = 'yes_no' | 'confirm' | null;

const PENDING_ONBOARDING_KEY = 'readar_pending_onboarding';
const ONBOARDING_ANSWERS_KEY = 'readar_onboarding_answers';
const PROGRESS_KEY = 'readar_onboarding_progress'; // in-progress chat, for resume-on-refresh
const TOTAL_STAGES = 7; // for a non-labeled progress hint only

let seq = 0;
const newId = (p: string) => `${p}-${Date.now()}-${seq++}`;

interface ChatSnapshot {
  messages: Message[];
  history: ChatTurn[];
  stageIndex: number;
  turnsInStage: number;
  ui: Ui;
  done: boolean;
}

function saveProgress(s: ChatSnapshot) {
  try { localStorage.setItem(PROGRESS_KEY, JSON.stringify(s)); } catch { /* ignore quota */ }
}
function loadProgress(): ChatSnapshot | null {
  try {
    const raw = localStorage.getItem(PROGRESS_KEY);
    return raw ? (JSON.parse(raw) as ChatSnapshot) : null;
  } catch {
    return null;
  }
}
function clearProgress() {
  try { localStorage.removeItem(PROGRESS_KEY); } catch { /* ignore */ }
}

const ChatOnboardingPage: React.FC = () => {
  const navigate = useNavigate();

  const [messages, setMessages] = useState<Message[]>([]);
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [stageIndex, setStageIndex] = useState(0);
  const [turnsInStage, setTurnsInStage] = useState(0);
  const [ui, setUi] = useState<Ui>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<HTMLElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const [showLatest, setShowLatest] = useState(false);
  const [revealingId, setRevealingId] = useState<string | null>(null);
  const scrollToLatest = () => {
    const channel = messagesRef.current;
    if (channel) channel.scrollTop = channel.scrollHeight;
  };
  const initializedRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Grow the textarea with its content (up to a max) so there's always room.
  const autoGrow = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };
  const resetTextareaHeight = () => {
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  // Keep the textarea sized to its content (covers typing AND the live voice stream).
  useLayoutEffect(() => {
    autoGrow();
    if (followLatest.current) scrollToLatest();
  }, [input]);

  // Both composer growth (including voice input) and typing reveal resize the
  // conversation. Follow its end only while the reader is already there.
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      if (followLatest.current) scrollToLatest();
    });
    for (const element of [composerRef.current, transcriptRef.current, messagesRef.current]) {
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [done, completing]);

  // ── Voice-to-text ──────────────────────────────────────────────────────────
  const stt = useSpeechToText();
  const baseTextRef = useRef('');
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<number | null>(null);

  // While recording, stream the transcript into the input (kept behind the
  // recording UI until the user stops — then the textarea reveals it).
  useEffect(() => {
    if (!stt.recording) return;
    const base = baseTextRef.current;
    setInput(stt.transcript ? (base ? `${base} ${stt.transcript}` : stt.transcript) : base);
  }, [stt.transcript, stt.recording]);

  // Elapsed timer while recording.
  useEffect(() => {
    if (stt.recording) {
      setElapsed(0);
      timerRef.current = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [stt.recording]);

  const startRecording = () => {
    if (loading || completing) return;
    baseTextRef.current = input;
    stt.start();
  };
  const stopRecording = () => {
    stt.stop();
    setTimeout(autoGrow, 0);
  };
  const cancelRecording = () => {
    stt.cancel();
    setInput(baseTextRef.current);
    setTimeout(autoGrow, 0);
  };

  useEffect(() => {
    if (followLatest.current) scrollToLatest();
  }, [messages, loading]);

  // Resume a saved chat if present; otherwise kick off the opener (once).
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const saved = loadProgress();
    if (saved && saved.messages?.length) {
      // Rehydrate prior progress (don't re-fire onboarding_started — already counted).
      setMessages(saved.messages.map((m) => ({ ...m, timestamp: new Date(m.timestamp) })));
      setHistory(saved.history);
      setStageIndex(saved.stageIndex);
      setTurnsInStage(saved.turnsInStage);
      setUi(saved.ui);
      setDone(saved.done);
      // If they refreshed right after sending (bot reply was lost), recover it.
      const last = saved.history[saved.history.length - 1];
      if (!saved.done && last && last.role === 'user') {
        void runTurn(saved.history, saved.stageIndex, saved.turnsInStage);
      }
      return;
    }

    void logEvent('onboarding_started');
    void runTurn([], 0, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist in-progress chat so a refresh / accidental nav resumes instead of restarting.
  useEffect(() => {
    if (messages.length === 0) return;
    saveProgress({ messages, history, stageIndex, turnsInStage, ui, done });
  }, [messages, history, stageIndex, turnsInStage, ui, done]);

  const addBot = (content: string) => {
    const id = newId('bot');
    setRevealingId(id);
    setMessages((prev) => [...prev, { id, type: 'bot', content, timestamp: new Date() }]);
  };
  const addUser = (content: string) =>
    setMessages((prev) => [...prev, { id: newId('user'), type: 'user', content, timestamp: new Date() }]);

  async function runTurn(hist: ChatTurn[], stage: number, turns: number) {
    setLoading(true);
    setError(null);
    setUi(null);
    try {
      const res = await apiClient.nepqChat(hist, stage, turns);
      addBot(res.message);
      const nextHist = [...hist, { role: 'assistant' as const, content: res.message }];
      setHistory(nextHist);
      if (res.stage_index > stage) {
        void logEvent('onboarding_stage_advanced', { stage: res.stage_index });
      }
      setStageIndex(res.stage_index);
      setTurnsInStage(res.turns_in_stage);
      setUi(res.ui);
      // Don't auto-redirect — let the user finish reading, then click through.
      if (res.done) {
        setDone(true);
        void logEvent('onboarding_chat_completed', { stage: res.stage_index });
      }
    } catch (e: any) {
      setError('We couldn’t continue just now. Your answers are still here. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  const send = (text: string) => {
    const value = text.trim();
    if (!value || loading || completing || error) return;
    followLatest.current = true;
    setShowLatest(false);
    setRevealingId(null);
    addUser(value);
    setInput('');
    resetTextareaHeight();
    const nextHist = [...history, { role: 'user' as const, content: value }];
    setHistory(nextHist);
    void runTurn(nextHist, stageIndex, turnsInStage);
  };

  async function completeOnboarding(finalHistory: ChatTurn[]) {
    if (loading || completing) return;
    setCompleting(true);
    setError(null);
    try {
      const profile = await apiClient.nepqExtract(finalHistory);
      // Keep the conversation if an older backend returns an empty/incomplete
      // profile instead of an error during a rolling deployment.
      if (!profile || !['idea', 'pre-revenue', 'early-revenue', 'scaling'].includes(profile.business_stage)
        || !['business_model', 'biggest_challenge'].every(
          (key) => typeof profile[key] === 'string' && profile[key].trim(),
        )) {
        throw new Error('Incomplete onboarding profile');
      }
      // The scribe returns the structured fields the engine needs. Store it where
      // the existing /recommendations/loading handoff (auth → save → recs) reads.
      const payload = { full_name: '', ...profile };
      localStorage.setItem(PENDING_ONBOARDING_KEY, JSON.stringify(payload));
      localStorage.setItem(ONBOARDING_ANSWERS_KEY, JSON.stringify(profile));
      clearProgress(); // chat finished — don't resume it next time
      navigate('/recommendations/loading');
    } catch (e: any) {
      setCompleting(false);
      setError('We couldn’t prepare your recommendations just now. Your answers are still here. Please try again.');
    }
  }

  const progress = completing ? 100 : Math.min(100, Math.round((stageIndex / TOTAL_STAGES) * 100));
  const disabled = loading || completing || !!error;

  return (
    <div className="chat-onboarding-page rd-scan-bg">
      <header className="chat-header">
        <div className="chat-header-content">
          <ReadarBrand />
          <h1 className="readar-sr-only">Find your next book</h1>
          {/* Non-labeled progress hint — never reveals the conversation framework */}
          <div className="progress-bar" aria-hidden="true">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </header>

      <main className="chat-messages" ref={messagesRef} aria-label="Onboarding conversation" onScroll={() => {
        const el = messagesRef.current;
        if (!el) return;
        followLatest.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
        setShowLatest(!followLatest.current);
      }}>
        <div ref={transcriptRef}>
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} animate={m.id === revealingId} />
        ))}

        {loading && (
          <div className="chat-processing">
            <RadarIcon size={52} animationDuration={4} showBlips={false} showShadow={false} />
          </div>
        )}

        {error && (
          <div className="chat-error" role="alert">
            <p>⚠️ {error}</p>
            <button
              className="nepq-retry"
              disabled={loading || completing}
              onClick={() => done
                ? completeOnboarding(history)
                : runTurn(history, stageIndex, turnsInStage)}
            >
              Try again
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
        </div>
      </main>

      {completing ? (
        <div className="nepq-finalizing">
          <RadarIcon size={88} animationDuration={6} />
          <p>Pulling your recommendations…</p>
        </div>
      ) : done ? (
        <div className="nepq-finish-bar">
          <button
            className="nepq-finish-btn"
            onClick={() => {
              void logEvent('onboarding_finish_clicked');
              completeOnboarding(history);
            }}
          >
            Take me to my recommendations →
          </button>
        </div>
      ) : (
        <div className="nepq-input-bar" ref={composerRef}>
          {showLatest && <button type="button" className="message-show-all" onClick={() => {
            followLatest.current = true; setShowLatest(false); scrollToLatest();
          }}>Back to latest message ↓</button>}
          {!stt.recording && ui === 'yes_no' && (
            <div className="nepq-quick-replies">
              <button className="nepq-chip" disabled={disabled} onClick={() => send('Yes')}>Yes</button>
              <button className="nepq-chip" disabled={disabled} onClick={() => send('No')}>No</button>
            </div>
          )}
          {!stt.recording && ui === 'confirm' && (
            <div className="nepq-quick-replies">
              <button className="nepq-chip nepq-chip--primary" disabled={disabled} onClick={() => send("Yes, that's right")}>
                Yes, that's right
              </button>
            </div>
          )}

          <div className="nepq-input-row">
            <textarea
              ref={textareaRef}
              className={`nepq-textarea${stt.recording ? ' nepq-textarea--recording' : ''}`}
              value={input}
              readOnly={stt.recording}
              disabled={disabled && !stt.recording}
              placeholder={
                stt.recording
                  ? 'Listening… speak your answer'
                  : ui
                  ? 'Or type your own reply…'
                  : stt.supported
                  ? 'Type or talk-to-text your reply…'
                  : 'Type your reply…'
              }
              aria-label="Your reply"
              rows={1}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  send(input);
                }
              }}
            />
            {!stt.recording && stt.supported && (
              <button
                className="nepq-mic"
                disabled={disabled}
                onClick={startRecording}
                aria-label="Voice input"
                title="Speak your answer"
              >
                <Mic size={20} />
              </button>
            )}
            {!stt.recording && (
              <button className="nepq-send" disabled={disabled || !input.trim()} onClick={() => send(input)}>
                Send
              </button>
            )}
          </div>

          {stt.recording && (
            <div className="nepq-rec-controls">
              <div className="nepq-rec-bars" aria-hidden="true">
                <span></span><span></span><span></span><span></span><span></span>
              </div>
              <span className="nepq-rec-timer">{fmtTime(elapsed)}</span>
              <button className="nepq-rec-btn nepq-rec-cancel" onClick={cancelRecording} aria-label="Cancel recording">
                <X size={18} />
              </button>
              <button className="nepq-rec-btn nepq-rec-stop" onClick={stopRecording} aria-label="Stop and insert">
                <Check size={18} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ChatOnboardingPage;
