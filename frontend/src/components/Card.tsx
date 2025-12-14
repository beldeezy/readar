import React from 'react';
import './Card.css';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'elevated' | 'flat';
}

export default function Card({ children, className = '', variant = 'default' }: CardProps) {
  return (
    <div className={`readar-card readar-card--${variant} ${className}`}>
      {children}
    </div>
  );
}

