import React from 'react';
import './Input.css';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export default function Input({ label, error, className = '', ...props }: InputProps) {
  return (
    <div className={`readar-input-group ${className}`}>
      {label && <label className="readar-input-label">{label}</label>}
      <input className={`readar-input ${error ? 'readar-input--error' : ''}`} {...props} />
      {error && <span className="readar-input-error">{error}</span>}
    </div>
  );
}

