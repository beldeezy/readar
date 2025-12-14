/**
 * RadarCluster Component
 * 
 * Manages multiple RadarIcon instances for the hero section.
 * 
 * Desktop: Renders 3-4 radar icons positioned near the edges of the hero.
 * Mobile: Renders a single radar icon below the hero content.
 * 
 * Inspiration: Gumroad-style minimal 2D flat graphics + Dribbble radar examples
 * Intent: Decorative radar around hero edges that hints at Readar's "reading radar" metaphor.
 */

import { useState, useEffect } from 'react';
import RadarIcon from './RadarIcon';
import './RadarCluster.css';

interface RadarClusterProps {
  iconSize?: number;
  iconOpacity?: number;
  animationDuration?: number;
}

export default function RadarCluster({
  iconSize = 140,
  iconOpacity = 0.7, // Increased from 0.35 for more visibility
  animationDuration = 10,
}: RadarClusterProps) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Desktop: multiple radars around edges
  if (!isMobile) {
    return (
      <div className="radar-cluster radar-cluster--desktop">
        <div className="radar-cluster-item radar-cluster-item--top-left">
          <RadarIcon
            size={iconSize}
            opacity={iconOpacity}
            animationDuration={animationDuration}
          />
        </div>
        <div className="radar-cluster-item radar-cluster-item--top-right">
          <RadarIcon
            size={iconSize}
            opacity={iconOpacity}
            animationDuration={animationDuration + 1}
          />
        </div>
        <div className="radar-cluster-item radar-cluster-item--bottom-left">
          <RadarIcon
            size={iconSize * 0.9}
            opacity={iconOpacity * 0.8}
            animationDuration={animationDuration + 2}
          />
        </div>
        <div className="radar-cluster-item radar-cluster-item--bottom-right">
          <RadarIcon
            size={iconSize * 0.85}
            opacity={iconOpacity * 0.75}
            animationDuration={animationDuration + 1.5}
          />
        </div>
      </div>
    );
  }

  // Mobile: single radar below content
  return (
    <div className="radar-cluster radar-cluster--mobile">
      <RadarIcon
        size={iconSize * 0.8}
        opacity={iconOpacity}
        animationDuration={animationDuration}
      />
    </div>
  );
}

