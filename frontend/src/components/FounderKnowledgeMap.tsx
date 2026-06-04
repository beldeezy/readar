import { useMemo } from 'react';
import type { KnowledgeMap } from '../api/types';
import './FounderKnowledgeMap.css';

interface Props {
  data: KnowledgeMap;
}

const MAX = 3; // 1-3 scale → 3 rings
const SIZE = 320; // svg viewbox
const CENTER = SIZE / 2;
const RADIUS = 110; // distance from center to score=3
const LABEL_PAD = 34; // extra radius for labels

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

export default function FounderKnowledgeMap({ data }: Props) {
  const { domains, ideal, total_books_scored } = data;
  const n = domains.length;

  // Map ideal by key so order always aligns with domains
  const idealByKey = useMemo(() => {
    const m: Record<string, number> = {};
    for (const d of ideal) m[d.key] = d.score;
    return m;
  }, [ideal]);

  const userScores = domains.map((d) => d.score);
  const idealScores = domains.map((d) => idealByKey[d.key] ?? 0);

  // Concentric reference rings (hexagons) at each level
  const rings = Array.from({ length: MAX }, (_, r) =>
    polygon(domains.map(() => r + 1)),
  );

  const isEmpty = total_books_scored === 0;

  return (
    <div className="fkm">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="fkm-svg"
        role="img"
        aria-label="Founder Knowledge Map radar chart"
      >
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
        {!isEmpty && (
          <polygon className="fkm-ideal" points={polygon(idealScores)} />
        )}

        {/* User shape */}
        {!isEmpty && (
          <polygon className="fkm-user" points={polygon(userScores)} />
        )}

        {/* User vertices */}
        {!isEmpty &&
          domains.map((d, i) => {
            const [x, y] = pointFor(i, n, d.score);
            if (d.score === 0) return null;
            return <circle key={d.key} className="fkm-dot" cx={x} cy={y} r={3.5} />;
          })}

        {/* Labels */}
        {domains.map((d, i) => {
          const [x, y] = pointFor(i, n, MAX, RADIUS + LABEL_PAD);
          const anchor = Math.abs(x - CENTER) < 8 ? 'middle' : x > CENTER ? 'start' : 'end';
          return (
            <text
              key={d.key}
              className="fkm-label"
              x={x}
              y={y}
              textAnchor={anchor}
              dominantBaseline="middle"
            >
              <tspan className="fkm-label-name">{d.label}</tspan>
              <tspan className="fkm-label-score" x={x} dy="1.2em">
                {d.score}/{MAX}
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

      {isEmpty && (
        <p className="fkm-empty">
          No scored books yet. Mark books as read or import your Goodreads history
          below to map your founder knowledge.
        </p>
      )}
    </div>
  );
}
