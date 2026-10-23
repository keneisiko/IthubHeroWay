import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { DOT, LONG, PLUS, RING, CROSS, THICK, TONES, paintShape as paint, type Cell } from '../lib/pixelStars'

interface Star {
  x: number
  y: number
  z: number
  u: number
  shape: Cell[]
  tone: number
  tw: number
  ph: number
  born: number
}

// пылинка или волосок на плёнке: всплывает, медленно плывёт и гаснет
interface Mote {
  sprite: HTMLCanvasElement
  x: number
  y: number
  vx: number
  vy: number
  rot: number
  vr: number
  t: number
  life: number
  alpha: number
}

interface Spark {
  x: number
  y: number
  life: number
  big: boolean
}

interface Bloom {
  x: number
  y: number
  t: number
}

interface Scene {
  w: number
  h: number
  stars: Star[]
  motes: Mote[]
}

// звёзды как на референсе: больше точек и крестиков, реже ромбы
const SHAPE_BAG: Cell[][] = [DOT, DOT, DOT, DOT, PLUS, PLUS, RING, RING, CROSS, LONG]
// вспышка: звезда раскрывается из точки в большой крест и обратно
const BLOOM: Cell[][] = [DOT, PLUS, LONG, THICK, THICK, LONG, PLUS, DOT]
const BLOOM_MS = 1500
const INTRO_MS = 1200

const rand = (a: number, b: number) => a + Math.random() * (b - a)
const pick = <T,>(list: T[]) => list[Math.floor(Math.random() * list.length)]
const wrap = (v: number, max: number) => ((v % max) + max) % max

function sprite(size: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement('canvas')
  c.width = size
  c.height = size
  return [c, c.getContext('2d')!]
}

function speck(): HTMLCanvasElement {
  const r = rand(1.2, 3.2)
  const size = Math.ceil(r * 2 + 4)
  const [c, g] = sprite(size)
  const n = 5 + Math.floor(Math.random() * 3)
  g.fillStyle = '#dcdcdc'
  g.beginPath()
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2
    const k = r * rand(0.5, 1)
    const px = size / 2 + Math.cos(a) * k
    const py = size / 2 + Math.sin(a) * k
    if (i === 0) g.moveTo(px, py)
    else g.lineTo(px, py)
  }
  g.closePath()
  g.fill()
  return c
}

function hair(): HTMLCanvasElement {
  const len = rand(18, 52)
  const size = Math.ceil(len + 8)
  const [c, g] = sprite(size)
  const a = rand(0, Math.PI)
  const hx = Math.cos(a) * len / 2
  const hy = Math.sin(a) * len / 2
  const m = size / 2
  g.strokeStyle = 'rgba(225, 225, 225, 0.9)'
  g.lineWidth = 0.8
  g.lineCap = 'round'
  g.beginPath()
  g.moveTo(m - hx, m - hy)
  g.bezierCurveTo(m - hx * 0.3 + rand(-10, 10), m - hy * 0.3 + rand(-10, 10), m + hx * 0.3 + rand(-10, 10), m + hy * 0.3 + rand(-10, 10), m + hx, m + hy)
  g.stroke()
  return c
}

let noiseUrl = ''

// зерно плёнки: плитка шума рисуется один раз за сессию
function noise(): string {
  if (noiseUrl) return noiseUrl
  const size = 140
  const [c, g] = sprite(size)
  const img = g.createImageData(size, size)
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.random()
    img.data[i] = img.data[i + 1] = img.data[i + 2] = 255
    img.data[i + 3] = v > 0.985 ? 52 : Math.round(Math.random() * 18)
  }
  g.putImageData(img, 0, 0)
  noiseUrl = `url(${c.toDataURL('image/png')})`
  return noiseUrl
}

function spawnMote(w: number, h: number, fresh: boolean): Mote {
  const isHair = Math.random() < 0.35
  const life = rand(9000, 16000)
  return {
    sprite: isHair ? hair() : speck(),
    x: rand(0, w),
    y: rand(0, h),
    vx: rand(-0.006, 0.006),
    vy: rand(-0.008, -0.002),
    rot: rand(0, Math.PI * 2),
    vr: rand(-0.00008, 0.00008),
    t: fresh ? rand(0, life) : 0,
    life,
    alpha: isHair ? rand(0.25, 0.45) : rand(0.35, 0.7),
  }
}

