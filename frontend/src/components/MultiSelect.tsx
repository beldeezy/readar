import { useState, useRef, useEffect } from 'react';
import './MultiSelect.css';

interface Option {
  value: string;
  label: string;
}

interface MultiSelectProps {
  options: Option[];
  selectedValues: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  label?: string;
  required?: boolean;
  className?: string;
}

export default function MultiSelect({
  options,
  selectedValues,
  onChange,
  placeholder = 'Select options...',
  label,
  required,
  className = '',
}: MultiSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleToggle = (value: string) => {
    if (value === 'everything') {
      // Special handling for "Everything" option
      if (selectedValues.includes('everything')) {
        // Deselect everything
        onChange([]);
      } else {
        // Select all options including "everything"
        const allValues = options.map(opt => opt.value);
        onChange(allValues);
      }
    } else {
      // Regular toggle
      if (selectedValues.includes(value)) {
        // Deselecting a regular option also deselects "everything" if it was selected
        const newValues = selectedValues.filter(v => v !== value && v !== 'everything');
        onChange(newValues);
      } else {
        // Selecting a regular option - add it but remove "everything" if present
        const newValues = [...selectedValues.filter(v => v !== 'everything'), value];
        onChange(newValues);
      }
    }
  };

  const getDisplayText = () => {
    if (selectedValues.length === 0) {
      return placeholder;
    }
    if (selectedValues.length === 1) {
      const option = options.find(opt => opt.value === selectedValues[0]);
      return option?.label || selectedValues[0];
    }
    return `${selectedValues.length} selected`;
  };

  return (
    <div className={`readar-input-group ${className}`}>
      {label && (
        <label className="readar-input-label">
          {label} {required && '*'}
        </label>
      )}
      <div className="readar-multiselect" ref={containerRef}>
        <button
          type="button"
          className="readar-multiselect-button"
          onClick={() => setIsOpen(!isOpen)}
          aria-expanded={isOpen}
        >
          <span>{getDisplayText()}</span>
          {selectedValues.length > 0 && (
            <span className="readar-multiselect-selected-count">
              {selectedValues.length}
            </span>
          )}
        </button>
        {isOpen && (
          <div className="readar-multiselect-dropdown">
            {options.map((option) => (
              <div
                key={option.value}
                className="readar-multiselect-option"
                onClick={() => handleToggle(option.value)}
              >
                <input
                  type="checkbox"
                  checked={selectedValues.includes(option.value)}
                  onChange={() => {}} // Handled by parent onClick
                  readOnly
                />
                <span className="readar-multiselect-option-label">
                  {option.label}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

