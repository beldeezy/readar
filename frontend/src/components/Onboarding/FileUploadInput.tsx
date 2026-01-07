import React, { useState } from 'react';
import { useAuth } from '../../auth/AuthProvider';
import { apiClient } from '../../api/client';
import './FileUploadInput.css';

interface FileUploadInputProps {
  onAnswer: (questionId: string, answer: any, displayText?: string) => void;
  onSkip?: () => void;
  questionId: string;
}

const FileUploadInput: React.FC<FileUploadInputProps> = ({ onAnswer, onSkip, questionId }) => {
  const { user } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        setError('Please select a CSV file');
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file || !user) return;

    setUploading(true);
    setError(null);

    try {
      // Use apiClient instead of raw fetch to ensure correct base URL and auth
      const result = await apiClient.uploadReadingHistoryCsv({ file });

      const count = result.imported_count || 0;
      const skipped = result.skipped_count || 0;

      onAnswer(
        questionId,
        { uploaded: true, count, skipped },
        `Uploaded reading history (${count} books imported${skipped > 0 ? `, ${skipped} skipped` : ''})`
      );
    } catch (err: any) {
      setError(err.message);
      setUploading(false);
    }
  };

  return (
    <div className="file-upload-input">
      <div className="upload-container">
        <div className="upload-zone">
          <input
            type="file"
            id="csv-upload"
            accept=".csv"
            onChange={handleFileSelect}
            className="file-input"
          />
          <label htmlFor="csv-upload" className="upload-label">
            <div className="upload-icon">📁</div>
            {file ? (
              <div className="file-info">
                <span className="file-name">{file.name}</span>
                <span className="file-size">
                  {(file.size / 1024).toFixed(1)} KB
                </span>
              </div>
            ) : (
              <div className="upload-text">
                <p className="upload-title">Click to select CSV file</p>
                <p className="upload-subtitle">Export your reading history from Goodreads</p>
              </div>
            )}
          </label>
        </div>

        {error && (
          <div className="upload-error">
            <p>⚠️ {error}</p>
          </div>
        )}
      </div>

      <div className="upload-actions">
        {file && !uploading && (
          <button className="submit-button" onClick={handleUpload}>
            Upload File
          </button>
        )}
        {uploading && (
          <button className="submit-button" disabled>
            Uploading...
          </button>
        )}
        {onSkip && (
          <button className="skip-button" onClick={onSkip} disabled={uploading}>
            Skip for now
          </button>
        )}
      </div>

      <div className="upload-help">
        <p>
          <strong>How to export from Goodreads:</strong>
        </p>
        <ol>
          <li>
            Go to{' '}
            <a
              href="https://www.goodreads.com/review/import"
              target="_blank"
              rel="noopener noreferrer"
              className="goodreads-link"
            >
              Goodreads Export Page
            </a>
          </li>
          <li>Click "Export Library" and download the CSV file</li>
          <li>Come back here and upload the file</li>
        </ol>
      </div>
    </div>
  );
};

export default FileUploadInput;
