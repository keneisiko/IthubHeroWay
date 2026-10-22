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

const WARP_MS = 1100
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3)

function makeStars(w: number, h: number): Star[] {
  const count = Math.round(Math.min(320, (w * h) / 5200))
  return Array.from({ length: count }, () => {
    const z = Math.random()
    return {
      x: Math.random() * w,
      y: Math.random() * h,
      z,
      r: 0.35 + z * z * 1.5,
      tw: 0.6 + Math.random() * 2.2,
      ph: Math.random() * Math.PI * 2,
    }
  })
}

/**
 * Небо профиля разработчика: чёрно-белые звёзды в три слоя глубины
 * медленно плывут и мерцают, изредка проходит метеор, в углу — чёрная
 * дыра. При открытии профиля звёзды выходят из гиперпрыжка из центра.
 * Рисуется в body, чтобы transform анимаций страницы не ломал fixed.
 */
export default function CosmosSky() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let w = 0
    let h = 0
    let stars: Star[] = []
    let meteor: Meteor | null = null
    let nextMeteor = 2500
    let raf = 0
    let last = performance.now()
    const born = last

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = window.innerWidth
      h = window.innerHeight
      if (w === 0 || h === 0) return
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      stars = makeStars(w, h)
    }

    const draw = (now: number) => {
      const dt = Math.min(now - last, 50)
      last = now
      if (w === 0 || h === 0) return
      ctx.clearRect(0, 0, w, h)
      const warp = still ? 1 : Math.min(1, (now - born) / WARP_MS)
      const k = easeOut(warp)
      const cx = w / 2
      const cy = h * 0.42

      for (const s of stars) {
        if (!still) {
          s.y -= dt * 0.004 * (0.2 + s.z)
          if (s.y < -2) { s.y = h + 2; s.x = Math.random() * w }
        }
        const twinkle = still ? 0.8 : 0.55 + 0.45 * Math.sin(now / 1000 * s.tw + s.ph)
        const alpha = (0.25 + s.z * 0.75) * twinkle
        if (warp < 1) {
          // гиперпрыжок: звезда летит из центра и тянет за собой след
          const x = cx + (s.x - cx) * k
          const y = cy + (s.y - cy) * k
          const tail = 1 - (1 - warp) * 0.35
          const x0 = cx + (s.x - cx) * k * tail
          const y0 = cy + (s.y - cy) * k * tail
          ctx.strokeStyle = `rgba(255,255,255,${alpha})`
          ctx.lineWidth = s.r * 1.4
          ctx.beginPath()
          ctx.moveTo(x0, y0)
          ctx.lineTo(x, y)
          ctx.stroke()
          continue
        }
        ctx.fillStyle = `rgba(255,255,255,${alpha})`
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fill()
        if (s.r > 1.4 && twinkle > 0.9) {
          // крупные звёзды вспыхивают крестиком
          ctx.strokeStyle = `rgba(255,255,255,${alpha * 0.5})`
          ctx.lineWidth = 0.6
          ctx.beginPath()
          ctx.moveTo(s.x - s.r * 4, s.y)
          ctx.lineTo(s.x + s.r * 4, s.y)
          ctx.moveTo(s.x, s.y - s.r * 4)
          ctx.lineTo(s.x, s.y + s.r * 4)
          ctx.stroke()
        }
      }

      if (still || warp < 1) return
      nextMeteor -= dt
      if (!meteor && nextMeteor <= 0) {
        const fromLeft = Math.random() < 0.5
        meteor = {
          x: fromLeft ? Math.random() * w * 0.5 : w * 0.5 + Math.random() * w * 0.5,
          y: Math.random() * h * 0.35,
          vx: (fromLeft ? 1 : -1) * (0.55 + Math.random() * 0.3),
          vy: 0.28 + Math.random() * 0.15,
          life: 1,
        }
        nextMeteor = 5000 + Math.random() * 7000
      }
      if (meteor) {
        meteor.x += meteor.vx * dt
        meteor.y += meteor.vy * dt
        meteor.life -= dt / 1300
        const len = 120
        const g = ctx.createLinearGradient(meteor.x, meteor.y, meteor.x - meteor.vx * len, meteor.y - meteor.vy * len)
        g.addColorStop(0, `rgba(255,255,255,${0.9 * Math.max(0, meteor.life)})`)
        g.addColorStop(1, 'rgba(255,255,255,0)')
        ctx.strokeStyle = g
        ctx.lineWidth = 1.4
        ctx.beginPath()
        ctx.moveTo(meteor.x, meteor.y)
        ctx.lineTo(meteor.x - meteor.vx * len, meteor.y - meteor.vy * len)
        ctx.stroke()
        if (meteor.life <= 0) meteor = null
      }
    }

    const loop = (now: number) => {
      draw(now)
      raf = requestAnimationFrame(loop)
    }

    resize()
    window.addEventListener('resize', resize)
    if (still) draw(performance.now())
    else raf = requestAnimationFrame(loop)

    const onVisibility = () => {
      cancelAnimationFrame(raf)
      if (!document.hidden && !still) {
        last = performance.now()
        raf = requestAnimationFrame(loop)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return createPortal(
    <div className="cosmos-sky" aria-hidden="true">
      <canvas ref={canvasRef} className="cosmos-sky__stars" />
      <span className="cosmos-sky__hole">
        <span className="cosmos-sky__disk" />
        <span className="cosmos-sky__core" />
        <span className="cosmos-sky__disk cosmos-sky__disk--front" />
      </span>
      <span className="cosmos-sky__vignette" />
    </div>,
    document.body,
  )
}
