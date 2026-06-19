import { useState, useEffect } from 'react'

/**
 * Анимирует число от 0 до target при монтировании или смене target.
 * @param target  — целевое число
 * @param duration — длительность в мс (по умолчанию 1100)
 * @param delay    — задержка старта в мс (по умолчанию 0)
 */
export function useCountUp(target: number, duration = 1100, delay = 0) {
  const [value, setValue] = useState(0)

  useEffect(() => {
    if (target === 0) return
    let raf = 0
    let startTime: number | null = null

    const tick = (now: number) => {
      if (startTime === null) startTime = now
      const elapsed = now - startTime
      if (elapsed < delay) {
        raf = requestAnimationFrame(tick)
        return
      }
      const t = Math.min(1, (elapsed - delay) / duration)
      const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic
      setValue(Math.round(target * eased))
      if (t < 1) raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration, delay])

  return value
}