function build(): Scene {
  const w = window.innerWidth
  const h = window.innerHeight
  const mobile = w < 768
  const count = Math.round((w * h) / (mobile ? 5200 : 6400))
  const stars: Star[] = []
  for (let i = 0; i < count; i++) {
    const z = Math.random() ** 1.6
    stars.push({
      x: rand(0, w),
      y: rand(0, h),
      z,
      u: z > 0.75 ? 3 : 2,
      shape: pick(SHAPE_BAG),
      tone: z > 0.6 ? 3 : z > 0.25 ? 2 : 1,
      tw: rand(0.25, 0.9),
      ph: rand(0, Math.PI * 2),
      born: rand(0, INTRO_MS * 0.85) * (1 - z * 0.4),
    })
  }
  const motes: Mote[] = []
  for (let i = 0; i < (mobile ? 9 : 18); i++) motes.push(spawnMote(w, h, true))
  return { w, h, stars, motes }
}

/**
 * Фон личной темы «Плёнка»: чёрный кадр с зерном, по нему медленно плывут
 * пиксельные звёзды, пылинки и волоски, как на отсканированной плёнке.
 * Звёзды мерцают ступенями по палитре, изредка одна раскрывается в большой
 * крест, за мышью остаются гаснущие пиксели. На входе звёзды проявляются
 * россыпью.
 */
