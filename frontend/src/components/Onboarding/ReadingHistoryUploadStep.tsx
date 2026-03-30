import React, { useState, useRef } from "react";
import Button from "../Button";
import { apiClient } from "../../api/client";
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

  const handleUploadContinue = async () => {
    if (!file) {
      setError("Please select a CSV file first.");
      return;
    }

    setIsProcessing(true);
    setError(null);
    setMessage(null);

    try {
      const result = await apiClient.uploadReadingHistoryCsv(file);
      setMessage(
        `✓ Imported ${result.imported_count} books` +
        (result.new_books_added > 0 ? ` (${result.new_books_added} added to catalog)` : "") +
        ". Your reading profile is being generated."
      );
      // Brief pause to let the user read the success message
      await new Promise(resolve => setTimeout(resolve, 900));
      onNext?.();
    } catch (e: any) {
      const detail = e?.response?.data?.detail || (e instanceof Error ? e.message : "Upload failed.");
      setError(detail);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSkip = () => {
    setError(null);
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
            disabled={isSubmitting || isProcessing}
          >
            Back
          </Button>
        )}
        <div className="reading-history-actions-right">
          <Button
            variant="ghost"
            onClick={handleSkip}
            disabled={isSubmitting || isProcessing}
          >
            {isSubmitting ? "Saving..." : "Skip for now"}
          </Button>
          <Button
            variant="mint"
            onClick={handleUploadContinue}
            disabled={isProcessing || !file || isSubmitting}
            delayMs={140}
          >
            {isProcessing ? "Uploading..." : isSubmitting ? "Saving..." : "Upload & continue"}
          </Button>
        </div>
      </div>
    </div>
  );
};
