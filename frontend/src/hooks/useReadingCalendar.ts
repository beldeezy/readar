import { useEffect, useState } from 'react';

function calendar() {
  const now = new Date();
  const day = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-');
  return { day, tz: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' };
}

/** Catch midnight and travel without requiring the reader to navigate away. */
export function useReadingCalendar() {
  const [value, setValue] = useState(calendar);
  useEffect(() => {
    const refresh = () => {
      const next = calendar();
      setValue((current) => current.day === next.day && current.tz === next.tz ? current : next);
    };
    const timer = window.setInterval(refresh, 60000);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, []);
  return value;
}
