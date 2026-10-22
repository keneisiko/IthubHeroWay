import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

interface Star {
  x: number
  y: number
  z: number
  r: number
  tw: number
  ph: number
}

interface Meteor {
  x: number
  y: number
  vx: number
  vy: number
  life: number
}

interface Scene {
  w: number
  h: number
  dpr: number
  stars: Star[]
  nebula: HTMLCanvasElement
  galaxy: HTMLCanvasElement
  glow: HTMLCanvasElement
  halo: HTMLCanvasElement
  disk: HTMLCanvasElement
  lens: HTMLCanvasElement
  R: number
  inner: number
  outer: number
  home: { x: number; y: number }
}

const INTRO_MS = 2600
const DISK_TILT = 0.15
const TAU = Math.PI * 2

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)
const easeOut = (t: number) => 1 - Math.pow(1 - t, 4)
const wrap = (v: number, max: number) => ((v % max) + max) % max
const rand = (a: number, b: number) => a + Math.random() * (b - a)

function canvas(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement('canvas')
  c.width = Math.max(1, Math.ceil(w))
  c.height = Math.max(1, Math.ceil(h))
  return [c, c.getContext('2d')!]
}

// Туманность рисуется один раз в половинном разрешении: при растяжении
// облака сами становятся мягкими, а кадр стоит одну drawImage.
function paintNebula(w: number, h: number): HTMLCanvasElement {
  const [c, g] = canvas(w, h)
  const cloud = (cx: number, cy: number, spread: number, size: number, alpha: number, n: number, mode: GlobalCompositeOperation) => {
    g.globalCompositeOperation = mode
    for (let i = 0; i < n; i++) {
      const a = Math.random() * TAU
      const d = Math.pow(Math.random(), 0.7) * spread
      const x = cx + Math.cos(a) * d
      const y = cy + Math.sin(a) * d * 0.6
      const r = size * rand(0.35, 1)
      const grad = g.createRadialGradient(x, y, 0, x, y, r)
      grad.addColorStop(0, `rgba(255,255,255,${alpha * rand(0.5, 1)})`)
      grad.addColorStop(1, 'rgba(255,255,255,0)')
      g.fillStyle = grad
      g.fillRect(x - r, y - r, r * 2, r * 2)
    }
  }
  const s = Math.max(w, h)
  // звёздный рукав по диагонали: облака, прожилки пыли и россыпь пылинок
  for (let i = 0; i < 9; i++) {
    const t = i / 8
    cloud(w * (-0.05 + t * 1.1), h * (0.95 - t * 0.85), s * 0.12, s * 0.1, 0.05, 14, 'lighter')
  }
  cloud(w * 0.18, h * 0.2, s * 0.14, s * 0.12, 0.045, 22, 'lighter')
  cloud(w * 0.85, h * 0.75, s * 0.12, s * 0.1, 0.04, 18, 'lighter')
  for (let i = 0; i < 12; i++) {
    const t = i / 11
    cloud(w * (0.02 + t * 1.0), h * (0.9 - t * 0.82) + rand(-1, 1) * s * 0.02, s * 0.05, s * 0.035, 0.22, 8, 'destination-out')
  }
  g.globalCompositeOperation = 'lighter'
  for (let i = 0; i < 1400; i++) {
    const t = Math.random()
    const off = (Math.random() + Math.random() + Math.random() - 1.5) * s * 0.09
    const x = w * (-0.05 + t * 1.1) + off * 0.6
    const y = h * (0.95 - t * 0.85) + off
    g.fillStyle = `rgba(255,255,255,${rand(0.08, 0.5)})`
    g.fillRect(x, y, 1, 1)
  }
  g.globalCompositeOperation = 'source-over'
  return c
}

function paintGalaxy(size: number): HTMLCanvasElement {
  const [c, g] = canvas(size, size)
  const m = size / 2
  const core = g.createRadialGradient(m, m, 0, m, m, m * 0.35)
  core.addColorStop(0, 'rgba(255,255,255,0.9)')
  core.addColorStop(0.3, 'rgba(255,255,255,0.25)')
  core.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = core
  g.fillRect(0, 0, size, size)
  for (let i = 0; i < 2600; i++) {
    const arm = i % 2
    const t = Math.pow(Math.random(), 0.8)
    const a = t * 5.2 + arm * Math.PI + rand(-0.35, 0.35) * (1 - t * 0.5)
    const r = t * m * 0.95
    g.fillStyle = `rgba(255,255,255,${(1 - t) * rand(0.15, 0.6)})`
    g.fillRect(m + Math.cos(a) * r, m + Math.sin(a) * r, 1.2, 1.2)
  }
  return c
}

