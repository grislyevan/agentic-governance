import { useState, useEffect, useRef, useCallback } from 'react';

const DEFAULT_INTERVAL = 30_000;

export default function usePolling(callback, interval = DEFAULT_INTERVAL) {
  const [lastUpdated, setLastUpdated] = useState(null);
  const [paused, setPaused] = useState(false);
  const inflight = useRef(false);
  const savedCallback = useRef(callback);

  useEffect(() => { savedCallback.current = callback; }, [callback]);

  useEffect(() => {
    if (paused) return;

    const tick = async () => {
      if (inflight.current) return;
      inflight.current = true;
      try {
        await savedCallback.current();
        setLastUpdated(Date.now());
      } finally {
        inflight.current = false;
      }
    };

    const id = setInterval(tick, interval);
    return () => clearInterval(id);
  }, [interval, paused]);

  useEffect(() => { setLastUpdated(Date.now()); }, []);

  const togglePause = useCallback(() => setPaused(p => !p), []);

  return { lastUpdated, paused, togglePause };
}
