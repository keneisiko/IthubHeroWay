/**
 * Монеты летят: при покупке пиксели-монеты вылетают из счётчика в шапке
 * к кнопке, на которую нажали; при награде — наоборот, в счётчик.
 * Так видно, откуда и куда ушли деньги, а не только что число в шапке
 * поменялось.
 *
 * Точка «откуда нажали» — последнее касание, если оно было недавно;
 * иначе центр экрана. Анимация на Web Animations: только transform и
 * opacity, без перерисовки страницы.
 */

let lastPointer: { x: number; y: number; at: number } | null = null

if (typeof window !== 'undefined') {
  window.addEventListener('pointerdown', (e) => {
    lastPointer = { x: e.clientX, y: e.clientY, at: Date.now() }
  }, { capture: true, passive: true })
}

function pointerOrCenter() {
  if (lastPointer && Date.now() - lastPointer.at < 8000) return lastPointer
  return { x: window.innerWidth / 2, y: window.innerHeight * 0.55 }
}

export function flyCoins(target: Element | null, direction: 'in' | 'out', count = 7): Promise<void> {
  if (!target || typeof window === 'undefined') return Promise.resolve()
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return Promise.resolve()

  const rect = target.getBoundingClientRect()
  const coin = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
  const touch = pointerOrCenter()
  const from = direction === 'in' ? touch : coin
  const to = direction === 'in' ? coin : touch

  const layer = document.createElement('div')
  layer.className = 'coin-fly'
  layer.setAttribute('aria-hidden', 'true')
  document.body.appendChild(layer)

  const flights = Array.from({ length: count }, (_, i) => {
    const px = document.createElement('i')
    px.className = 'coin-fly__px'
    layer.appendChild(px)
    const spread = (i - (count - 1) / 2) * 14
    const lift = 70 + Math.random() * 60
    const midX = (from.x + to.x) / 2 + spread
    const midY = Math.min(from.y, to.y) - lift
    const anim = px.animate(
      [
        { transform: `translate(${from.x}px, ${from.y}px) scale(0.4) rotate(0deg)`, opacity: 0 },
        { transform: `translate(${from.x + spread * 0.4}px, ${from.y - 18}px) scale(1) rotate(45deg)`, opacity: 1, offset: 0.18 },
        { transform: `translate(${midX}px, ${midY}px) scale(1.1) rotate(160deg)`, opacity: 1, offset: 0.55 },
        { transform: `translate(${to.x}px, ${to.y}px) scale(0.5) rotate(270deg)`, opacity: 0.2 },
      ],
      {
        duration: 720 + i * 30,
        delay: i * 45,
        easing: 'cubic-bezier(0.45, 0, 0.25, 1)',
        fill: 'forwards',
      },
    )
    return anim.finished.catch(() => undefined)
  })

  return Promise.all(flights).then(() => { layer.remove() })
}
