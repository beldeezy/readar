import React from 'react';
import './Badge.css';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'warm' | 'purple' | 'dark';
  size?: 'sm' | 'md';
}

export default function Badge({ children, className = '', variant = 'primary', size = 'md', ...props }: BadgeProps) {
  return (
    <span className={`readar-badge readar-badge--${variant} readar-badge--${size} ${className}`} {...props}>
      {children}
    </span>
  );
}