function paintGlow(size: number, stops: [number, number][]): HTMLCanvasElement {
  const [c, g] = canvas(size, size)
  const m = size / 2
  const grad = g.createRadialGradient(m, m, 0, m, m, m)
  for (const [at, a] of stops) grad.addColorStop(at, `rgba(255,255,255,${a})`)
  g.fillStyle = grad
  g.fillRect(0, 0, size, size)
  return c
}

// Диск аккреции «плоско сверху»: сотни колец с рваными штрихами и яркий
// внутренний край. На экран он ложится сжатым по вертикали и повёрнутым,
// поэтому кажется, что газ закручивается вокруг дыры. Рисуется один раз
// в повышенном разрешении q — на входе камера подлетает к нему вплотную.
function paintDisk(inner: number, outer: number, q: number): HTMLCanvasElement {
  const [c, g] = canvas(outer * 2 * q, outer * 2 * q)
  g.scale(q, q)
  const m = outer
  g.lineCap = 'round'
  for (let k = 0; k < 240; k++) {
    const t = Math.pow(k / 239, 1.35)
    const r = inner + (outer - inner) * t
    const fall = Math.pow(1 - t, 1.8)
    g.lineWidth = rand(0.7, 2)
    g.setLineDash([rand(8, 80), rand(4, 36)])
    g.lineDashOffset = rand(0, 100)
    g.strokeStyle = `rgba(255,255,255,${(0.03 + fall * 0.6 + (t < 0.05 ? 0.4 : 0)) * rand(0.45, 1)})`
    g.beginPath()
    g.arc(m, m, r, 0, TAU)
    g.stroke()
  }
  g.setLineDash([])
  const hot = g.createRadialGradient(m, m, inner * 0.9, m, m, outer)
  hot.addColorStop(0, 'rgba(255,255,255,0.4)')
  hot.addColorStop(0.22, 'rgba(255,255,255,0.08)')
  hot.addColorStop(1, 'rgba(255,255,255,0)')
  g.globalCompositeOperation = 'lighter'
  g.fillStyle = hot
  g.beginPath()
  g.arc(m, m, outer, 0, TAU)
  g.arc(m, m, inner * 0.95, 0, TAU, true)
  g.fill()
  return c
}

// Дальняя сторона диска, изогнутая гравитацией в дугу над тенью и
// тонкую под ней, плюс фотонное кольцо у самого горизонта.
function paintLens(R: number, q: number): HTMLCanvasElement {
  const [c, g] = canvas(R * 4 * q, R * 4 * q)
  g.scale(q, q)
  const m = R * 2
  for (let k = 0; k < 60; k++) {
    const t = k / 59
    const r = R * (1.05 + t * 0.4)
    const fall = Math.pow(1 - t, 2.8)
    const v = g.createLinearGradient(0, m - r, 0, m + r)
    v.addColorStop(0, `rgba(255,255,255,${fall * 0.9})`)
    v.addColorStop(0.5, `rgba(255,255,255,${fall * 0.2})`)
    v.addColorStop(1, `rgba(255,255,255,${fall * 0.5})`)
    g.strokeStyle = v
    g.lineWidth = rand(0.6, 1.4)
    g.setLineDash([rand(10, 60), rand(2, 16)])
    g.lineDashOffset = rand(0, 80)
    g.beginPath()
    g.arc(m, m, r, 0, TAU)
    g.stroke()
  }
  g.setLineDash([])
  g.shadowColor = '#fff'
  g.shadowBlur = R * 0.12
  g.strokeStyle = 'rgba(255,255,255,0.95)'
  g.lineWidth = Math.max(1.2, R * 0.022)
  g.beginPath()
  g.arc(m, m, R * 1.025, 0, TAU)
  g.stroke()
  return c
}

function build(dprCap: number): Scene {
  const w = window.innerWidth
  const h = window.innerHeight
  const dpr = Math.min(window.devicePixelRatio || 1, dprCap)
  const q = Math.min(3, dpr * 1.6)
  const mobile = w < 768
  const R = mobile ? Math.min(w, h) * 0.1 : Math.min(w, h) * 0.115
  const inner = R * 1.55
  const outer = R * 3.6
  const count = Math.round(Math.min(mobile ? 200 : 380, (w * h) / 4200))
  const stars = Array.from({ length: count }, () => {
    const z = Math.pow(Math.random(), 1.6)
    return { x: Math.random() * w, y: Math.random() * h, z, r: 0.4 + z * 1.5, tw: rand(0.6, 3.2), ph: Math.random() * TAU }
  })
  return {
    w,
    h,
    dpr,
    stars,
    nebula: paintNebula(w * 0.6, h * 0.6),
    galaxy: paintGalaxy(mobile ? 160 : 220),
    glow: paintGlow(32, [[0, 0.9], [0.2, 0.35], [1, 0]]),
    halo: paintGlow(256, [[0, 0.32], [0.25, 0.14], [0.6, 0.04], [1, 0]]),
    disk: paintDisk(inner, outer, q),
    lens: paintLens(R, q),
    R,
    inner,
    outer,
    // в покое — там, где у профиля свободно: слева под картой пути и у пятиугольника
    home: mobile ? { x: w * 0.96, y: h * 0.84 } : { x: Math.max(w * 0.15, w / 2 - 520), y: h * 0.9 },
  }
}

