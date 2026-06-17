import './SegmentReadout.css';

interface SegmentReadoutProps {
  value: number | string;
  label?: string;
  /** Pad numeric values to at least this many digits (e.g. 2 → "07"). */
  minDigits?: number;
}

/**
 * Flat "flip-clock" readout: monospace digits in dark cells with a center
 * seam — the Braun flip-clock motif rendered flat (no bevels/gradients).
 */
export default function SegmentReadout({ value, label, minDigits = 0 }: SegmentReadoutProps) {
  let text = String(value);
  if (minDigits && /^\d+$/.test(text)) text = text.padStart(minDigits, '0');
  const chars = text.split('');

  return (
    <div className="rd-readout">
      <div className="rd-readout-digits" aria-label={`${value}`}>
        {chars.map((c, i) => (
          <span key={i} className="rd-readout-cell">{c}</span>
        ))}
      </div>
      {label && <div className="rd-readout-label">{label}</div>}
    </div>
  );
}
