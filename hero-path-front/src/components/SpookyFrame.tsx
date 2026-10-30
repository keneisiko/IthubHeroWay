import { useEffect, useRef } from 'react'
import { outline, type Rect } from '../lib/pixelFrame'
import {
  BAT, CANDLE, CROW_FLY, CROW_SIT, FLAME, GHOST, NIGHT, PUMPKIN, PUMPKIN_SMALL, SKULL, SPIDER, drawSprite,
} from '../lib/pixelSprites'

interface SpookyFrameProps {
  /** Крупная рамка профиля: свеча, череп, ворон, паук, призрак, мышь. */
  large?: boolean
  /** Появление при открытии профиля: кладка рушится сверху и складывается. */
  intro?: boolean
}

const BAYER = [
  [0, 8, 2, 10],
  [12, 4, 14, 6],
  [3, 11, 1, 9],
  [15, 7, 13, 5],
]
const STONES = ['#2b2340', '#352a4d', '#40335c', '#2f2645', '#3a2f55']
const STONE_HI = '#56487a'
const MORTAR = '#16111f'
const CRACK = '#0e0a16'
const CAP = '#62528a'
const MOSS = ['#4f8a3a', '#3d6e2c']
const IVY = ['#3f7a30', '#5a9a3c', '#2f5a26']
const WEB = 'rgba(226, 218, 245, 0.42)'
const FACE = ['#ffd23f', '#ffb020', '#fff3c4', '#ffc230']
const FOG = '#5f4f8c'
const SMOKE = '#8a72c4'

interface Stone extends Rect { color: string; delay: number }
interface Ember { x: number; y: number; vx: number; vy: number; life: number }

const rand = (a: number, b: number) => a + Math.random() * (b - a)
const clamp01 = (v: number) => Math.max(0, Math.min(1, v))
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3)

// линия по клеткам — паутина рисуется пикселями, а не сглаженной чертой
function pixelLine(ctx: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, u: number) {
  const steps = Math.max(1, Math.round(Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) / u))
  for (let i = 0; i <= steps; i++) {
    const x = x0 + ((x1 - x0) * i) / steps
    const y = y0 + ((y1 - y0) * i) / steps
    ctx.fillRect(Math.round(x / u) * u, Math.round(y / u) * u, u, u)
  }
}

/**
 * Рамка нашивки «Самый страшный» — пиксельный склеп. Фото вмуровано в
 * кладку из кирпичей с трещинами, мхом и плющом; над ним — череп-замковый
 * камень с горящими глазами и оплывшая свеча. В крупной рамке на краю
 * сидит ворон (моргает, вертит головой, каркает, хлопает крылом), в углу
 * паутина с пауком, внизу тыквы, из тумана выглядывает призрак, вокруг
 * облетает летучая мышь и поднимаются искры. При появлении из-под фото
 * вырывается дым, кладка рушится сверху и складывается снизу вверх,
 * свеча и тыква загораются, прилетает ворон.
 */
