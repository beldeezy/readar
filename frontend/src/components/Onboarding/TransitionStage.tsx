import React, { useState } from 'react';

interface TransitionStageProps {
  summary: string;
  isLoading: boolean;
  onConfirm: () => void;
  onCorrect: (correction: string) => void;
}

/**
 * TransitionStage — displayed after all onboarding questions are answered.
 *
 * Shows an AI-generated summary of the user's situation (dream outcome,
 * logical problem, emotional impact) and asks them to confirm or correct it.
 * If they correct it, the parent re-fetches a revised summary.
 */
const TransitionStage: React.FC<TransitionStageProps> = ({
  summary,
  isLoading,
  onConfirm,
  onCorrect,
}) => {
  const [showCorrectionInput, setShowCorrectionInput] = useState(false);
  const [correction, setCorrection] = useState('');
  const [correctionError, setCorrectionError] = useState('');

  const handleCorrectClick = () => {
    setShowCorrectionInput(true);
    setCorrectionError('');
  };

  const handleSubmitCorrection = () => {
    if (!correction.trim()) {
      setCorrectionError('Please describe what we got wrong so we can fix it.');
      return;
    }
    onCorrect(correction.trim());
    setShowCorrectionInput(false);
    setCorrection('');
    setCorrectionError('');
  };

  return (
    <div className="transition-stage">
      {/* Loading state */}
      {isLoading && (
        <div className="transition-stage__loading">
          <div className="transition-stage__spinner" />
          <p className="transition-stage__loading-text">
            Pulling together what you've shared…
          </p>
        </div>
      )}

      {/* Summary card */}
      {!isLoading && summary && (
        <>
          <div className="transition-stage__summary-card">
            <p className="transition-stage__summary-text">{summary}</p>
          </div>

          <p className="transition-stage__confirm-question">
            Would you like to clarify anything, or would you like to see your book recommendations?
          </p>

          {!showCorrectionInput ? (
            <div className="transition-stage__actions">
              <button
                className="transition-stage__btn transition-stage__btn--confirm"
                onClick={onConfirm}
              >
                📚 Show me my recommendations
              </button>
              <button
                className="transition-stage__btn transition-stage__btn--correct"
                onClick={handleCorrectClick}
              >
                ✏️ Let me clarify something first…
              </button>
            </div>
          ) : (
            <div className="transition-stage__correction-form">
              <label
                className="transition-stage__correction-label"
                htmlFor="transition-correction"
              >
                What did we get wrong? Let us know and we'll revise it.
              </label>
              <textarea
                id="transition-correction"
                className="transition-stage__correction-input"
                value={correction}
                onChange={(e) => {
                  setCorrection(e.target.value);
                  if (correctionError) setCorrectionError('');
                }}
                placeholder="e.g. My biggest problem is actually cash flow, not team management…"
                rows={4}
              />
              {correctionError && (
                <p className="transition-stage__correction-error">
                  {correctionError}
                </p>
              )}
              <div className="transition-stage__correction-actions">
                <button
                  className="transition-stage__btn transition-stage__btn--submit-correction"
                  onClick={handleSubmitCorrection}
                >
                  Update Summary
                </button>
                <button
                  className="transition-stage__btn transition-stage__btn--cancel"
                  onClick={() => {
                    setShowCorrectionInput(false);
                    setCorrection('');
                    setCorrectionError('');
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default TransitionStage;
