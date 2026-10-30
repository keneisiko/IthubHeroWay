import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import nightUrl from '../assets/halloween/night.png'
import { BAT, CROW_FLY, WITCH, drawSprite } from '../lib/pixelSprites'

// сцена нарисована в 560×315 и растягивается на экран целыми «пикселями»
const W = 560
const H = 315
const MOON = { x: 110, y: 52, r: 34 }
// огни на картинке: тыквы на кладбище и окна замка — x, y, сила
const LIGHTS: [number, number, number][] = [
  [40, 264, 1],
  [111, 270, 0.55],
  [411, 295, 0.55],
  [502, 280, 1],
  [508, 140, 0.7],
  [536, 134, 0.7],
  [477, 160, 0.4],
]
const FRAME_MS = 1000 / 24
const INTRO_FLASH = 260

interface Flyer { x: number; y: number; vx: number; ph: number; amp: number }
interface Bat { cx: number; cy: number; rx: number; ry: number; sp: number; ph: number }
interface Wisp { x: number; y: number; ph: number; sp: number; hue: string }
interface Ember { x: number; y: number; vx: number; vy: number; life: number }
interface Star { x: number; y: number; ph: number; sp: number }

const rand = (a: number, b: number) => a + Math.random() * (b - a)

function fogTexture(): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = W * 2
  c.height = 90
  const g = c.getContext('2d')!
  for (let i = 0; i < 70; i++) {
    const x = rand(0, W * 2)
    const y = rand(20, 75)
    const rx = rand(30, 90)
    const ry = rand(8, 20)
    for (const dx of [-W * 2, 0, W * 2]) {
      const grad = g.createRadialGradient(x + dx, y, 0, x + dx, y, rx)
      grad.addColorStop(0, `rgba(176, 160, 222, ${rand(0.07, 0.14)})`)
      grad.addColorStop(1, 'rgba(176, 160, 222, 0)')
      g.fillStyle = grad
      g.save()
      g.translate(x + dx, y)
      g.scale(1, ry / rx)
      g.translate(-(x + dx), -y)
      g.fillRect(x + dx - rx, y - rx, rx * 2, rx * 2)
      g.restore()
    }
  }
  return c
}

/**
 * Фон нашивки «Самый страшный»: пиксельная ночь на кладбище. Поверх
 * картинки живут огни тыкв и окон замка (мерцают, как свечи), туман
 * в долине, звёзды, летучие мыши у башен, блуждающие огоньки над
 * могилами, изредка — стая ворон, ведьма на метле на фоне луны и
 * молния. Вход — удар молнии, в его вспышке проявляется ночь.
 */
