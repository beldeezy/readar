import { useMemo } from 'react';
import type { KnowledgeMap } from '../api/types';
import './FounderKnowledgeMap.css';

interface Props {
  data: KnowledgeMap;
}

const MAX = 100; // 0-100 FIFA-style scale

// Knowledge altitude ladder (1-5) for the depth indicator
const LEVEL_NAMES: Record<number, string> = {
  1: 'Awareness',
  2: 'Mental models',
  3: 'Principles',
  4: 'Disciplines',
  5: 'Processes',
};
const SIZE = 320; // radar area
const CENTER = SIZE / 2;
const RADIUS = 110; // distance from center to score=100
const LABEL_PAD = 30; // extra radius for labels
const RING_LEVELS = [25, 50, 75, 100]; // gridline rings on the 0-100 scale

// Extra room around the radar so multi-line spoke labels never clip (esp. mobile).
const MARGIN_X = 60;
const MARGIN_Y = 26;

// Spoke angles: start at top (-90°), clockwise, 60° apart.
function angleFor(i: number, n: number): number {
  return (-90 + (360 / n) * i) * (Math.PI / 180);
}

function pointFor(i: number, n: number, score: number, radius = RADIUS): [number, number] {
  const a = angleFor(i, n);
  const r = (score / MAX) * radius;
  return [CENTER + r * Math.cos(a), CENTER + r * Math.sin(a)];
}

function polygon(scores: number[], radius = RADIUS): string {
  return scores
    .map((s, i) => pointFor(i, scores.length, s, radius).join(','))
    .join(' ');
}

// Split "Leadership & People" → ["Leadership", "& People"] for two-line labels.
function splitLabel(label: string): [string, string] {
  const idx = label.indexOf(' & ');
  if (idx === -1) return [label, ''];
  return [label.slice(0, idx), '& ' + label.slice(idx + 3)];
}

export default function FounderKnowledgeMap({ data }: Props) {
  const { domains, ideal, total_books_scored } = data;
  const n = domains.length;

  // Map ideal by key so order always aligns with domains
  const idealByKey = useMemo(() => {
    const m: Record<string, number> = {};
    for (const d of ideal) m[d.key] = d.score;
    return m;
  }, [ideal]);

  const idealScores = domains.map((d) => idealByKey[d.key] ?? 0);
  // Cap the plotted user shape at the ideal so it always fills TOWARD the goal
  // and never pokes past it — visible gaps are exactly the under-read domains.
  const plottedUser = domains.map((d) => Math.min(d.score, idealByKey[d.key] ?? d.score));

  const rings = RING_LEVELS.map((level) => polygon(domains.map(() => level)));
  const isEmpty = total_books_scored === 0;
  const viewBox = `${-MARGIN_X} ${-MARGIN_Y} ${SIZE + 2 * MARGIN_X} ${SIZE + 2 * MARGIN_Y}`;

  return (
    <div className="fkm">
      <svg viewBox={viewBox} className="fkm-svg" role="img" aria-label="Founder Knowledge Map radar chart">
        {/* Radar scope bezel + bearing ticks (instrument framing, flat) */}
        <circle cx={CENTER} cy={CENTER} r={RADIUS + 14} fill="none" stroke="var(--rd-border)" strokeWidth={1.5} />
        {Array.from({ length: 36 }).map((_, k) => {
          const a = ((k * 10 - 90) * Math.PI) / 180;
          const major = k % 9 === 0;
          const rOut = RADIUS + 14;
          const rIn = rOut - (major ? 8 : 4);
          return (
            <line
              key={`tick-${k}`}
              x1={CENTER + rOut * Math.cos(a)}
              y1={CENTER + rOut * Math.sin(a)}
              x2={CENTER + rIn * Math.cos(a)}
              y2={CENTER + rIn * Math.sin(a)}
              stroke={major ? 'var(--rd-accent)' : 'var(--rd-border-strong)'}
              strokeWidth={major ? 2 : 1}
              strokeLinecap="round"
            />
          );
        })}

        {/* Reference rings */}
        {rings.map((pts, i) => (
          <polygon key={i} className="fkm-ring" points={pts} />
        ))}

        {/* Axes */}
        {domains.map((d, i) => {
          const [x, y] = pointFor(i, n, MAX);
          return <line key={d.key} className="fkm-axis" x1={CENTER} y1={CENTER} x2={x} y2={y} />;
        })}

        {/* Ideal target (dashed outline) */}
        {!isEmpty && <polygon className="fkm-ideal" points={polygon(idealScores)} />}

        {/* User shape (capped at the ideal) */}
        {!isEmpty && <polygon className="fkm-user" points={polygon(plottedUser)} />}

        {/* User vertices */}
        {!isEmpty &&
          domains.map((d, i) => {
            if (d.score === 0) return null;
            const [x, y] = pointFor(i, n, plottedUser[i]);
            return <circle key={d.key} className="fkm-dot" cx={x} cy={y} r={3.5} />;
          })}

        {/* Labels (two-line domain name + score) */}
        {domains.map((d, i) => {
          const [x, y] = pointFor(i, n, MAX, RADIUS + LABEL_PAD);
          const anchor = Math.abs(x - CENTER) < 8 ? 'middle' : x > CENTER ? 'start' : 'end';
          const [l1, l2] = splitLabel(d.label);
          const met = d.score >= (idealByKey[d.key] ?? Infinity);
          return (
            <text key={d.key} className="fkm-label" x={x} y={y} textAnchor={anchor} dominantBaseline="middle">
              <tspan className="fkm-label-name" x={x} dy="-1.05em">{l1}</tspan>
              {l2 && (
                <tspan className="fkm-label-name" x={x} dy="1.05em">{l2}</tspan>
              )}
              <tspan className="fkm-label-score" x={x} dy="1.15em">
                {d.score}
                {d.depth ? ` · L${d.depth}` : ''}
                {met ? ' ✓' : ''}
              </tspan>
            </text>
          );
        })}
      </svg>

      <div className="fkm-legend">
        <span className="fkm-legend-item">
          <span className="fkm-swatch fkm-swatch--user" /> Your reading
        </span>
        <span className="fkm-legend-item">
          <span className="fkm-swatch fkm-swatch--ideal" /> Ideal for your stage
        </span>
      </div>

      {!isEmpty && (
        <p className="fkm-depth-key">
          <strong>Filled area</strong> = your reading toward the stage ideal · <strong>✓</strong> ={' '}
          ideal met · <strong>L1–L5</strong> = depth:{' '}
          {[1, 2, 3, 4, 5].map((lvl, i) => (
            <span key={lvl}>
              {i > 0 ? ' · ' : ''}L{lvl} {LEVEL_NAMES[lvl]}
            </span>
          ))}
        </p>
      )}

      {isEmpty && (
        <p className="fkm-empty">
          No scored books yet. Mark books as read or import your Goodreads history
          below to map your founder knowledge.
        </p>
      )}
    </div>
  );
}
