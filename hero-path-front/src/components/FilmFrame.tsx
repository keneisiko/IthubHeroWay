import { useEffect, useRef } from 'react'
import { CROSS, DOT, LONG, PLUS, RING, THICK, TONES, paintShape, type Cell } from '../lib/pixelStars'

interface Rect {
  x: number
  y: number
  w: number
  h: number
}

// пылинка свечения: клетка вокруг фото со своим ритмом мерцания
interface Mote {
  x: number
  y: number
  tone: number
  tw: number
  ph: number
  plus: boolean
}

interface Spark {
  x: number
  y: number
  t: number
  life: number
  big: boolean
}

// поле вокруг фото в клетках, частота кадров пиксельной анимации
const MARGIN = 6
const FPS = 12
// звёзды по углам по часовой стрелке от левого верхнего: в покое и когда горят
const CORNERS: [Cell[], Cell[]][] = [
  [DOT, CROSS],
  [LONG, THICK],
  [DOT, PLUS],
  [RING, LONG],
]
const SPARK_STEPS: Cell[][] = [DOT, PLUS, LONG, PLUS, DOT]
const SPARK_TONES = [1, 2, 3, 2, 1]

const rand = (a: number, b: number) => a + Math.random() * (b - a)
const clamp01 = (v: number) => Math.max(0, Math.min(1, v))
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3)

// контур вокруг фото по часовой стрелке; углы срезаны ступенькой
function outline(o: number, s: number, u: number): Rect[] {
  const n = Math.max(1, Math.round(s / u))
  const at = (i: number) => o + Math.round((i * s) / n)
  const cells: Rect[] = []
  for (let i = 0; i < n; i++) cells.push({ x: at(i), y: o - u, w: at(i + 1) - at(i), h: u })
  cells.push({ x: o + s - u, y: o, w: u, h: u })
  for (let i = 0; i < n; i++) cells.push({ x: o + s, y: at(i), w: u, h: at(i + 1) - at(i) })
  cells.push({ x: o + s - u, y: o + s - u, w: u, h: u })
  for (let i = n - 1; i >= 0; i--) cells.push({ x: at(i), y: o + s, w: at(i + 1) - at(i), h: u })
  cells.push({ x: o, y: o + s - u, w: u, h: u })
  for (let i = n - 1; i >= 0; i--) cells.push({ x: o - u, y: at(i), w: u, h: at(i + 1) - at(i) })
  cells.push({ x: o, y: o, w: u, h: u })
  return cells
}

/**
 * Рамка аватара в теме «Плёнка» — пиксельная, как звёзды на фоне. Фото
 * обведено серебряным контуром со ступенчатыми углами, вокруг дышит
 * свечение из точек (дизеринг по палитре). По углам — пиксельные звёзды,
 * по кругу по очереди вспыхивает одна; по контуру бежит светлая звёздочка,
 * вокруг то тут, то там раскрываются искры. При появлении контур
 * прорисовывается клетка за клеткой.
 */
