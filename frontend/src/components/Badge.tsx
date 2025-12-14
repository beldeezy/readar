import React from 'react';
import './Badge.css';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'warm' | 'purple' | 'dark';
  size?: 'sm' | 'md';
}

export default function Badge({ children, variant = 'primary', size = 'md' }: BadgeProps) {
  return (
    <span className={`readar-badge readar-badge--${variant} readar-badge--${size}`}>
      {children}
    </span>
  );
}

