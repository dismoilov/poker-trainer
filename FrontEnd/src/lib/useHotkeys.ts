import { useEffect, useCallback } from 'react';

export function useHotkey(key: string, callback: () => void, enabled = true) {
  const stableCallback = useCallback(callback, [callback]);

  useEffect(() => {
    if (!enabled) return;

    function handler(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      )
        return;

      const pressed = e.key === ' ' ? 'Space' : e.key;
      if (pressed === key || pressed.toLowerCase() === key.toLowerCase()) {
        e.preventDefault();
        stableCallback();
      }
    }

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [key, stableCallback, enabled]);
}