// Половина диска — задняя (за тенью) или передняя (поверх неё) — с
// доплеровским перекосом: сторона, летящая к нам, ярче.
function drawDiskHalf(ctx: CanvasRenderingContext2D, s: Scene, spin: number, front: boolean) {
  const { inner, outer } = s
  ctx.save()
  ctx.beginPath()
  ctx.rect(-outer, front ? 0 : -outer, outer * 2, outer)
  ctx.clip()
  ctx.save()
  ctx.scale(1, DISK_TILT)
  ctx.rotate(spin)
  ctx.drawImage(s.disk, -outer, -outer, outer * 2, outer * 2)
  ctx.restore()
  ctx.beginPath()
  ctx.ellipse(0, 0, outer, outer * DISK_TILT, 0, 0, TAU)
  ctx.ellipse(0, 0, inner * 0.95, inner * 0.95 * DISK_TILT, 0, 0, TAU, true)
  ctx.clip()
  const lit = ctx.createLinearGradient(-outer, 0, outer, 0)
  lit.addColorStop(0, 'rgba(255,255,255,0.22)')
  lit.addColorStop(0.5, 'rgba(255,255,255,0)')
  lit.addColorStop(0.5, 'rgba(0,0,0,0)')
  lit.addColorStop(1, 'rgba(0,0,0,0.55)')
  ctx.fillStyle = lit
  ctx.fillRect(-outer, -outer, outer * 2, outer * 2)
  ctx.restore()
}

function drawHole(ctx: CanvasRenderingContext2D, s: Scene, x: number, y: number, scale: number, spin: number) {
  const { R, outer } = s
  ctx.save()
  ctx.translate(x, y)
  ctx.scale(scale, scale)
  const haloR = outer * 1.5
  ctx.drawImage(s.halo, -haloR, -haloR, haloR * 2, haloR * 2)
  drawDiskHalf(ctx, s, spin, false)
  ctx.drawImage(s.lens, -R * 2, -R * 2, R * 4, R * 4)
  ctx.fillStyle = '#000'
  ctx.beginPath()
  ctx.arc(0, 0, R, 0, TAU)
  ctx.fill()
  drawDiskHalf(ctx, s, spin, true)
  ctx.restore()
}

/**
 * Небо профиля разработчика целиком на одном canvas: туманность со
 * звёздным рукавом, спиральная галактика, мерцающие звёзды с
 * параллаксом, метеоры и массивная чёрная дыра — диск аккреции,
 * линзированная дуга, фотонное кольцо. При входе камера отъезжает от
 * горизонта событий, а звёзды раскручиваются вихрем на свои места.
 */