export default function SpookySky() {
  const ref = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const el = ref.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return
    el.width = W
    el.height = H
    ctx.imageSmoothingEnabled = false
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const img = new Image()
    img.src = nightUrl
    const fog = fogTexture()
    let raf = 0
    let lastDraw = 0
    let last = performance.now()
    const born = last
    let stars: Star[] = []
    const bats: Bat[] = Array.from({ length: 3 }, (_, i) => ({
      cx: 500 + i * 12,
      cy: 105 + i * 14,
      rx: rand(18, 34),
      ry: rand(8, 16),
      sp: rand(0.0007, 0.0012),
      ph: rand(0, Math.PI * 2),
    }))
    const wisps: Wisp[] = Array.from({ length: 5 }, (_, i) => ({
      x: [170, 250, 330, 380, 455][i],
      y: rand(250, 285),
      ph: rand(0, Math.PI * 2),
      sp: rand(0.0006, 0.0011),
      hue: i % 2 ? '#9cff7a' : '#7affe0',
    }))
    let crows: Flyer[] = []
    let nextCrows = still ? Infinity : 900
    let witch: { x: number; t: number } | null = null
    let nextWitch = still ? Infinity : 5500
    let flash = 0
    let nextFlash = still ? Infinity : rand(22000, 38000)
    const trail: Ember[] = []
    const embers: Ember[] = []
    const cursor = { x: -1, y: -1, px: -1, py: -1 }

    const launchCrows = (fromTree: boolean) => {
      const n = 3 + Math.floor(Math.random() * 3)
      crows = Array.from({ length: n }, (_, i) => ({
        x: fromTree ? 60 + i * 9 : W + 10 + i * rand(14, 26),
        y: fromTree ? 105 + rand(-8, 8) : rand(55, 115) + i * rand(-6, 6),
        vx: fromTree ? rand(0.05, 0.075) : -rand(0.045, 0.065),
        ph: rand(0, Math.PI * 2),
        amp: rand(2, 5),
      }))
    }

    const pickStars = () => {
      const probe = document.createElement('canvas')
      probe.width = W
      probe.height = H
      const p = probe.getContext('2d')!
      p.drawImage(img, 0, 0)
      const data = p.getImageData(0, 0, W, 140).data
      const found: Star[] = []
      for (let y = 0; y < 140; y++) {
        for (let x = 0; x < W; x++) {
          const i = (y * W + x) * 4
          const lum = data[i] + data[i + 1] + data[i + 2]
          if (lum < 520) continue
          if (Math.hypot(x - MOON.x, y - MOON.y) < MOON.r + 10) continue
          found.push({ x, y, ph: rand(0, Math.PI * 2), sp: rand(0.0015, 0.004) })
        }
      }
      stars = found.filter((_, i) => i % 2 === 0).slice(0, 90)
    }

    // та же точка, что object-position в CSS: на телефоне сцена сдвинута к луне
    const originX = () => (window.innerWidth < 700 ? 0.22 : 0.5)

    const toScene = (cx: number, cy: number) => {
      const r = el.getBoundingClientRect()
      const scale = Math.max(r.width / W, r.height / H)
      const ox = (r.width - W * scale) * originX()
      const oy = (r.height - H * scale) / 2
      return { x: (cx - r.left - ox) / scale, y: (cy - r.top - oy) / scale }
    }

    const draw = (now: number) => {
      const dt = Math.min(now - last, 80)
      last = now
      const age = still ? 99999 : now - born
      ctx.globalCompositeOperation = 'source-over'
      ctx.globalAlpha = 1
      ctx.drawImage(img, 0, 0, W, H)

      // луна дышит мягким ореолом
      ctx.globalCompositeOperation = 'lighter'
      const pulse = 0.11 + 0.04 * Math.sin(now / 1800)
      const mg = ctx.createRadialGradient(MOON.x, MOON.y, MOON.r * 0.6, MOON.x, MOON.y, MOON.r * 2.6)
      mg.addColorStop(0, `rgba(255, 236, 190, ${pulse})`)
      mg.addColorStop(1, 'rgba(255, 236, 190, 0)')
      ctx.fillStyle = mg
      ctx.fillRect(MOON.x - MOON.r * 3, MOON.y - MOON.r * 3, MOON.r * 6, MOON.r * 6)

      // звёзды мерцают
      for (const s of stars) {
        const a = 0.5 + 0.5 * Math.sin(now * s.sp + s.ph)
        if (a < 0.55) continue
        ctx.fillStyle = `rgba(255, 250, 235, ${(a - 0.55) * 1.6})`
        ctx.fillRect(s.x, s.y, 1, 1)
        if (a > 0.97) {
          ctx.fillRect(s.x - 1, s.y, 3, 1)
          ctx.fillRect(s.x, s.y - 1, 1, 3)
        }
      }

      // свечи в тыквах и окнах: неровное пламя
      for (const [x, y, k] of LIGHTS) {
        const f = 0.75 + 0.15 * Math.sin(now / 90 + x) + 0.1 * Math.sin(now / 37 + y)
        const rad = (7 + 9 * k) * f
        const lg = ctx.createRadialGradient(x, y, 0, x, y, rad)
        lg.addColorStop(0, `rgba(255, 150, 40, ${0.42 * k * f})`)
        lg.addColorStop(1, 'rgba(255, 110, 20, 0)')
        ctx.fillStyle = lg
        ctx.fillRect(x - rad, y - rad, rad * 2, rad * 2)
      }
      ctx.globalCompositeOperation = 'source-over'

      // туман в долине и над могилами, два слоя навстречу
      const fx = (now * 0.006) % (W * 2)
      ctx.globalAlpha = 0.85
      ctx.drawImage(fog, -fx, 175)
      ctx.drawImage(fog, W * 2 - fx, 175)
      const fx2 = (now * 0.0035) % (W * 2)
      ctx.globalAlpha = 0.6
      ctx.drawImage(fog, fx2 - W * 2, 228)
      ctx.drawImage(fog, fx2, 228)
      ctx.globalAlpha = 1

      // блуждающие огоньки над могилами
      for (const w of wisps) {
        const t = now * w.sp + w.ph
        const a = Math.max(0, Math.sin(t * 0.7))
        if (a <= 0.05) continue
        const x = w.x + Math.sin(t) * 14
        const y = w.y + Math.cos(t * 1.3) * 6
        ctx.globalAlpha = a * 0.35
        ctx.fillStyle = w.hue
        ctx.fillRect(Math.round(x) - 1, Math.round(y) - 1, 3, 3)
        ctx.globalAlpha = a
        ctx.fillRect(Math.round(x), Math.round(y), 1, 1)
      }
      ctx.globalAlpha = 1

      // летучие мыши кружат у башен
      for (const b of bats) {
        const t = now * b.sp + b.ph
        const x = b.cx + Math.cos(t) * b.rx
        const y = b.cy + Math.sin(t * 2) * b.ry
        drawSprite(ctx, BAT[Math.floor(now / 110 + b.ph * 10) % 2], x, y, 1, undefined, Math.sin(t) > 0)
      }

      // стая ворон
      nextCrows -= dt
      if (nextCrows <= 0 && crows.length === 0) {
        launchCrows(false)
        nextCrows = rand(14000, 22000)
      }
      for (const c of crows) {
        c.x += c.vx * dt
        const y = c.y + Math.sin(now / 400 + c.ph) * c.amp
        drawSprite(ctx, CROW_FLY[Math.floor(now / 150 + c.ph * 3) % 2], c.x, y, 1, undefined, c.vx > 0)
      }
      crows = crows.filter((c) => c.x > -20 && c.x < W + 60)

      // ведьма на метле пролетает на фоне луны, за метлой — искры
      nextWitch -= dt
      if (nextWitch <= 0 && !witch) {
        witch = { x: W + 30, t: 0 }
        nextWitch = rand(24000, 34000)
      }
      if (witch) {
        witch.t += dt
        witch.x -= dt * 0.042
        const y = MOON.y - 4 + Math.sin(((witch.x - MOON.x) / W) * Math.PI) * 26 + Math.sin(now / 300) * 1.5
        if (Math.random() < 0.6) {
          trail.push({ x: witch.x + 20, y: y + 9, vx: rand(0.002, 0.01), vy: rand(-0.004, 0.008), life: 1 })
        }
        drawSprite(ctx, WITCH[Math.floor(now / 160) % 2], witch.x, y, 1)
        if (witch.x < -30) witch = null
      }
      for (let i = trail.length - 1; i >= 0; i--) {
        const p = trail[i]
        p.life -= dt / 900
        p.x += p.vx * dt
        p.y += p.vy * dt
        if (p.life <= 0) {
          trail.splice(i, 1)
          continue
        }
        ctx.fillStyle = p.life > 0.66 ? '#ffd23f' : p.life > 0.33 ? '#ff7a1a' : '#9cff7a'
        ctx.globalAlpha = p.life
        ctx.fillRect(Math.round(p.x), Math.round(p.y), 1, 1)
      }
      ctx.globalAlpha = 1

      // угольки за курсором
      if (cursor.x >= 0 && cursor.px >= 0) {
        const moved = Math.hypot(cursor.x - cursor.px, cursor.y - cursor.py)
        const spawn = Math.min(3, Math.floor(moved / 5))
        for (let i = 0; i < spawn && embers.length < 50; i++) {
          embers.push({ x: cursor.x + rand(-1.5, 1.5), y: cursor.y + rand(-1.5, 1.5), vx: rand(-0.004, 0.004), vy: -rand(0.006, 0.016), life: 1 })
        }
        cursor.px = cursor.x
        cursor.py = cursor.y
      }
      for (let i = embers.length - 1; i >= 0; i--) {
        const p = embers[i]
        p.life -= dt / 1100
        p.x += p.vx * dt + Math.sin(now / 200 + i) * 0.03
        p.y += p.vy * dt
        if (p.life <= 0) {
          embers.splice(i, 1)
          continue
        }
        ctx.fillStyle = p.life > 0.6 ? '#ffd23f' : p.life > 0.3 ? '#ff7a1a' : '#b8480c'
        ctx.fillRect(Math.round(p.x), Math.round(p.y), 1, 1)
      }

      // молния: двойная вспышка; первая — на входе
      nextFlash -= dt
      if (nextFlash <= 0) {
        flash = now
        nextFlash = rand(26000, 46000)
      }
      const since = still ? Infinity : now - flash
      const strike = age < INTRO_FLASH + 900 ? age - INTRO_FLASH : since
      if (strike >= 0 && strike < 700) {
        const a = strike < 90 ? 0.55 : strike < 160 ? 0.12 : strike < 240 ? 0.42 : 0.42 * (1 - (strike - 240) / 460)
        ctx.fillStyle = `rgba(225, 215, 255, ${Math.max(0, a)})`
        ctx.fillRect(0, 0, W, H)
      }

      // вход: до удара молнии — темнота
      if (age < INTRO_FLASH + 120) {
        ctx.fillStyle = `rgba(4, 2, 8, ${age < INTRO_FLASH ? 1 : 1 - (age - INTRO_FLASH) / 120})`
        ctx.fillRect(0, 0, W, H)
      }
    }

    const loop = (now: number) => {
      raf = requestAnimationFrame(loop)
      if (now - lastDraw < FRAME_MS) return
      lastDraw = now
      draw(now)
    }

    const onPointer = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse') return
      const p = toScene(e.clientX, e.clientY)
      if (cursor.px < 0) {
        cursor.px = p.x
        cursor.py = p.y
      }
      cursor.x = p.x
      cursor.y = p.y
    }

    const onVisibility = () => {
      cancelAnimationFrame(raf)
      if (!document.hidden && !still) {
        last = performance.now()
        raf = requestAnimationFrame(loop)
      }
    }

    img.onload = () => {
      pickStars()
      if (!still) launchCrows(true)
      if (still) draw(performance.now())
      else raf = requestAnimationFrame(loop)
    }
    window.addEventListener('pointermove', onPointer, { passive: true })
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      cancelAnimationFrame(raf)
      img.onload = null
      window.removeEventListener('pointermove', onPointer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return createPortal(
    <div className="spooky-sky" aria-hidden="true">
      <canvas ref={ref} className="spooky-sky__scene" />
      <span className="spooky-sky__vignette" />
    </div>,
    document.body,
  )
}
