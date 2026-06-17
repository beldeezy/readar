import './Gauge.css';

interface GaugeProps {
  value: number;
  max: number;
  /** Big number shown at center (defaults to the rounded value). */
  displayValue?: string;
  label?: string;
  caption?: string;
  size?: number;   // overall width in px
  ticks?: number;  // number of tick segments (level meter)
}

/**
 * Flat 2D "Braun dial" gauge: a semicircular tick meter with a needle.
 * Level ticks fill with the accent up to the value; everything is flat,
 * brand-palette, no gradients — an instrument readout, not a chart.
 */
export default function Gauge({
  value,
  max,
  displayValue,
  label,
  caption,
  size = 180,
  ticks = 11,
}: GaugeProps) {
  const pct = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  const pad = 14;
  const R = size / 2 - pad;
  const cx = size / 2;
  const cy = R + pad;
  const height = cy + pad + 40; // room for center value + label

  const ptAt = (frac: number, r: number) => {
    const rad = (Math.PI) * (1 - frac); // 0=left, 1=right along the top arc
    return [cx + r * Math.cos(rad), cy - r * Math.sin(rad)] as const;
  };

  const trackPath = `M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`;

  // Level ticks
  const tickEls = [];
  for (let k = 0; k <= ticks; k++) {
    const frac = k / ticks;
    const [x1, y1] = ptAt(frac, R + 1);
    const [x2, y2] = ptAt(frac, R - 9);
    const active = frac <= pct + 0.0001;
    tickEls.push(
      <line
        key={k}
        x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={active ? 'var(--rd-accent)' : 'var(--rd-border-strong)'}
        strokeWidth={2}
        strokeLinecap="round"
      />
    );
  }

  const [nx, ny] = ptAt(pct, R - 16);

  return (
    <div className="rd-gauge" style={{ width: size }}>
      <svg width={size} height={height} viewBox={`0 0 ${size} ${height}`} role="img" aria-label={label || 'gauge'}>
        {/* bezel arc */}
        <path d={trackPath} fill="none" stroke="var(--rd-border)" strokeWidth={1.5} />
        {tickEls}
        {/* needle */}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="var(--rd-accent)" strokeWidth={2.5} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={5} fill="var(--rd-surface)" stroke="var(--rd-accent)" strokeWidth={2} />
        {/* center readout */}
        <text x={cx} y={cy - 14} textAnchor="middle" className="rd-gauge-value">
          {displayValue ?? Math.round(value)}
        </text>
      </svg>
      {label && <div className="rd-gauge-label">{label}</div>}
      {caption && <div className="rd-gauge-caption">{caption}</div>}
    </div>
  );
}
