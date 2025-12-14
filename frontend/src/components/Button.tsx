import React from 'react';
import './Button.css';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'warm' | 'purple' | 'mint';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  delayMs?: number;
}

export default function Button({
  variant = 'primary',
  size = 'md',
  children,
  className = '',
  onClick,
  delayMs = 0,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={`readar-button readar-button--${variant} readar-button--${size} ${className}`}
      onClick={(e) => {
        if (!onClick || disabled) return;
        if (delayMs > 0) {
          e.preventDefault();
          e.stopPropagation(); // IMPORTANT: prevents parent <a> navigation
          window.setTimeout(() => onClick(e), delayMs);
          return;
        }
        onClick(e);
      }}
      {...rest}
    >
      {children}
    </button>
  );
}

