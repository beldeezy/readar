import React, { useState, useRef } from "react";
import { apiClient } from "../../api/client";
import Button from "../Button";
import "./ReadingHistoryUploadStep.css";

type Props = {
  userId: string;
  onNext: () => void;
  onBack?: () => void;
  onSkip: () => void;
  isSubmitting?: boolean;
};

export const ReadingHistoryUploadStep: React.FC<Props> = ({
  userId,
  onNext,
  onBack,
  onSkip,
  isSubmitting = false,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
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

  async function importGoodreadsCsv() {
    if (!file) {
      throw new Error("Choose a CSV file first.");
    }

    const result = await apiClient.uploadReadingHistoryCsv({ userId, file });
    setMessage(
      `Imported ${result.imported_count} books (skipped ${result.skipped_count}).`
    );
    return result;
  }

  const handleUploadContinue = async () => {
    setIsUploading(true);
    setError(null);
    setMessage(null);

    try {
      // Try to upload CSV, but don't block on failure
      await importGoodreadsCsv();
    } catch (e) {
      console.error(e);
      // Show error but don't block progression
      setError(e instanceof Error ? e.message : "Failed to upload CSV. You can continue anyway.");
    } finally {
      setIsUploading(false);
    }

    // Always proceed to next step, even if upload failed
    // onNext will attempt to save onboarding data but won't block navigation
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
            disabled={isUploading || !file || isSubmitting}
            delayMs={140}
          >
            {isUploading ? "Uploading..." : isSubmitting ? "Saving..." : "Upload & continue"}
          </Button>
        </div>
      </div>
    </div>
  );
};

