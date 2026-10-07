/**
 * Салют на победные моменты: покупка, сданный квест.
 *
 * Квадратное конфетти фирменных цветов — тот же квадрат, что в логотипе
 * IThub и в значках, — плюс жёлтые монетки. На телефоне короткая вибрация.
 * При системной настройке «уменьшить движение» салюта нет, только вибрация.
 *
 * Летит из точки последнего касания: пользователь нажал «Купить» —
 * салют вылетает из-под пальца, а не из центра экрана.
 */

const COLORS = ['#9a33f4', '#9a33f4', '#ff00ee', '#38dddd', '#6cd63e', '#121212', '#f5f5f5']
const COIN = '#ffd900'

let lastPointer: { x: number; y: number } | null = null
if (typeof window !== 'undefined') {
  window.addEventListener('pointerdown', (e) => {
    lastPointer = { x: e.clientX, y: e.clientY }
  }, { capture: true, passive: true })
}

interface Particle {
  x: number; y: number; vx: number; vy: number
  size: number; rot: number; vr: number
  color: string; coin: boolean
  life: number; age: number
}

export function celebrate(size: 'small' | 'big' = 'big'): void {
  if (typeof window === 'undefined') return
  navigator.vibrate?.(size === 'big' ? [14, 50, 22] : 12)
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

  const origin = lastPointer ?? { x: window.innerWidth / 2, y: window.innerHeight * 0.45 }
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const canvas = document.createElement('canvas')
  canvas.className = 'celebrate-canvas'
  canvas.width = window.innerWidth * dpr
  canvas.height = window.innerHeight * dpr
  canvas.setAttribute('aria-hidden', 'true')
  document.body.appendChild(canvas)
  const ctx = canvas.getContext('2d')
  if (!ctx) { canvas.remove(); return }
  ctx.scale(dpr, dpr)

  const count = size === 'big' ? 90 : 42
  const particles: Particle[] = Array.from({ length: count }, () => {
    // конус вверх ±70° от вертикали
    const angle = -Math.PI / 2 + (Math.random() - 0.5) * (Math.PI * 0.78)
    const speed = (size === 'big' ? 7 : 5.5) + Math.random() * 7
    const coin = Math.random() < 0.22
    return {
      x: origin.x, y: origin.y,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      size: coin ? 9 + Math.random() * 4 : 6 + Math.random() * 6,
      rot: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.35,
      color: coin ? COIN : COLORS[(Math.random() * COLORS.length) | 0],
      coin,
      life: 70 + Math.random() * 45, age: 0,
    }
  })

  let frame = 0
  // ушли со вкладки — не держим холст висеть
  const onHidden = () => {
    if (document.visibilityState === 'hidden') finish()
  }
  const finish = () => {
    cancelAnimationFrame(frame)
    canvas.remove()
    document.removeEventListener('visibilitychange', onHidden)
  }
  document.addEventListener('visibilitychange', onHidden)

  const draw = () => {
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight)
    let alive = 0
    for (const p of particles) {
      if (p.age >= p.life) continue
      alive++
      p.age++
      p.vy += 0.32
      p.vx *= 0.985
      p.vy *= 0.985
      p.x += p.vx
      p.y += p.vy
      p.rot += p.vr
      const fade = p.age > p.life * 0.65 ? 1 - (p.age - p.life * 0.65) / (p.life * 0.35) : 1
      ctx.globalAlpha = Math.max(0, fade)
      ctx.save()
      ctx.translate(p.x, p.y)
      ctx.rotate(p.rot)
      ctx.fillStyle = p.color
      if (p.coin) {
        // монетка «кувыркается»: сплющивается по ширине
        ctx.scale(Math.abs(Math.cos(p.rot * 2)) * 0.8 + 0.2, 1)
        ctx.beginPath()
        ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2)
        ctx.fill()
      } else {
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size)
      }
      ctx.restore()
    }
    if (alive > 0) frame = requestAnimationFrame(draw)
    else finish()
  }
  frame = requestAnimationFrame(draw)
}