export default function FilmFrame() {
  const ref = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const el = ref.current
    const host = el?.parentElement
    const ctx = el?.getContext('2d')
    if (!el || !host || !ctx) return
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    const u = Math.max(2, Math.round(3 * dpr))
    const o = MARGIN * u
    let s = 0
    let w = 0
    let cells: Rect[] = []
    let motes: Mote[] = []
    const sparks: Spark[] = []
    let timer = 0
    let nextSpark = 0
    const born = performance.now() + (still ? -10000 : 350)

    const fit = () => {
      s = Math.round(host.offsetWidth * dpr)
      w = s + o * 2
      el.width = w
      el.height = w
      el.style.width = el.style.height = `${w / dpr}px`
      el.style.left = el.style.top = `${-o / dpr}px`
      host.style.setProperty('--film-px', `${u / dpr}px`)
      cells = outline(o, s, u)
      // звёздная пыль вокруг фото: у контура гуще и ярче, к краю редеет
      motes = []
      const cols = Math.floor(w / u)
      for (let j = 0; j < cols; j++) {
        for (let i = 0; i < cols; i++) {
          const cx = i * u + u / 2
          const cy = j * u + u / 2
          const dx = Math.max(o - cx, 0, cx - o - s)
          const dy = Math.max(o - cy, 0, cy - o - s)
          const d = Math.hypot(dx, dy) / u
          if (d < 2.2 || d > MARGIN) continue
          const near = 1 - (d - 2) / (MARGIN - 2)
          if (Math.random() > 0.34 * Math.pow(near, 1.6)) continue
          motes.push({ x: i * u, y: j * u, tone: near > 0.6 ? 2 : near > 0.3 ? 1 : 0, tw: rand(0.6, 1.8), ph: rand(0, Math.PI * 2), plus: d > 3.2 && Math.random() < 0.14 })
        }
      }
    }

    // точка на поле вокруг фото, не ближе трёх клеток к контуру
    const spot = () => {
      for (let i = 0; i < 12; i++) {
        const x = rand(0, w)
        const y = rand(0, w)
        const dx = Math.max(o - x, 0, x - o - s)
        const dy = Math.max(o - y, 0, y - o - s)
        const d = Math.hypot(dx, dy) / u
        if (d > 3 && d < MARGIN - 1) return { x, y }
      }
      return { x: o - 3 * u, y: o + s / 2 }
    }

    const draw = (now: number) => {
      const age = now - born
      const reveal = easeOut(clamp01(age / 700))
      const glow = clamp01((age - 350) / 800)
      ctx.clearRect(0, 0, w, w)

      // пыль мерцает ступенями по палитре и проявляется после контура
      for (const m of motes) {
        if (Math.random() > glow) continue
        const lvl = still ? 0.6 : 0.5 + 0.5 * Math.sin((now / 1000) * m.tw + m.ph)
        const tone = Math.round(m.tone - 1 + lvl * 1.6)
        if (tone < 0) continue
        ctx.fillStyle = TONES[Math.min(3, tone)]
        if (m.plus && lvl > 0.75) paintShape(ctx, m.x + u / 2, m.y + u / 2, u, PLUS)
        else ctx.fillRect(m.x, m.y, u, u)
      }

      // контур прорисовывается по часовой стрелке от левого верхнего угла
      const shown = Math.round(cells.length * reveal)
      ctx.fillStyle = TONES[2]
      for (let i = 0; i < shown; i++) {
        const c = cells[i]
        ctx.fillRect(c.x, c.y, c.w, c.h)
      }

      if (reveal < 1) {
        const head = cells[Math.max(0, shown - 1)]
        ctx.fillStyle = TONES[3]
        paintShape(ctx, head.x + head.w / 2, head.y + head.h / 2, u, PLUS)
        return
      }

      // бегущая звёздочка: белая голова с крестом и короткий хвост
      if (!still) {
        const n = cells.length
        const at = Math.floor(now / 85) % n
        ctx.fillStyle = TONES[3]
        for (let t = 0; t < 4; t++) {
          const c = cells[(at - t + n) % n]
          ctx.fillRect(c.x, c.y, c.w, c.h)
        }
        const c = cells[at]
        paintShape(ctx, c.x + c.w / 2, c.y + c.h / 2, u, PLUS)
      }

      // звёзды по углам: по кругу загорается одна
      const lit = still ? 1 : Math.floor(now / 900) % 4
      const pop = age < 1500
      const near = o - 3 * u
      const far = o + s + 3 * u
      const spots = [[near, near], [far, near], [far, far], [near, far]]
      spots.forEach(([x, y], i) => {
        const on = pop || i === lit
        // вокруг звезды расчищаем пыль, чтобы она читалась
        ctx.clearRect(Math.round(x - 3.5 * u), Math.round(y - 3.5 * u), 7 * u, 7 * u)
        ctx.fillStyle = on || i === 1 ? TONES[3] : TONES[2]
        paintShape(ctx, x, y, u, CORNERS[i][on ? 1 : 0])
      })

      if (still) return
      nextSpark -= 1000 / FPS
      if (nextSpark <= 0 && sparks.length < 4) {
        const p = spot()
        sparks.push({ ...p, t: 0, life: rand(900, 1600), big: Math.random() < 0.4 })
        nextSpark = rand(250, 700)
      }
      for (let i = sparks.length - 1; i >= 0; i--) {
        const p = sparks[i]
        p.t += 1000 / FPS
        if (p.t >= p.life) {
          sparks.splice(i, 1)
          continue
        }
        let step = Math.min(4, Math.floor((p.t / p.life) * 5))
        if (!p.big && step === 2) step = 1
        ctx.fillStyle = TONES[SPARK_TONES[step]]
        paintShape(ctx, p.x, p.y, u, SPARK_STEPS[step])
      }
    }

    const tick = () => draw(performance.now())
    const start = () => {
      window.clearInterval(timer)
      if (!still && !document.hidden) timer = window.setInterval(tick, 1000 / FPS)
      tick()
    }

    const ro = new ResizeObserver(() => {
      fit()
      tick()
    })
    fit()
    ro.observe(host)
    document.addEventListener('visibilitychange', start)
    start()

    return () => {
      window.clearInterval(timer)
      ro.disconnect()
      document.removeEventListener('visibilitychange', start)
      host.style.removeProperty('--film-px')
    }
  }, [])

  return <canvas ref={ref} className="film-frame" aria-hidden="true" />
}

