import React from 'react';
import './Card.css';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: 'default' | 'elevated' | 'flat';
}

export default function Card({ children, className = '', variant = 'default', ...props }: CardProps) {
  return (
    <div className={`readar-card readar-card--${variant} ${className}`} {...props}>
      {children}
    </div>
  );
}