export default function FilmSky() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const el = canvasRef.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return
    const root = document.documentElement
    root.style.setProperty('--film-noise', noise())
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const coarse = window.matchMedia('(pointer: coarse)').matches
    const frameMs = coarse ? 1000 / 31 : 0
    let s = build()
    let raf = 0
    let last = performance.now()
    let lastDraw = 0
    const born = last
    const sparks: Spark[] = []
    const cursor = { x: -1, y: -1, px: -1, py: -1 }
    let bloom: Bloom | null = null
    let nextBloom = INTRO_MS + rand(1200, 2600)
    let scratch = { x: 0, until: 0 }
    let nextScratch = rand(4000, 8000)

    const fit = () => {
      el.width = s.w
      el.height = s.h
    }

    const draw = (now: number) => {
      const dt = Math.min(now - last, 50)
      last = now
      const age = still ? Infinity : now - born
      const { w, h } = s
      ctx.clearRect(0, 0, w, h)

      for (const st of s.stars) {
        if (age < st.born) continue
        if (!still) {
          st.x = wrap(st.x + dt * 0.0016 * (0.3 + st.z), w)
          st.y = wrap(st.y - dt * 0.0036 * (0.3 + st.z), h)
        }
        // первые мгновения после проявления звезда вспыхивает крестом
        if (age - st.born < 160) {
          ctx.fillStyle = TONES[3]
          paint(ctx, st.x, st.y, st.u, PLUS)
          continue
        }
        const lvl = still ? 0.6 : 0.5 + 0.5 * Math.sin(now * 0.001 * st.tw + st.ph)
        const tone = Math.max(0, Math.min(3, st.tone - 1 + Math.round(lvl * 1.6)))
        ctx.fillStyle = TONES[tone]
        const shape = st.shape === DOT && st.z > 0.55 && lvl > 0.85 ? PLUS : st.shape
        paint(ctx, st.x, st.y, st.u, shape)
      }

      for (let i = 0; i < s.motes.length; i++) {
        const m = s.motes[i]
        if (!still) {
          m.t += dt
          m.x += m.vx * dt
          m.y += m.vy * dt
          m.rot += m.vr * dt
          if (m.t >= m.life) {
            s.motes[i] = spawnMote(w, h, false)
            continue
          }
        }
        const fade = Math.sin((m.t / m.life) * Math.PI)
        ctx.globalAlpha = m.alpha * fade * Math.min(1, age / INTRO_MS)
        const sz = m.sprite.width
        ctx.save()
        ctx.translate(m.x, m.y)
        ctx.rotate(m.rot)
        ctx.drawImage(m.sprite, -sz / 2, -sz / 2)
        ctx.restore()
      }
      ctx.globalAlpha = 1

      if (still) return

      nextBloom -= dt
      if (!bloom && nextBloom <= 0) {
        bloom = { x: rand(w * 0.05, w * 0.95), y: rand(h * 0.08, h * 0.92), t: 0 }
        nextBloom = rand(2800, 5600)
      }
      if (bloom) {
        bloom.t += dt
        const k = Math.min(BLOOM.length - 1, Math.floor((bloom.t / BLOOM_MS) * BLOOM.length))
        ctx.fillStyle = k === 0 || k === BLOOM.length - 1 ? TONES[2] : TONES[3]
        paint(ctx, bloom.x, bloom.y, 2, BLOOM[k])
        if (bloom.t >= BLOOM_MS) bloom = null
      }

      // царапина на плёнке: тонкая вертикальная черта на долю секунды
      nextScratch -= dt
      if (nextScratch <= 0) {
        scratch = { x: rand(w * 0.1, w * 0.9), until: now + rand(90, 170) }
        nextScratch = rand(5000, 11000)
      }
      if (now < scratch.until) {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.07)'
        ctx.fillRect(Math.round(scratch.x + rand(-1, 1)), 0, 1, h)
      }

      drawSparks(dt)
    }

    function drawSparks(dt: number) {
      if (cursor.x >= 0 && cursor.px >= 0) {
        const moved = Math.hypot(cursor.x - cursor.px, cursor.y - cursor.py)
        const spawn = Math.min(2, Math.floor(moved / 16))
        for (let i = 0; i < spawn && sparks.length < 40; i++) {
          sparks.push({ x: cursor.x + rand(-6, 6), y: cursor.y + rand(-6, 6), life: 1, big: Math.random() < 0.3 })
        }
        cursor.px = cursor.x
        cursor.py = cursor.y
      }
      for (let i = sparks.length - 1; i >= 0; i--) {
        const p = sparks[i]
        p.life -= dt / 900
        p.y -= dt * 0.012
        if (p.life <= 0) {
          sparks.splice(i, 1)
          continue
        }
        // гаснет ступенями по палитре: белый, серебро, графит, уголь
        ctx!.fillStyle = TONES[Math.min(3, Math.floor(p.life * 4))]
        paint(ctx!, p.x, p.y, 2, p.big && p.life > 0.5 ? PLUS : DOT)
      }
    }

    const onPointer = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse') return
      if (cursor.px < 0) {
        cursor.px = e.clientX
        cursor.py = e.clientY
      }
      cursor.x = e.clientX
      cursor.y = e.clientY
    }

    const loop = (now: number) => {
      raf = requestAnimationFrame(loop)
      if (frameMs && now - lastDraw < frameMs) return
      lastDraw = now
      draw(now)
    }

    const onResize = () => {
      if (window.innerWidth === s.w && Math.abs(window.innerHeight - s.h) < 120) return
      s = build()
      for (const st of s.stars) st.born = 0
      fit()
      if (still) draw(performance.now())
    }

    const onVisibility = () => {
      cancelAnimationFrame(raf)
      if (!document.hidden && !still) {
        last = performance.now()
        raf = requestAnimationFrame(loop)
      }
    }

    fit()
    window.addEventListener('resize', onResize)
    document.addEventListener('visibilitychange', onVisibility)
    if (still) draw(performance.now())
    else {
      window.addEventListener('pointermove', onPointer, { passive: true })
      raf = requestAnimationFrame(loop)
    }

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onPointer)
      window.removeEventListener('resize', onResize)
      document.removeEventListener('visibilitychange', onVisibility)
      root.style.removeProperty('--film-noise')
    }
  }, [])

  return createPortal(
    <div className="film-sky" aria-hidden="true">
      <span className="film-sky__leak film-sky__leak--a" />
      <span className="film-sky__leak film-sky__leak--b" />
      <canvas ref={canvasRef} className="film-sky__stars" />
      <span className="film-sky__grain" />
      <span className="film-sky__vignette" />
    </div>,
    document.body,
  )
}
