import { useMemo, useState } from "react";
import type { Book } from "@/api/types";
import type { BookPreference } from "@/api/types";
import type { BookStatus } from "../BookCard";
import PrimaryButton from "../PrimaryButton";
import { BookCard } from "../BookCard";

const MIN_SELECTED = 4;

type StatusMap = Record<string, BookStatus | "">;

// Calibration books - typed as Book[] to match BookCard interface
// NOTE: Currently using external_id slugs (e.g., "the-lean-startup") as book.id.
// The backend onboarding router handles both UUIDs and external_id lookups.
// Ideally, these should be fetched from the backend to get real UUIDs.
const CALIBRATION_BOOKS: Book[] = [
  {
    id: "the-lean-startup",
    title: "The Lean Startup",
    subtitle: "How Today's Entrepreneurs Use Continuous Innovation",
    author_name: "Eric Ries",
    description:
      "A playbook for building businesses through rapid experimentation, validated learning, and continuous iteration.",
    thumbnail_url: "",
    cover_image_url: "",
    page_count: 336,
    published_year: 2011,
    categories: ["Startups", "Lean"],
  },
  {
    id: "zero-to-one",
    title: "Zero to One",
    subtitle: "Notes on Startups, or How to Build the Future",
    author_name: "Peter Thiel",
    description:
      "A look at what it takes to create new value from zero instead of copying what already exists.",
    thumbnail_url: "",
    cover_image_url: "",
    page_count: 224,
    published_year: 2014,
    categories: ["Startups", "Strategy"],
  },
  {
    id: "the-e-myth-revisited",
    title: "The E-Myth Revisited",
    subtitle: "Why Most Small Businesses Don't Work and What to Do About It",
    author_name: "Michael E. Gerber",
    description:
      "Why most small businesses don't work and what to do about it. A guide to building systems that work.",
    thumbnail_url: "",
    cover_image_url: "",
    page_count: 268,
    published_year: 1995,
    categories: ["Systems", "Operations"],
  },
  {
    id: "psychology-of-money",
    title: "The Psychology of Money",
    subtitle: "Timeless lessons on wealth, greed, and happiness",
    author_name: "Morgan Housel",
    description:
      "Timeless lessons on wealth, greed, and happiness. How people think about money and make financial decisions.",
    thumbnail_url: "",
    cover_image_url: "",
    page_count: 256,
    published_year: 2020,
    categories: ["Money", "Mindset"],
  },
  {
    id: "deep-work",
    title: "Deep Work",
    subtitle: "Rules for Focused Success in a Distracted World",
    author_name: "Cal Newport",
    description:
      "Rules for focused success in a distracted world. The ability to focus without distraction is becoming increasingly rare.",
    thumbnail_url: "",
    cover_image_url: "",
    page_count: 304,
    published_year: 2016,
    categories: ["Focus", "Productivity"],
  },
  {
    id: "atomic-habits",
    title: "Atomic Habits",
    subtitle: "An Easy & Proven Way to Build Good Habits",
    author_name: "James Clear",
    description:
      "An easy and proven way to build good habits and break bad ones. Tiny changes that make a remarkable difference.",
    thumbnail_url: "",
    cover_image_url: "",
    page_count: 320,
    published_year: 2018,
    categories: ["Habits", "Behavior Change"],
  },
];

export type BookCalibrationStepProps = {
  /** Existing preferences coming from prior onboarding state, if any */
  initialPreferences?: BookPreference[];
  /** Called whenever user changes a selection (optional) */
  onChangePreferences?: (prefs: BookPreference[]) => void;
  /** Called when user hits Continue */
  onContinue?: (prefs: BookPreference[]) => void;
  /** Called when user hits Back */
  onBack?: () => void;
};

export function BookCalibrationStep({
  initialPreferences,
  onChangePreferences,
  onContinue,
  onBack,
}: BookCalibrationStepProps) {
  const [books] = useState<Book[]>(CALIBRATION_BOOKS);
  const [statusByBookId, setStatusByBookId] = useState<StatusMap>(() => {
    const initial: StatusMap = {};

    // seed from initialPreferences (when user returns to this step)
    (initialPreferences ?? []).forEach((pref) => {
      initial[pref.book_id] = pref.status as BookStatus;
    });

    // ensure all calibration books have an entry
    CALIBRATION_BOOKS.forEach((book) => {
      if (initial[book.id] === undefined) initial[book.id] = "";
    });

    return initial;
  });

  const [showNudge, setShowNudge] = useState(false);

  const selectedCount = useMemo(
    () => Object.values(statusByBookId).filter((s): s is BookStatus => s !== "").length,
    [statusByBookId]
  );

  const canSubmit = selectedCount >= MIN_SELECTED;

  // helper: convert map -> BookPreference[]
  const mapToPreferences = (map: StatusMap): BookPreference[] =>
    Object.entries(map)
      .filter((entry): entry is [string, BookStatus] => {
        const [, status] = entry;
        return status !== "";
      })
      .map(([book_id, status]) => ({
        book_id,
        status: status as BookStatus,
      }));

  // Removed useEffect that was causing infinite loop
  // onChangePreferences is now only called on explicit user actions (handleStatusChange)

  function triggerNudge() {
    setShowNudge(true);
    setTimeout(() => setShowNudge(false), 750);
  }

  function handleStatusChange(bookId: string, status: BookStatus | "") {
    setStatusByBookId((prev) => {
      const next: StatusMap = { ...prev, [bookId]: status };
      
      // Notify parent immediately on user action (not in useEffect)
      if (onChangePreferences) {
        const prefs = mapToPreferences(next);
        onChangePreferences(prefs);
      }
      
      return next;
    });
  }

  function handleContinueClick() {
    if (!canSubmit) {
      triggerNudge();
      return;
    }

    const prefs = mapToPreferences(statusByBookId);
    if (onContinue) onContinue(prefs);
  }

  return (
    <div className="book-selection-page">
      <header className="book-selection-header">
        <div>
          <h1>Help us understand your reading preferences</h1>
          <p>
            Select books that reflect your interests and reading history. Pick
            at least {MIN_SELECTED} titles to help us calibrate your
            recommendations.
          </p>
        </div>
      </header>

      <section className="book-grid">
        {books.map((book) => (
          <BookCard
            key={book.id}
            book={book}
            status={statusByBookId[book.id] ?? ""}
            onStatusChange={(status) => handleStatusChange(book.id, status)}
          />
        ))}
      </section>

      <footer className="book-selection-footer">
        <div
          className={`selection-progress ${
            showNudge ? "selection-progress--nudge" : ""
          }`}
        >
          <span>
            {selectedCount} selected (min {MIN_SELECTED})
          </span>
          <span className="selection-progress-underline" />
        </div>

        <div style={{ display: "flex", gap: "0.75rem" }}>
          <button type="button" onClick={onBack} className="btn-subtle">
            Back
          </button>

          <PrimaryButton
            isDisabled={false}
            onClick={handleContinueClick}
            delayMs={140}
          >
            Continue
          </PrimaryButton>
        </div>
      </footer>
    </div>
  );
}

