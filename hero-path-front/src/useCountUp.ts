import { useState, useEffect, useRef } from 'react'

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

/**
 * Плавно переводит число от прежнего значения к новому.
 *
 * В отличие от useCountUp не начинает с нуля при каждой смене цели:
 * баланс 240 → 120 едет вниз, а не «0 → 120». При включённом
 * «уменьшении движения» в системе число меняется сразу.
 */
export function useAnimatedNumber(target: number, duration = 700) {
  const [value, setValue] = useState(target)
  const fromRef = useRef(target)

  useEffect(() => {
    const from = fromRef.current
    if (from === target) return
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      fromRef.current = target
      setValue(target)
      return
    }
    let raf = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      const current = Math.round(from + (target - from) * eased)
      fromRef.current = current
      setValue(current)
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])

  return value
}