export default function SpookyFrame({ large = false, intro = false }: SpookyFrameProps) {
  const ref = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const el = ref.current
    const host = el?.parentElement
    const ctx = el?.getContext('2d')
    if (!el || !host || !ctx) return
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    const u = large ? Math.max(3, Math.round(4 * dpr)) : Math.max(2, Math.round(2 * dpr))
    const su = large ? u : Math.max(1, Math.round(dpr))
    const hu = Math.max(1, Math.round(u / 2))
    const margin = large ? 17 : 5
    const o = margin * u
    const fps = large ? 12 : 8
    let s = 0
    let w = 0
    let stones: Stone[] = []
    let ivy: Stone[] = []
    let timer = 0
    const born = performance.now()
    const playIntro = intro && !still
    let crowFrame = 0
    let nextCrowMove = 2600
    let ghostAt = 1900
    const embers: Ember[] = []

    const fit = () => {
      s = Math.round(host.offsetWidth * dpr)
      w = s + o * 2
      el.width = w
      el.height = w
      el.style.width = el.style.height = `${w / dpr}px`
      el.style.left = el.style.top = `${-o / dpr}px`
      host.style.setProperty('--spooky-px', `${u / dpr}px`)
      // шов у фото и кирпичи вразбежку: в каждом ряду свой сдвиг, на углах — светлый край
      stones = []
      const rings = large ? 3 : 2
      for (let r = 0; r < rings; r++) {
        const cells = outline(o - r * u, s + 2 * r * u, u)
        cells.forEach((c, i) => {
          let color: string
          if (r === 0) color = MORTAR
          else {
            const k = i + r * 2
            const brick = Math.floor(k / 4)
            const top = c.y < o - r * u
            const bottom = c.y > o + s + (r - 1) * u
            if (k % 4 === 3) color = MORTAR
            else if (Math.random() < 0.05) color = CRACK
            else if (bottom && r === rings - 1 && Math.random() < 0.4) color = MOSS[i % 2]
            else if (top && r === rings - 1) color = k % 4 === 0 ? STONE_HI : CAP
            else color = k % 4 === 0 ? STONE_HI : STONES[(brick * 7 + r) % STONES.length]
          }
          // кладка складывается снизу вверх: нижние камни падают первыми
          const delay = 450 + (1 - c.y / w) * 650 + rand(0, 90)
          stones.push({ ...c, color, delay })
        })
      }
      ivy = []
      if (large) {
        for (const [x0, len] of [[o - 4 * u, 8], [o + u, 4], [o + 4 * u, 6], [o + s + 2 * u, 5]] as const) {
          let x = x0
          for (let k = 0; k < len; k++) {
            ivy.push({ x, y: o - 3 * u + k * u, w: u, h: u, color: IVY[k % IVY.length], delay: 1250 + k * 70 })
            if (k % 3 === 2) x += Math.random() < 0.5 ? -u : u
          }
        }
      }
    }

    const draw = (now: number) => {
      const age = playIntro ? now - born : 99999
      ctx.clearRect(0, 0, w, w)
      const flick = still ? 0.85 : 0.72 + 0.16 * Math.sin(now / 95) + 0.12 * Math.sin(now / 41)
      const lit = clamp01((age - 1250) / 300)
      const face = FACE[Math.floor((flick - 0.44) * 4.9) % FACE.length] ?? FACE[0]
      const pal = { ...NIGHT, y: face, E: flick > 0.85 ? '#ffb347' : '#ff7a1a' }

      // свет свечи и тыквы ложится на кладку и фото
      ctx.globalCompositeOperation = 'lighter'
      const px = o + s - u
      const py = o + s
      const lg = ctx.createRadialGradient(px, py, 0, px, py, s * (large ? 1 : 0.8))
      lg.addColorStop(0, `rgba(255, 140, 40, ${(large ? 0.42 : 0.5) * flick * (large ? lit : 1)})`)
      lg.addColorStop(0.45, `rgba(255, 100, 20, ${0.13 * flick * (large ? lit : 1)})`)
      lg.addColorStop(1, 'rgba(255, 90, 10, 0)')
      ctx.fillStyle = lg
      ctx.fillRect(0, 0, w, w)
      if (large) {
        const cx = o + 2.5 * u
        const cy = o - 13 * u
        const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, 16 * u)
        cg.addColorStop(0, `rgba(255, 190, 80, ${0.3 * flick * lit})`)
        cg.addColorStop(1, 'rgba(255, 150, 40, 0)')
        ctx.fillStyle = cg
        ctx.fillRect(0, 0, w, w)
      }
      ctx.globalCompositeOperation = 'source-over'

      // призрак поднимается из тумана у левого нижнего угла, моргает и уходит обратно
      if (large && !still) {
        const cycle = 9500
        const t = (now - born - ghostAt + cycle * 10) % cycle
        if (age > ghostAt && t < 3200) {
          const rise = t < 700 ? easeOut(t / 700) : t > 2500 ? 1 - easeOut((t - 2500) / 700) : 1
          const gx = o - 11 * u
          const gy = o + s + 3 * u - rise * 10 * u + Math.sin(now / 260) * u * 0.5
          ctx.globalAlpha = 0.88
          const ghost = GHOST[Math.floor(now / 220) % 2]
          const blink = t % 1400 < 120
          drawSprite(ctx, blink ? ghost.map((row, j) => (j === 3 || j === 4 ? row.replace(/k/g, 't') : row)) : ghost, gx, gy, u, pal)
          ctx.globalAlpha = 1
        }
      }

      // туман стелется низким облаком у подножия кладки: точки по Байеру,
      // гуще в середине, к краям тают, клубы медленно плывут
      if (large) {
        const fx = o + s / 2
        const fy = o + s + 3 * u
        const rx = s / 2 + 11 * u
        const ry = 5 * u
        const cols = Math.ceil(w / u)
        for (let j = Math.floor((fy - ry) / u); j < cols; j++) {
          for (let i = 0; i < cols; i++) {
            const ex = (i * u + u / 2 - fx) / rx
            const ey = (j * u + u / 2 - fy) / ry
            const ell = ex * ex + ey * ey
            if (ell >= 1) continue
            const wave = 0.5 + 0.5 * Math.sin(i * 0.42 + now / 900 + j * 0.9) * Math.sin(i * 0.15 - now / 1400)
            const k = (0.18 + 0.5 * wave) * (1 - ell) * clamp01((age - 900) / 600)
            if (BAYER[j % 4][(i + Math.floor(now / 450)) % 4] / 16 >= k) continue
            ctx.fillStyle = FOG
            ctx.fillRect(i * u, j * u, u, u)
          }
        }
      }

      // дым из-под фото на входе: кольцо точек расходится и тает
      if (playIntro && age > 400 && age < 1500) {
        const t = (age - 400) / 1100
        const R = s / 2 + 2 * u + t * 13 * u
        const c = o + s / 2
        const cols = Math.ceil(w / u)
        for (let j = 0; j < cols; j++) {
          for (let i = 0; i < cols; i++) {
            const d = Math.hypot(i * u + u / 2 - c, j * u + u / 2 - c)
            const band = 1 - Math.abs(d - R) / (4 * u)
            if (band <= 0) continue
            if (BAYER[j % 4][i % 4] / 16 >= band * (1 - t) * 0.9) continue
            ctx.fillStyle = SMOKE
            ctx.fillRect(i * u, j * u, u, u)
          }
        }
      }

      // кладка: камни падают сверху и встают на место
      for (const c of stones) {
        const local = age - c.delay
        if (local < 0) continue
        const k = clamp01(local / 260)
        const drop = (1 - easeOut(k)) * 9 * u
        ctx.fillStyle = c.color
        ctx.fillRect(c.x, Math.round(c.y - drop), c.w, c.h)
      }
      for (const c of ivy) {
        if (age < c.delay) continue
        ctx.fillStyle = c.color
        ctx.fillRect(c.x, c.y, c.w, c.h)
      }

      if (!large) {
        drawSprite(ctx, PUMPKIN_SMALL, o + s - 4 * su, o + s - 3 * su, su, pal)
        return
      }

      // паутина в верхнем левом углу фото и паук на нитке
      if (age > 1350) {
        const len = Math.min(13 * u, s * 0.46)
        ctx.fillStyle = WEB
        const rays = [0, 0.5, 1.07, Math.PI / 2].map((a) => [o + Math.cos(a) * len, o + Math.sin(a) * len])
        for (const [x, y] of rays) pixelLine(ctx, o, o, x, y, hu)
        for (const r of [0.42, 0.82]) {
          for (let i = 0; i < rays.length - 1; i++) {
            const [x0, y0] = rays[i]
            const [x1, y1] = rays[i + 1]
            pixelLine(ctx, o + (x0 - o) * r, o + (y0 - o) * r, o + (x1 - o) * r, o + (y1 - o) * r, hu)
          }
        }
      }
      if (age > 1600) {
        const t = still ? 1 : clamp01((age - 1600) / 1400)
        const climb = still ? 0 : Math.max(0, Math.sin(now / 5200)) ** 6
        const drop = (3 + 9 * t) * u * (1 - climb * 0.8) + (still ? 0 : Math.sin(now / 650) * u)
        const sx = o - 6 * u
        const sy = o - 3 * u
        ctx.fillStyle = WEB
        for (let y = sy; y < sy + drop; y += u) ctx.fillRect(Math.round(sx / u) * u, Math.round(y / u) * u, u, u)
        drawSprite(ctx, SPIDER, Math.round(sx / u) * u - 2 * u, Math.round((sy + drop) / u) * u, u, pal)
      }

      // череп — замковый камень, падает последним
      const skullT = clamp01((age - 1100) / 300)
      if (skullT > 0) {
        drawSprite(ctx, SKULL, o + 9 * u, o - 6 * u - (1 - easeOut(skullT)) * 10 * u, u, pal)
      }

      // оплывшая свеча на кладке: фитиль вспыхивает и горит неровно
      if (age > 1150) {
        const cx = o + u
        const cy = o - 11 * u
        drawSprite(ctx, CANDLE, cx, cy, u, pal)
        if (lit > 0) drawSprite(ctx, FLAME[Math.floor(now / 140) % FLAME.length], cx, cy - 5 * u, u, pal)
      }

      // тыквы: большая выкатывается в нижний правый угол, маленькая — у левого
      const roll = clamp01((age - 1200) / 450)
      if (roll > 0) {
        drawSprite(ctx, PUMPKIN, o + s - 6 * u + (1 - easeOut(roll)) * 14 * u, o + s - 4 * u, u, lit > 0 ? pal : { ...pal, y: '#3a1d0a' })
        drawSprite(ctx, PUMPKIN_SMALL, o - 5 * u, o + s - 2 * u, u, lit > 0 ? pal : { ...pal, y: '#3a1d0a' })
      }

      // искры поднимаются от тыквы и свечи
      if (!still && lit >= 1) {
        if (Math.random() < 0.35) embers.push({ x: o + s - u + rand(-3, 3) * u, y: o + s - 3 * u, vx: rand(-0.004, 0.004) * u, vy: -rand(0.012, 0.022) * u, life: 1 })
        if (Math.random() < 0.15) embers.push({ x: o + 2 * u, y: o - 15 * u, vx: rand(-0.003, 0.003) * u, vy: -rand(0.01, 0.018) * u, life: 1 })
      }
      for (let i = embers.length - 1; i >= 0; i--) {
        const p = embers[i]
        p.life -= (1000 / fps) / 1500
        p.x += p.vx * (1000 / fps)
        p.y += p.vy * (1000 / fps)
        if (p.life <= 0 || embers.length > 40) {
          embers.splice(i, 1)
          continue
        }
        ctx.fillStyle = p.life > 0.6 ? '#ffd23f' : p.life > 0.3 ? '#ff7a1a' : '#b8480c'
        ctx.fillRect(Math.round(p.x / u) * u, Math.round(p.y / u) * u, u, u)
      }

      // летучая мышь облетает рамку
      if (!still && age > 1900) {
        const t = now / 1300
        const bx = o + s / 2 + Math.cos(t) * (s / 2 + 10 * u) - 4 * u
        const by = o + s / 2 + Math.sin(t) * (s / 2 + 9 * u) * 0.92
        drawSprite(ctx, BAT[Math.floor(now / 120) % 2], bx, by, u, pal, Math.sin(t) < 0)
      }

      // ворон прилетает и садится на край, потом моргает, вертит головой, каркает
      const perchX = o + s - 11 * u
      const perchY = o - 3 * u - 8 * u
      const land = still ? 1 : playIntro ? clamp01((age - 950) / 900) : 1
      if (land < 1) {
        const k = 1 - Math.pow(1 - land, 3)
        drawSprite(ctx, CROW_FLY[Math.floor(now / 110) % 2], w + 4 * u + (perchX - w - 4 * u) * k, -6 * u + (perchY + 6 * u) * k, u, pal)
      } else {
        if (!still) {
          nextCrowMove -= 1000 / fps
          if (nextCrowMove <= 0) {
            crowFrame = crowFrame === 0 ? [1, 1, 3, 2, 4][Math.floor(Math.random() * 5)] : 0
            nextCrowMove = crowFrame === 0 ? rand(1800, 4200) : crowFrame === 1 ? 160 : crowFrame === 4 ? 260 : crowFrame === 2 ? 420 : rand(900, 1600)
          }
        }
        drawSprite(ctx, CROW_SIT[crowFrame], perchX, perchY, u, pal)
      }
    }

    const tick = () => draw(performance.now())
    const start = () => {
      window.clearInterval(timer)
      if (!still && !document.hidden) timer = window.setInterval(tick, 1000 / fps)
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
    ghostAt = playIntro ? 2300 : 600

    return () => {
      window.clearInterval(timer)
      ro.disconnect()
      document.removeEventListener('visibilitychange', start)
      host.style.removeProperty('--spooky-px')
    }
  }, [large, intro])

  return <canvas ref={ref} className="spooky-frame" aria-hidden="true" />
}
