import './RadarIllustration.css';

export default function RadarIllustration() {
  return (
    <div className="radar-illustration">
      <svg
        className="radar-svg"
        viewBox="0 0 800 600"
        preserveAspectRatio="xMidYMid meet"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Background circles - radar rings */}
        <circle
          cx="400"
          cy="300"
          r="200"
          fill="none"
          stroke="var(--rd-radar)"
          strokeWidth="1.5"
          opacity="0.3"
        />
        <circle
          cx="400"
          cy="300"
          r="150"
          fill="none"
          stroke="var(--rd-radar)"
          strokeWidth="1.5"
          opacity="0.3"
        />
        <circle
          cx="400"
          cy="300"
          r="100"
          fill="none"
          stroke="var(--rd-radar)"
          strokeWidth="1.5"
          opacity="0.3"
        />
        
        {/* Radar sweep - rotating wedge */}
        <g className="radar-sweep">
          <path
            d="M 400 300 L 400 100 A 200 200 0 0 1 550 300 Z"
            fill="var(--rd-accent)"
            opacity="0.15"
          />
        </g>
        
        {/* Book shapes - flat rectangles with spines */}
        <g className="radar-books">
          {/* Top left book */}
          <rect
            x="100"
            y="80"
            width="40"
            height="60"
            fill="var(--rd-surface)"
            stroke="var(--rd-radar)"
            strokeWidth="1.5"
            opacity="0.6"
            rx="2"
          />
          <line
            x1="100"
            y1="80"
            x2="100"
            y2="140"
            stroke="var(--rd-radar)"
            strokeWidth="2"
            opacity="0.4"
          />
          
          {/* Top right book */}
          <rect
            x="660"
            y="100"
            width="40"
            height="60"
            fill="var(--rd-surface)"
            stroke="var(--rd-radar)"
            strokeWidth="1.5"
            opacity="0.6"
            rx="2"
          />
          <line
            x1="660"
            y1="100"
            x2="660"
            y2="160"
            stroke="var(--rd-radar)"
            strokeWidth="2"
            opacity="0.4"
          />
          
          {/* Bottom left book */}
          <rect
            x="80"
            y="460"
            width="40"
            height="60"
            fill="var(--rd-surface)"
            stroke="var(--rd-radar)"
            strokeWidth="1.5"
            opacity="0.6"
            rx="2"
          />
          <line
            x1="80"
            y1="460"
            x2="80"
            y2="520"
            stroke="var(--rd-radar)"
            strokeWidth="2"
            opacity="0.4"
          />
          
          {/* Bottom right book */}
          <rect
            x="680"
            y="480"
            width="40"
            height="60"
            fill="var(--rd-surface)"
            stroke="var(--rd-radar)"
            strokeWidth="1.5"
            opacity="0.6"
            rx="2"
          />
          <line
            x1="680"
            y1="480"
            x2="680"
            y2="540"
            stroke="var(--rd-radar)"
            strokeWidth="2"
            opacity="0.4"
          />
          
          {/* Left side book */}
          <rect
            x="50"
            y="250"
            width="40"
            height="60"
            fill="var(--rd-surface)"
            stroke="var(--rd-radar)"
            strokeWidth="1.5"
            opacity="0.6"
            rx="2"
          />
          <line
            x1="50"
            y1="250"
            x2="50"
            y2="310"
            stroke="var(--rd-radar)"
            strokeWidth="2"
            opacity="0.4"
          />
          
          {/* Right side book */}
          <rect
            x="710"
            y="270"
            width="40"
            height="60"
            fill="var(--rd-surface)"
            stroke="var(--rd-radar)"
            strokeWidth="1.5"
            opacity="0.6"
            rx="2"
          />
          <line
            x1="710"
            y1="270"
            x2="710"
            y2="330"
            stroke="var(--rd-radar)"
            strokeWidth="2"
            opacity="0.4"
          />
        </g>
        
        {/* Center dot */}
        <circle
          cx="400"
          cy="300"
          r="4"
          fill="var(--rd-accent)"
          opacity="0.5"
        />
      </svg>
    </div>
  );
}

