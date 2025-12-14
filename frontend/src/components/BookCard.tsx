import type { Book } from "../api/types";

// BookStatus matches BookPreferenceStatus
export type BookStatus = "read_liked" | "read_disliked" | "interested" | "not_interested";

type BookCardProps = {
  book: Book;
  status: BookStatus | "";
  onStatusChange: (status: BookStatus | "") => void;
};

export function BookCard({ book, status, onStatusChange }: BookCardProps) {
  const displayCover =
    book.thumbnail_url || book.cover_image_url || undefined;

  const displayYear = book.published_year;

  const metaPieces: string[] = [];
  if (book.author_name) metaPieces.push(book.author_name);
  if (displayYear) metaPieces.push(String(displayYear));
  if (book.page_count) metaPieces.push(`${book.page_count} pages`);

  const metaLine = metaPieces.join(" • ");

  return (
    <article className="book-card">
      {/* Optional cover on top (will inherit card hover/transform styles) */}
      {displayCover && (
        <div className="book-card-cover" style={{ marginBottom: "0.75rem" }}>
          <img
            src={displayCover}
            alt={book.title}
            loading="lazy"
            style={{
              width: "100%",
              borderRadius: "12px",
              objectFit: "cover",
              maxHeight: "180px",
            }}
          />
        </div>
      )}

      {/* TEXT CONTENT */}
      <header style={{ marginBottom: "0.5rem" }}>
        <h2 className="book-card-title">{book.title}</h2>

        {book.author_name && (
          <p className="book-card-author">{book.author_name}</p>
        )}

        {metaLine && <p className="book-card-meta">{metaLine}</p>}
      </header>

      {book.description && (
        <p className="book-card-description">
          {book.description.length > 220
            ? book.description.slice(0, 217) + "…"
            : book.description}
        </p>
      )}

      {/* FOOTER: PREFERENCE DROPDOWN */}
      <div className="book-card-footer">
        <label className="book-card-status-label">
          <span>Your preference</span>
          <select
            className="book-card-status-select"
            value={status}
            onChange={(e) =>
              onStatusChange(e.target.value as BookStatus | "")
            }
          >
            <option value="">No selection</option>
            <option value="read_liked">I&apos;ve read it (liked)</option>
            <option value="read_disliked">I&apos;ve read it (disliked)</option>
            <option value="interested">Interesting</option>
            <option value="not_interested">Not interested</option>
          </select>
        </label>
      </div>
    </article>
  );
}
