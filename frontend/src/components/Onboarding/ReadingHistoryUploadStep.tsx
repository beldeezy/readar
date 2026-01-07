import React, { useState, useRef } from "react";
<<<<<<< HEAD
=======
import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
>>>>>>> claude/setup-production-testing-unmNg
import Button from "../Button";
import "./ReadingHistoryUploadStep.css";

type Props = {
  onNext: () => void;
  onBack?: () => void;
  onSkip: () => void;
  isSubmitting?: boolean;
};

export const ReadingHistoryUploadStep: React.FC<Props> = ({
  onNext,
  onBack,
  onSkip,
  isSubmitting = false,
}) => {
  const { user: authUser } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFileSelect(f: File) {
    if (!f.name.toLowerCase().endsWith(".csv")) {
      setError("Please upload a .csv file from Goodreads.");
      setMessage(null);
      return;
    }
    setFile(f);
    setError(null);
    setMessage(`Selected: ${f.name}`);
  }

  async function validateAndParseCSV(csvFile: File): Promise<number> {
    // Quick local validation - just count non-empty lines (approximation of book count)
    const text = await csvFile.text();
    const lines = text.split('\n').filter(line => line.trim().length > 0);

    // CSV has header row, so book count is lines - 1
    const bookCount = Math.max(0, lines.length - 1);

    return bookCount;
  }

  const handleUploadContinue = async () => {
    if (!file) {
      setError("Please select a CSV file first.");
      return;
    }

    setIsProcessing(true);
    setError(null);
    setMessage(null);

    // Check if user is authenticated before attempting upload
    if (!authUser) {
      // User is not authenticated yet - skip upload and proceed
      // The file will need to be uploaded after they complete authentication
      setMessage("You'll be able to upload your reading history after signing in.");
      setIsUploading(false);
      // Proceed to next step immediately
      onNext?.();
      return;
    }

    try {
<<<<<<< HEAD
      // Validate CSV locally (no backend call)
      const bookCount = await validateAndParseCSV(file);

      // Store flag in localStorage to indicate user has reading history
      // Backend can use this later when implementing full import
      if (bookCount > 0) {
        localStorage.setItem('readar_has_reading_history', 'true');
        localStorage.setItem('readar_reading_history_book_count', String(bookCount));
      }

      setMessage(`✓ File accepted (${bookCount} books detected). Full import coming soon!`);

      // Small delay to show success message
      await new Promise(resolve => setTimeout(resolve, 800));
=======
      // Try to upload CSV if user is authenticated
      await importGoodreadsCsv();
>>>>>>> claude/setup-production-testing-unmNg
    } catch (e) {
      console.error(e);
      setError(e instanceof Error ? e.message : "Failed to parse CSV.");
    } finally {
      setIsProcessing(false);
    }

    // Always proceed to next step
    onNext?.();
  };

  const handleSkip = () => {
    setError(null);
    // Skip immediately without any API calls
    // onSkip just navigates to the next step
    onSkip?.();
  };

  return (
    <div className="reading-history-upload-step">
      <div>
        <h2>Add your prior reading history</h2>
        <p>
          Optional: upload a CSV of books you&apos;ve already read so Readar
          can fine-tune your recommendations.
        </p>
      </div>

      <div className="reading-history-upload-container">
        <p>How to export from Goodreads (optional):</p>
        <ol>
          <li>
            Visit{" "}
            <a
              href="https://www.goodreads.com/review/import"
              target="_blank"
              rel="noreferrer"
            >
              Goodreads &gt; Import/Export
            </a>
            .
          </li>
          <li>Click "Export Library" and download the .csv file.</li>
          <li>Drag and drop that file below (or click to choose it).</li>
        </ol>

        <div
          className="reading-history-dropzone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const dropped = e.dataTransfer.files?.[0];
            if (dropped) handleFileSelect(dropped);
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <p>Drag and drop your Goodreads CSV here,</p>
          <p>or click to browse files</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFileSelect(f);
            }}
          />
        </div>

        {message && (
          <p className="reading-history-message">{message}</p>
        )}
        {error && <p className="reading-history-error">{error}</p>}
      </div>

      <div className="reading-history-actions">
        {onBack && (
          <Button
            variant="ghost"
            onClick={onBack}
            disabled={isSubmitting}
          >
            Back
          </Button>
        )}
        <div className="reading-history-actions-right">
          <Button
            variant="ghost"
            onClick={handleSkip}
            disabled={isSubmitting}
          >
            {isSubmitting ? "Saving..." : "Skip for now"}
          </Button>
          <Button
            variant="mint"
            onClick={handleUploadContinue}
            disabled={isProcessing || !file || isSubmitting}
            delayMs={140}
          >
            {isProcessing ? "Processing..." : isSubmitting ? "Saving..." : "Upload & continue"}
          </Button>
        </div>
      </div>
    </div>
  );
};

