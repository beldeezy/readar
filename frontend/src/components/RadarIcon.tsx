import React from 'react';
import './RadarIcon.css';

interface RadarIconProps {
  size?: number;
  opacity?: number;
  animationDuration?: number;
  ringColor?: string;
  sweepColor?: string;
  showBlips?: boolean;
  showShadow?: boolean;
}

/**
 * Single 2D flat radar:
 * - Concentric rings + crosshairs
 * - Soft cone with glow starting at the clock hand and fading toward the tail
 * - Bold white offset shadow bottom-right
 * - Tiny book icons that ping as the sweep passes
 * - Ring illumination segments within the sweep wedge
 */
export default function RadarIcon({
  size = 120,
  opacity = 0.9,
  animationDuration = 10,
  ringColor = 'rgba(249, 250, 251, 0.9)',
  sweepColor = 'rgba(53, 255, 201, 0.9)',
  showBlips = true,
  showShadow = true,
}: RadarIconProps) {
  const coreSize = size;
  const shadowOffsetX = showShadow ? 8 : 0;
  const shadowOffsetY = showShadow ? 8 : 0;

  const svgWidth = coreSize + shadowOffsetX;
  const svgHeight = coreSize + shadowOffsetY;

  const centerX = coreSize / 2;
  const centerY = coreSize / 2;

  const outerRingStrokeWidth = 3.5;
  const radius = coreSize / 2 - 4;

  const innerRadius1 = radius * 0.7;
  const innerRadius2 = radius * 0.5;
  const innerRadius3 = radius * 0.3;

  // Sweep geometry – keep inside outer ring
  const sweepRadius = radius - outerRingStrokeWidth / 2 - 2;
  // Near-full sweep (avoid exact 2π to prevent SVG arc edge cases)
  const sweepAngle = (17 * Math.PI) / 18; // ~340°
  const ringSweepAngle = Math.PI / 1; // for ring illumination

  // Hand side: straight up from center
  const handX = centerX;
  const handY = centerY - sweepRadius;

  // Tail side: end of the outer arc
  const tailX = centerX + sweepRadius * Math.sin(sweepAngle);
  const tailY = centerY + sweepRadius * Math.cos(sweepAngle);

  // Tiny book blips: angles in degrees around the radar (0° = top, 90° = right)
  const blipAnglesDeg = [35, 145, 260];
  const blipRadius = radius * 0.65;


  const blips = blipAnglesDeg.map((deg) => {
    const rad = (deg * Math.PI) / 180;
    const x = centerX + blipRadius * Math.sin(rad);
    const y = centerY - blipRadius * Math.cos(rad); // invert Y so 0° is at top

    // CCW: 0° at top, sweep rotates from 0 -> -360,
    // so we want phase to go DOWN as angle increases.
    const phase = 1 - deg / 360; // when sweep reaches this angle (0–1 over full rotation)
    // Window AFTER the sweep passes where the blip is visible
    const t1 = Math.min(phase + 0.04, 0.97);  // slightly after sweep hits
    const t2 = Math.min(phase + 0.16, 0.995); // brief visible window

    return {
      x,
      y,
      phaseStr: phase.toFixed(3),
      t1Str: t1.toFixed(3),
      t2Str: t2.toFixed(3),
    };
  });

  return (
    <svg
      className="radar-icon"
      width={svgWidth}
      height={svgHeight}
      viewBox={`0 0 ${svgWidth} ${svgHeight}`}
      style={{ opacity }}
      xmlns="http://www.w3.org/2000/svg"
    >


      {/* Bold flat white shadow, offset bottom-right */}
      {showShadow && (
        <circle
          className="radar-shadow"
          cx={centerX + shadowOffsetX}
          cy={centerY + shadowOffsetY}
          r={radius}
          fill="rgba(255, 255, 255, 0.75)"
        />
      )}

      {/* Radar core – centered geometry */}
      <g className="radar-core">
        {/* Background inside radar */}
        <circle
          cx={centerX}
          cy={centerY}
          r={radius}
          fill="var(--rd-radar-bg)"
          className="radar-background"
        />

        {/* Outer ring */}
        <circle
          cx={centerX}
          cy={centerY}
          r={radius}
          fill="none"
          stroke={ringColor}
          strokeWidth={outerRingStrokeWidth}
          className="radar-ring-outer"
        />

        {/* Inner rings */}
        <circle
          cx={centerX}
          cy={centerY}
          r={innerRadius1}
          fill="none"
          stroke="rgba(249, 250, 251, 0.5)"
          strokeWidth={1.5}
          className="radar-ring-inner"
        />
        <circle
          cx={centerX}
          cy={centerY}
          r={innerRadius2}
          fill="none"
          stroke="rgba(249, 250, 251, 0.5)"
          strokeWidth={1.5}
          className="radar-ring-inner"
        />
        <circle
          cx={centerX}
          cy={centerY}
          r={innerRadius3}
          fill="none"
          stroke="rgba(249, 250, 251, 0.5)"
          strokeWidth={1.5}
          className="radar-ring-inner"
        />

        {/* Crosshairs */}
        <line
          x1={centerX}
          y1={centerY - radius}
          x2={centerX}
          y2={centerY + radius}
          stroke="rgba(249, 250, 251, 0.4)"
          strokeWidth={1.5}
          className="radar-crosshair"
        />
        <line
          x1={centerX - radius}
          y1={centerY}
          x2={centerX + radius}
          y2={centerY}
          stroke="rgba(249, 250, 251, 0.4)"
          strokeWidth={1.5}
          className="radar-crosshair"
        />

        {/* Tiny book blips – appear briefly as sweep passes */}
        {showBlips && blips.map((blip, index) => (
          <g
            key={index}
            opacity={0}
            transform={`translate(${blip.x} ${blip.y})`}
          >
            {/* Upright book body */}
            <rect
              x={-5}
              y={-7}
              width={10}
              height={14}
              rx={1.6}
              ry={1.6}
              fill="rgba(249, 250, 251, 0.98)"
            />
            {/* Spine line on the left */}
            <line
              x1={-2.5}
              y1={-7}
              x2={-2.5}
              y2={7}
              stroke="rgba(15, 23, 42, 0.85)"
              strokeWidth={0.9}
            />
            {/* Optional page line on the right */}
            <line
              x1={0.5}
              y1={-4.5}
              x2={3}
              y2={-4.5}
              stroke="rgba(148, 163, 184, 0.9)"
              strokeWidth={0.7}
            />
            {/* Drop shadow underneath */}
            <rect
              x={-5.5}
              y={7.5}
              width={11}
              height={2.5}
              rx={1.25}
              ry={1.25}
              fill="rgba(15, 23, 42, 0.45)"
            />
            {/* Ping animation – opacity pulse once per rotation after sweep passes */}
            <animate
              attributeName="opacity"
              dur={`${animationDuration}s`}
              repeatCount="indefinite"
              values="0;0;1;0;0"
              keyTimes={`0;${blip.phaseStr};${blip.t1Str};${blip.t2Str};1`}
            />
          </g>
        ))}

        {/* Sweep – cone with glow starting at the hand, fading toward the tail */}
        <g className="radar-sweep">
          {/* Near-full sweep trail with HARD cutoff (no overlap when it nears the hand again) */}
          {(() => {
            const segments = 96; // smoother trail; 72 is fine if you want lighter DOM
            const maxAngle = sweepAngle; // radians behind the hand
            const step = maxAngle / segments;

            // point on circle at angle "a" where a=0 is the hand direction (top)
            const pt = (a: number, r: number) => ({
              x: centerX + r * Math.sin(a),
              y: centerY - r * Math.cos(a),
            });

            // HARD CUTOFF:
            // - We never render the very last segment(s)
            // - And we force alpha to 0 at/after cutoff
            const cutoffFraction = 0.992; // tail ends just before reaching hand again
            const cutoffIndex = Math.floor(segments * cutoffFraction);

            return Array.from({ length: segments }, (_, i) => {
              if (i >= cutoffIndex) return null; // hard cutoff: nothing drawn

              const a0 = i * step;
              const a1 = (i + 1) * step;

              const p0 = pt(a0, sweepRadius);
              const p1 = pt(a1, sweepRadius);

              // Opacity curve: bright near hand, long smooth decay.
              // Because we hard-stop drawing near the end, there is zero overlap.
              const t = i / cutoffIndex; // 0 at hand, 1 near cutoff
              const alpha = 0.22 * Math.pow(1 - t, 2.4); // tweak 0.22 / 2.4 to taste

              return (
                <path
                  key={i}
                  d={`
                    M ${centerX} ${centerY}
                    L ${p0.x} ${p0.y}
                    A ${sweepRadius} ${sweepRadius} 0 0 1 ${p1.x} ${p1.y}
                    Z
                  `}
                  fill={sweepColor}
                  opacity={alpha}
                />
              );
            }).filter(Boolean);
          })()}

          {/* Ring illumination: short arcs on each ring within the sweep angle */}
          {/* Outer ring segment */}
          <path
            d={`
              M ${centerX} ${centerY - radius}
              A ${radius} ${radius} 0 0 1
                ${centerX + radius * Math.sin(ringSweepAngle)}
                ${centerY + radius * Math.cos(ringSweepAngle)}
            `}
            fill="none"
            stroke={sweepColor}
            strokeWidth={2}
            strokeLinecap="round"
            opacity={0.45}
          />
          {/* Inner ring segment 1 */}
          <path
            d={`
              M ${centerX} ${centerY - innerRadius1}
              A ${innerRadius1} ${innerRadius1} 0 0 1
                ${centerX + innerRadius1 * Math.sin(ringSweepAngle)}
                ${centerY + innerRadius1 * Math.cos(ringSweepAngle)}
            `}
            fill="none"
            stroke={sweepColor}
            strokeWidth={1.6}
            strokeLinecap="round"
            opacity={0.35}
          />
          {/* Inner ring segment 2 */}
          <path
            d={`
              M ${centerX} ${centerY - innerRadius2}
              A ${innerRadius2} ${innerRadius2} 0 0 1
                ${centerX + innerRadius2 * Math.sin(ringSweepAngle)}
                ${centerY + innerRadius2 * Math.cos(ringSweepAngle)}
            `}
            fill="none"
            stroke={sweepColor}
            strokeWidth={1.4}
            strokeLinecap="round"
            opacity={0.3}
          />
          {/* Inner ring segment 3 */}
          <path
            d={`
              M ${centerX} ${centerY - innerRadius3}
              A ${innerRadius3} ${innerRadius3} 0 0 1
                ${centerX + innerRadius3 * Math.sin(ringSweepAngle)}
                ${centerY + innerRadius3 * Math.cos(ringSweepAngle)}
            `}
            fill="none"
            stroke={sweepColor}
            strokeWidth={1.2}
            strokeLinecap="round"
            opacity={0.25}
          />

          {/* Bright outer arc – main edge of the sweep (you currently keep this invisible) */}
          <path
            d={`
              M ${handX} ${handY}
              A ${sweepRadius} ${sweepRadius} 0 0 1 ${tailX} ${tailY}
            `}
            fill="none"
            stroke={sweepColor}
            strokeWidth={2.4}
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0} // keep at 0 to respect your current style
          />

          {/* Leading radial edge (center to hand) */}
          <line
            x1={centerX}
            y1={centerY}
            x2={handX}
            y2={handY}
            stroke={sweepColor}
            strokeWidth={2}
            strokeLinecap="round"
            opacity={0.9}
          />

          {/* Rotate the whole sweep around the radar center */}
          <animateTransform
            attributeName="transform"
            type="rotate"
            from={`0 ${centerX} ${centerY}`}
            to={`-360 ${centerX} ${centerY}`}
            dur={`${animationDuration}s`}
            repeatCount="indefinite"
          />
        </g>

        {/* Center dot */}
        <circle
          cx={centerX}
          cy={centerY}
          r={2.5}
          fill={sweepColor}
          opacity={0.9}
          className="radar-center"
        />
      </g>
    </svg>
  );
}
