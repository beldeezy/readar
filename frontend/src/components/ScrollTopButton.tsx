import { useEffect, useState } from 'react';
import { ArrowUp } from 'lucide-react';
import './ScrollTopButton.css';

/**
 * Floating "return to top" button — appears after scrolling down,
 * sits bottom-right (above the mobile bottom nav).
 */
export default function ScrollTopButton({ threshold = 400 }: { threshold?: number }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > threshold);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold]);

  if (!visible) return null;

  return (
    <button
      className="rd-scrolltop"
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      aria-label="Return to top"
      title="Return to top"
    >
      <ArrowUp size={20} strokeWidth={2.25} />
    </button>
  );
}
