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

function makeStars(w: number, h: number): Star[] {
  const count = Math.round(Math.min(360, (w * h) / 4600))
  return Array.from({ length: count }, () => {
    const z = Math.random()
    return {
      x: Math.random() * w,
      y: Math.random() * h,
      z,
      r: 0.35 + z * z * 1.6,
      tw: 0.8 + Math.random() * 3,
      ph: Math.random() * Math.PI * 2,
    }
  })
}

const wrap = (v: number, max: number) => ((v % max) + max) % max

/**
 * Небо профиля разработчика: чёрно-белые звёзды в три слоя глубины
 * плывут и мерцают, при прокрутке и движении мыши слои расходятся
 * (параллакс), проходят метеоры. Под звёздами — туманности, спиральная
 * галактика и чёрная дыра на CSS. Рисуется в body, чтобы transform
 * анимаций страницы не ломал position: fixed.
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
    let nextMeteor = 1200
    let raf = 0
    let last = performance.now()
    // параллакс: цель от мыши и прокрутки, текущее значение догоняет её плавно
    const aim = { x: 0, y: 0 }
    const cam = { x: 0, y: 0 }

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
      cam.x += (aim.x - cam.x) * Math.min(1, dt * 0.004)
      cam.y += (aim.y - cam.y) * Math.min(1, dt * 0.004)
      const scroll = window.scrollY

      for (const s of stars) {
        if (!still) {
          s.y -= dt * 0.006 * (0.2 + s.z)
          s.x += dt * 0.002 * (0.2 + s.z)
        }
        // ближние звёзды (z→1) уходят при прокрутке и за мышью сильнее дальних
        const depth = 0.15 + s.z * 0.85
        const x = wrap(s.x - cam.x * depth * 26, w)
        const y = wrap(s.y - scroll * depth * 0.22 - cam.y * depth * 18, h)
        const twinkle = still ? 0.8 : 0.5 + 0.5 * Math.sin(now / 1000 * s.tw + s.ph)
        const alpha = (0.22 + s.z * 0.78) * twinkle
        ctx.fillStyle = `rgba(255,255,255,${alpha})`
        ctx.beginPath()
        ctx.arc(x, y, s.r, 0, Math.PI * 2)
        ctx.fill()
        if (s.r > 1.35 && twinkle > 0.88) {
          // крупные звёзды вспыхивают крестиком
          ctx.strokeStyle = `rgba(255,255,255,${alpha * 0.55})`
          ctx.lineWidth = 0.6
          ctx.beginPath()
          ctx.moveTo(x - s.r * 4.5, y)
          ctx.lineTo(x + s.r * 4.5, y)
          ctx.moveTo(x, y - s.r * 4.5)
          ctx.lineTo(x, y + s.r * 4.5)
          ctx.stroke()
        }
      }

      if (still) return
      nextMeteor -= dt
      if (!meteor && nextMeteor <= 0) {
        const fromLeft = Math.random() < 0.5
        meteor = {
          x: fromLeft ? Math.random() * w * 0.5 : w * 0.5 + Math.random() * w * 0.5,
          y: Math.random() * h * 0.45,
          vx: (fromLeft ? 1 : -1) * (0.6 + Math.random() * 0.35),
          vy: 0.26 + Math.random() * 0.18,
          life: 1,
        }
        nextMeteor = 2600 + Math.random() * 4200
      }
      if (meteor) {
        meteor.x += meteor.vx * dt
        meteor.y += meteor.vy * dt
        meteor.life -= dt / 1200
        const len = 140
        const fade = Math.max(0, meteor.life)
        const g = ctx.createLinearGradient(meteor.x, meteor.y, meteor.x - meteor.vx * len, meteor.y - meteor.vy * len)
        g.addColorStop(0, `rgba(255,255,255,${0.95 * fade})`)
        g.addColorStop(1, 'rgba(255,255,255,0)')
        ctx.strokeStyle = g
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(meteor.x, meteor.y)
        ctx.lineTo(meteor.x - meteor.vx * len, meteor.y - meteor.vy * len)
        ctx.stroke()
        ctx.fillStyle = `rgba(255,255,255,${fade})`
        ctx.beginPath()
        ctx.arc(meteor.x, meteor.y, 1.6, 0, Math.PI * 2)
        ctx.fill()
        if (meteor.life <= 0) meteor = null
      }
    }

    const loop = (now: number) => {
      draw(now)
      raf = requestAnimationFrame(loop)
    }

    const onPointer = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse') return
      aim.x = e.clientX / w - 0.5
      aim.y = e.clientY / h - 0.5
    }

    resize()
    window.addEventListener('resize', resize)
    if (still) draw(performance.now())
    else {
      window.addEventListener('pointermove', onPointer, { passive: true })
      raf = requestAnimationFrame(loop)
    }

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
      window.removeEventListener('pointermove', onPointer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return createPortal(
    <div className="cosmos-sky" aria-hidden="true">
      <span className="cosmos-sky__nebula cosmos-sky__nebula--a" />
      <span className="cosmos-sky__nebula cosmos-sky__nebula--b" />
      <span className="cosmos-sky__galaxy" />
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
