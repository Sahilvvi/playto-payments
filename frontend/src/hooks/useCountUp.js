import { useEffect, useRef, useState } from "react";

export function useCountUp(target, duration = 600) {
  const [value, setValue] = useState(target);
  const prev = useRef(target);
  const raf = useRef(null);

  useEffect(() => {
    if (prev.current === target) return;
    const start = prev.current;
    const diff = target - start;
    const startTime = performance.now();

    const tick = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setValue(Math.round(start + diff * eased));
      if (progress < 1) raf.current = requestAnimationFrame(tick);
      else prev.current = target;
    };

    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);

  return value;
}
