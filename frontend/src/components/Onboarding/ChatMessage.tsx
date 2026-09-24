import React, { useEffect, useState } from 'react';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import RadarIcon from '../RadarIcon';
import './ChatMessage.css';

interface Message {
  id: string;
  type: 'bot' | 'user';
  content: string;
  questionId?: string;
  timestamp: Date;
}

interface ChatMessageProps {
  message: Message;
  animate?: boolean;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message, animate = false }) => {
  const reduced = useReducedMotion();
  const [visible, setVisible] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const characters = Array.from(message.content);
  const shouldAnimate = animate && message.type === 'bot' && !reduced && !revealed;
  useEffect(() => {
    if (!animate || reduced || revealed) return;
    const length = Array.from(message.content).length;
    let elapsed = 0;
    const duration = Math.min(2500, Math.max(400, length * 18));
    const timer = window.setInterval(() => {
      elapsed += 30;
      setVisible(Math.ceil(length * elapsed / duration));
      if (elapsed >= duration) { clearInterval(timer); setRevealed(true); }
    }, 30);
    return () => clearInterval(timer);
  }, [animate, reduced, revealed, message.content]);
  return (
    <div className={`chat-message ${message.type}`}>
      <div className="message-bubble">
        {message.type === 'bot' && (
          <div className="bot-avatar">
            <RadarIcon size={40} animationDuration={8} showBlips={false} showShadow={false} />
          </div>
        )}
        <div className="message-content">
          {/* Assistive technology receives one complete message, never character-by-character announcements. */}
          <p aria-hidden={shouldAnimate || undefined}>{shouldAnimate ? characters.slice(0, visible).join('') : message.content}</p>
          {shouldAnimate && <>
            <span className="readar-sr-only" role="status" aria-atomic="true">{message.content}</span>
            <button type="button" className="message-show-all" onClick={() => setRevealed(true)}>Show full message</button>
          </>}
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
