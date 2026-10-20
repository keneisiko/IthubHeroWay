import { useEffect, useRef } from 'react'
import { BURST_EVENT, type BurstDetail } from '../lib/pixelBurst'

/**
 * Живой фон входа: сетка пикселей IThub, по которой идут «герои».
 *
 * Каждый герой шагает по клеткам к жёлтой монете и оставляет за собой
 * гаснущий след — путь героя буквально. Подобрал монету — вспышка,
 * следующая монета появляется в другом месте. Курсор и касание
 * подсвечивают клетки рядом, а ввод в поля формы выпускает волну
 * от поля (pixelBurst из lib/pixelBurst).
 *
 * Рисуем только то, что светится: статичная сетка точек отрисована один
 * раз в отдельный слой. Вкладка скрыта — цикл стоит. При «уменьшить
 * движение» остаётся один неподвижный кадр с уже пройденным путём.
 */


interface Walker {
  c: number
  r: number
  dc: number
  dr: number
  coin: { c: number; r: number }
  acc: number
}

const STEP_MS = 85
const TRAIL_DECAY = 0.955
const TONES = {
  light: [255, 255, 255],
  coin: [255, 217, 0],
  error: [253, 78, 78],
} as const

export default function PixelField({ className = '' }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    let cell = 24
    let cols = 0
    let rows = 0
    let width = 0
    let height = 0
    let energy = new Float32Array(0)
    let tone = new Uint8Array(0)
    let walkers: Walker[] = []
    const grid = document.createElement('canvas')
    const pointer = { x: -9999, y: -9999, active: false }
    let raf = 0
    let last = 0
    let running = false

    const idx = (c: number, r: number) => r * cols + c
    const rand = (n: number) => Math.floor(Math.random() * n)

    const light = (c: number, r: number, value: number, t = 0) => {
      if (c < 0 || r < 0 || c >= cols || r >= rows) return
      const i = idx(c, r)
      if (value >= energy[i]) {
        energy[i] = Math.min(1, value)
        tone[i] = t
      }
    }

    const placeCoin = (w: Walker) => {
      const span = Math.max(6, Math.floor(Math.min(cols, rows) * 0.6))
      for (let tries = 0; tries < 12; tries++) {
        const c = Math.max(1, Math.min(cols - 2, w.c + rand(span * 2) - span))
        const r = Math.max(1, Math.min(rows - 2, w.r + rand(span * 2) - span))
        if (Math.abs(c - w.c) + Math.abs(r - w.r) > 5) {
          w.coin = { c, r }
          return
        }
      }
      w.coin = { c: rand(cols), r: rand(rows) }
    }

    const makeWalker = (): Walker => {
      const w: Walker = { c: rand(cols), r: rand(rows), dc: 1, dr: 0, coin: { c: 0, r: 0 }, acc: Math.random() * STEP_MS }
      placeCoin(w)
      return w
    }

    const ripple = (cx: number, cy: number, power: number, t: number) => {
      const c0 = Math.floor(cx / cell)
      const r0 = Math.floor(cy / cell)
      const radius = Math.round(2 + power * 4)
      for (let dr = -radius; dr <= radius; dr++) {
        for (let dc = -radius; dc <= radius; dc++) {
          const d = Math.abs(dc) + Math.abs(dr)
          if (d > radius) continue
          // ромб с яркой кромкой: волна, а не пятно
          const edge = 1 - Math.abs(d - radius * 0.7) / radius
          light(c0 + dc, r0 + dr, Math.max(0, edge) * power, t)
        }
      }
    }

    const step = (w: Walker) => {
      const options: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1]]
      const scored = options
        .filter(([dc, dr]) => !(dc === -w.dc && dr === -w.dr))
        .map(([dc, dr]) => {
          const nc = w.c + dc
          const nr = w.r + dr
          if (nc < 0 || nr < 0 || nc >= cols || nr >= rows) return { dc, dr, s: -Infinity }
          const dist = Math.abs(w.coin.c - nc) + Math.abs(w.coin.r - nr)
          const straight = dc === w.dc && dr === w.dr ? 1.4 : 0
          return { dc, dr, s: -dist + straight + Math.random() * 2.2 }
        })
        .sort((a, b) => b.s - a.s)
      const pick = scored[0]
      if (!pick || pick.s === -Infinity) {
        w.dc = -w.dc
        w.dr = -w.dr
        return
      }
      w.dc = pick.dc
      w.dr = pick.dr
      w.c += pick.dc
      w.r += pick.dr
      light(w.c, w.r, 1)
      if (w.c === w.coin.c && w.r === w.coin.r) {
        ripple((w.c + 0.5) * cell, (w.r + 0.5) * cell, 0.9, 1)
        placeCoin(w)
      }
    }

    const drawGrid = () => {
      grid.width = Math.ceil(width * dpr)
      grid.height = Math.ceil(height * dpr)
      const g = grid.getContext('2d')
      if (!g) return
      g.scale(dpr, dpr)
      g.fillStyle = 'rgba(255, 255, 255, 0.09)'
      const dot = 2
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          g.fillRect(c * cell + cell / 2 - dot / 2, r * cell + cell / 2 - dot / 2, dot, dot)
        }
      }
    }

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      width = rect.width
      height = rect.height
      cell = width < 640 ? 20 : 24
      cols = Math.ceil(width / cell)
      rows = Math.ceil(height / cell)
      canvas.width = Math.ceil(width * dpr)
      canvas.height = Math.ceil(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      energy = new Float32Array(cols * rows)
      tone = new Uint8Array(cols * rows)
      const count = width < 640 ? 2 : 4
      walkers = Array.from({ length: count }, makeWalker)
      drawGrid()
    }

    const render = (time: number) => {
      ctx.clearRect(0, 0, width, height)
      ctx.drawImage(grid, 0, 0, width, height)

      const inset = cell * 0.16
      const size = cell - inset * 2
      for (let i = 0; i < energy.length; i++) {
        const e = energy[i]
        if (e < 0.015) continue
        const c = i % cols
        const r = (i - c) / cols
        const [cr, cg, cb] = tone[i] === 1 ? TONES.coin : tone[i] === 2 ? TONES.error : TONES.light
        ctx.fillStyle = `rgba(${cr}, ${cg}, ${cb}, ${(e * 0.55).toFixed(3)})`
        ctx.fillRect(c * cell + inset, r * cell + inset, size, size)
      }

      // монета «дышит» размером, а не прозрачностью: полупрозрачный
      // жёлтый на тёмно-фиолетовом смешивается в болотный
      const coinSize = size * (0.62 + Math.sin(time / 240) * 0.1)
      for (const w of walkers) {
        const x = w.coin.c * cell + cell / 2
        const y = w.coin.r * cell + cell / 2
        ctx.fillStyle = '#ffd900'
        ctx.fillRect(x - coinSize / 2, y - coinSize / 2, coinSize, coinSize)
        ctx.fillStyle = '#c9a800'
        ctx.fillRect(x - 2, y - 2, 4, 4)

        // голова героя — знак IThub: квадрат в квадрате
        const hx = w.c * cell
        const hy = w.r * cell
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)'
        ctx.lineWidth = 2
        ctx.strokeRect(hx + inset + 1, hy + inset + 1, size - 2, size - 2)
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(hx + cell / 2 - 3, hy + cell / 2 - 3, 6, 6)
      }
    }

    const tick = (time: number) => {
      const dt = Math.min(64, last ? time - last : 16)
      last = time
      for (const w of walkers) {
        w.acc += dt
        while (w.acc >= STEP_MS) {
          w.acc -= STEP_MS
          step(w)
        }
      }
      const decay = Math.pow(TRAIL_DECAY, dt / 16.67)
      for (let i = 0; i < energy.length; i++) {
        if (energy[i] > 0) energy[i] *= decay
      }
      if (pointer.active) {
        const pc = Math.floor(pointer.x / cell)
        const pr = Math.floor(pointer.y / cell)
        for (let dr = -2; dr <= 2; dr++) {
          for (let dc = -2; dc <= 2; dc++) {
            const d = Math.hypot(dc, dr)
            if (d <= 2.2) light(pc + dc, pr + dr, (1 - d / 2.6) * 0.5)
          }
        }
      }
      render(time)
      raf = requestAnimationFrame(tick)
    }

    const start = () => {
      if (running || reduce) return
      running = true
      last = 0
      raf = requestAnimationFrame(tick)
    }

    const stop = () => {
      running = false
      cancelAnimationFrame(raf)
    }

    const bakeStill = () => {
      // один кадр с уже пройденными тропами — фон не пустой и без движения
      for (const w of walkers) {
        for (let s = 0; s < 40; s++) {
          step(w)
          for (let i = 0; i < energy.length; i++) energy[i] *= 0.97
        }
      }
      render(0)
    }

    const onPointer = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect()
      pointer.x = e.clientX - rect.left
      pointer.y = e.clientY - rect.top
      pointer.active = true
    }
    const onLeave = () => { pointer.active = false }
    const onUp = (e: PointerEvent) => {
      // палец убрали — подсветка не должна залипать там, где было касание
      if (e.pointerType !== 'mouse') pointer.active = false
    }
    const onDown = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect()
      ripple(e.clientX - rect.left, e.clientY - rect.top, 0.7, 0)
    }
    const onBurst = (e: Event) => {
      const { x, y, power = 0.6, tone: t = 'light' } = (e as CustomEvent<BurstDetail>).detail
      const rect = canvas.getBoundingClientRect()
      ripple(x - rect.left, y - rect.top, power, t === 'coin' ? 1 : t === 'error' ? 2 : 0)
      if (reduce) render(0)
    }
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') stop()
      else start()
    }

    resize()
    if (reduce) bakeStill()
    else start()

    const observer = new ResizeObserver(() => {
      resize()
      if (reduce) bakeStill()
    })
    observer.observe(canvas)
    window.addEventListener('pointermove', onPointer, { passive: true })
    window.addEventListener('pointerdown', onDown, { passive: true })
    window.addEventListener('pointerup', onUp, { passive: true })
    window.addEventListener('pointercancel', onUp, { passive: true })
    document.addEventListener('pointerleave', onLeave)
    window.addEventListener('blur', onLeave)
    window.addEventListener(BURST_EVENT, onBurst)
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      stop()
      observer.disconnect()
      window.removeEventListener('pointermove', onPointer)
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
      document.removeEventListener('pointerleave', onLeave)
      window.removeEventListener('blur', onLeave)
      window.removeEventListener(BURST_EVENT, onBurst)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return <canvas ref={canvasRef} className={`pixel-field ${className}`} aria-hidden="true" />
}
