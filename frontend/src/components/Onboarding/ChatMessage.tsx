import React from 'react';
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
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  return (
    <div className={`chat-message ${message.type}`}>
      <div className="message-bubble">
        {message.type === 'bot' && (
          <div className="bot-avatar">
            <RadarIcon size={40} animationDuration={8} />
          </div>
        )}
        <div className="message-content">
          <p>{message.content}</p>
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