export default function CosmosSky() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const el = canvasRef.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const coarse = window.matchMedia('(pointer: coarse)').matches
    // на телефоне меньше пикселей и 30 кадров — батарея важнее
    const dprCap = coarse ? 1.25 : 1.5
    const frameMs = coarse ? 1000 / 31 : 0
    let s = build(dprCap)
    let meteor: Meteor | null = null
    let nextMeteor = INTRO_MS + 900
    let raf = 0
    let last = performance.now()
    let lastDraw = 0
    let spin = 0
    const born = last
    const aim = { x: 0, y: 0 }
    const cam = { x: 0, y: 0 }

    const fit = () => {
      el.width = Math.round(s.w * s.dpr)
      el.height = Math.round(s.h * s.dpr)
    }

    const draw = (now: number) => {
      const dt = Math.min(now - last, 50)
      last = now
      const { w, h, dpr } = s
      const p = still ? 1 : Math.min(1, (now - born) / INTRO_MS)
      const k = easeInOut(p)
      const reveal = easeOut(Math.min(1, p * 1.4))
      cam.x += (aim.x - cam.x) * Math.min(1, dt * 0.003)
      cam.y += (aim.y - cam.y) * Math.min(1, dt * 0.003)
      const scroll = window.scrollY
      spin += dt * (0.00012 + (1 - k) * 0.0022)

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)

      // камера: на входе дыра в центре и огромная, потом уходит на место
      const holeScale = 1 + (1 - k) * 2.4
      const hx = w / 2 + (s.home.x - cam.x * 10 - w / 2) * k
      const hy = h / 2 + (s.home.y - cam.y * 8 - scroll * 0.06 - h / 2) * k

      ctx.globalAlpha = 0.95 * reveal
      const nx = -cam.x * 14 - w * 0.05
      const ny = wrap(-scroll * 0.04, h * 0.1) - cam.y * 10 - h * 0.05
      ctx.drawImage(s.nebula, nx, ny, w * 1.1, h * 1.1)

      ctx.globalAlpha = 0.75 * reveal
      const gs = s.galaxy.width
      const gx = w < 768 ? w * 0.16 : w * 0.955
      const gy = (w < 768 ? h * 0.16 : h * 0.14) - scroll * 0.03
      ctx.save()
      ctx.translate(gx - cam.x * 6, gy - cam.y * 5)
      ctx.rotate(-0.5)
      ctx.scale(1, 0.42)
      ctx.rotate(now * 0.00004)
      ctx.drawImage(s.galaxy, -gs / 2, -gs / 2)
      ctx.restore()

      // звёзды: на входе закручены вокруг дыры и раскручиваются наружу
      const swirl = (1 - k) * (1 - k) * 3.4
      const pull = 0.25 + 0.75 * k
      for (const st of s.stars) {
        if (!still) {
          st.y -= dt * 0.005 * (0.2 + st.z)
          st.x += dt * 0.0016 * (0.2 + st.z)
        }
        const depth = 0.15 + st.z * 0.85
        let x = wrap(st.x - cam.x * depth * 28, w)
        let y = wrap(st.y - scroll * depth * 0.2 - cam.y * depth * 18, h)
        if (k < 1) {
          const dx = x - hx
          const dy = y - hy
          const a = swirl * (1.4 - Math.min(1, Math.hypot(dx, dy) / Math.max(w, h)))
          const ca = Math.cos(a)
          const sa = Math.sin(a)
          x = hx + (dx * ca - dy * sa) * pull
          y = hy + (dx * sa + dy * ca) * pull
        }
        const tw = still ? 0.85 : 0.5 + 0.5 * Math.sin(now * 0.001 * st.tw + st.ph)
        const alpha = (0.2 + st.z * 0.8) * tw * reveal
        if (st.r > 1.3) {
          ctx.globalAlpha = alpha
          const gsz = st.r * 9
          ctx.drawImage(s.glow, x - gsz / 2, y - gsz / 2, gsz, gsz)
        } else {
          ctx.globalAlpha = alpha
          ctx.fillStyle = '#fff'
          ctx.fillRect(x - st.r / 2, y - st.r / 2, st.r, st.r)
        }
      }

      // чёрная дыра
      ctx.globalAlpha = 1
      drawHole(ctx, s, hx, hy, holeScale, spin)

      if (still || p < 1) return
      nextMeteor -= dt
      if (!meteor && nextMeteor <= 0) {
        const fromLeft = Math.random() < 0.5
        meteor = {
          x: fromLeft ? rand(0, w * 0.5) : rand(w * 0.5, w),
          y: rand(0, h * 0.45),
          vx: (fromLeft ? 1 : -1) * rand(0.6, 0.95),
          vy: rand(0.26, 0.44),
          life: 1,
        }
        nextMeteor = rand(2600, 6800)
      }
      if (meteor) {
        meteor.x += meteor.vx * dt
        meteor.y += meteor.vy * dt
        meteor.life -= dt / 1200
        const fade = Math.max(0, meteor.life)
        const len = 150
        const tx = meteor.x - meteor.vx * len
        const ty = meteor.y - meteor.vy * len
        const grad = ctx.createLinearGradient(meteor.x, meteor.y, tx, ty)
        grad.addColorStop(0, `rgba(255,255,255,${0.95 * fade})`)
        grad.addColorStop(1, 'rgba(255,255,255,0)')
        ctx.strokeStyle = grad
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(meteor.x, meteor.y)
        ctx.lineTo(tx, ty)
        ctx.stroke()
        ctx.globalAlpha = fade
        ctx.drawImage(s.glow, meteor.x - 7, meteor.y - 7, 14, 14)
        ctx.globalAlpha = 1
        if (meteor.life <= 0) meteor = null
      }
    }

    const loop = (now: number) => {
      raf = requestAnimationFrame(loop)
      if (frameMs && now - lastDraw < frameMs) return
      lastDraw = now
      draw(now)
    }

    const onResize = () => {
      if (window.innerWidth === s.w && Math.abs(window.innerHeight - s.h) < 120) return
      s = build(dprCap)
      fit()
      if (still) draw(performance.now())
    }

    const onPointer = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse') return
      aim.x = e.clientX / s.w - 0.5
      aim.y = e.clientY / s.h - 0.5
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
      window.removeEventListener('resize', onResize)
      window.removeEventListener('pointermove', onPointer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return createPortal(
    <div className="cosmos-sky" aria-hidden="true">
      <canvas ref={canvasRef} className="cosmos-sky__stars" />
      <span className="cosmos-sky__vignette" />
    </div>,
    document.body,
  )
}
