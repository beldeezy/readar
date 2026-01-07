import React, { useState } from 'react';
import { ChatQuestion } from '../../config/chatOnboarding';
import BookCalibrationInput from './BookCalibrationInput';
import FileUploadInput from './FileUploadInput';
import './ChatInput.css';

interface ChatInputProps {
  question: ChatQuestion;
  onAnswer: (questionId: string, answer: any, displayText?: string) => void;
  onSkip?: () => void;
}

const ChatInput: React.FC<ChatInputProps> = ({ question, onAnswer, onSkip }) => {
  const [textValue, setTextValue] = useState('');
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);

  const handleSelectOption = (value: string, label: string) => {
    onAnswer(question.id, value, label);
  };

  const handleMultiSelectToggle = (value: string) => {
    const newSelection = selectedOptions.includes(value)
      ? selectedOptions.filter((v) => v !== value)
      : [...selectedOptions, value];
    setSelectedOptions(newSelection);
  };

  const handleMultiSelectSubmit = () => {
    if (selectedOptions.length === 0 && question.required) return;

    const labels = selectedOptions
      .map((val) => question.options?.find((opt) => opt.value === val)?.label)
      .filter(Boolean)
      .join(', ');

    onAnswer(question.id, selectedOptions, labels || 'None selected');
  };

  const handleTextSubmit = () => {
    if (!textValue.trim() && question.required) return;
    onAnswer(question.id, textValue.trim(), textValue.trim());
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (question.type === 'textarea') return; // Allow enter in textarea
      handleTextSubmit();
    }
  };

  // Render different input types
  if (question.type === 'book-calibration') {
    return (
      <div className="chat-input">
        <BookCalibrationInput onAnswer={onAnswer} questionId={question.id} />
      </div>
    );
  }

  if (question.type === 'file-upload') {
    return (
      <div className="chat-input">
        <FileUploadInput onAnswer={onAnswer} onSkip={onSkip} questionId={question.id} />
      </div>
    );
  }

  if (question.type === 'select') {
    return (
      <div className="chat-input">
        <div className="input-options">
          {question.options?.map((option) => (
            <button
              key={option.value}
              className="option-button"
              onClick={() => handleSelectOption(option.value, option.label)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (question.type === 'multi-select') {
    return (
      <div className="chat-input">
        <div className="input-options multi-select">
          {question.options?.map((option) => (
            <button
              key={option.value}
              className={`option-button checkbox ${
                selectedOptions.includes(option.value) ? 'selected' : ''
              }`}
              onClick={() => handleMultiSelectToggle(option.value)}
            >
              <span className="checkbox-icon">
                {selectedOptions.includes(option.value) ? '✓' : ''}
              </span>
              {option.label}
            </button>
          ))}
        </div>
        <div className="input-actions">
          <button
            className="submit-button"
            onClick={handleMultiSelectSubmit}
            disabled={question.required && selectedOptions.length === 0}
          >
            Continue
          </button>
          {onSkip && (
            <button className="skip-button" onClick={onSkip}>
              Skip
            </button>
          )}
        </div>
      </div>
    );
  }

  if (question.type === 'text' || question.type === 'textarea') {
    return (
      <div className="chat-input">
        <div className="text-input-container">
          {question.type === 'text' ? (
            <input
              type="text"
              className="text-input"
              value={textValue}
              onChange={(e) => setTextValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your answer..."
              autoFocus
            />
          ) : (
            <textarea
              className="textarea-input"
              value={textValue}
              onChange={(e) => setTextValue(e.target.value)}
              placeholder="Type your answer..."
              rows={3}
              autoFocus
            />
          )}
        </div>
        <div className="input-actions">
          <button
            className="submit-button"
            onClick={handleTextSubmit}
            disabled={question.required && !textValue.trim()}
          >
            Continue
          </button>
          {onSkip && (
            <button className="skip-button" onClick={onSkip}>
              Skip
            </button>
          )}
        </div>
      </div>
    );
  }

  return null;
};

export default ChatInput;
