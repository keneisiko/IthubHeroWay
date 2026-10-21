/**
 * Пиксельный прожектор: под курсором на карточке с классом .spot
 * проступает сетка квадратных точек IThub. Только для мыши — на
 * телефоне наведения нет. Координаты пишутся в CSS-переменные раз в
 * кадр, сама отрисовка — маска на псевдоэлементе.
 */

let lit: HTMLElement | null = null
let frame = 0
let lastEvent: PointerEvent | null = null

function update() {
  frame = 0
  const e = lastEvent
  if (!e) return
  const target = e.target instanceof Element ? e.target.closest<HTMLElement>('.spot') : null
  if (target !== lit) {
    lit?.classList.remove('spot--lit')
    lit = target
    lit?.classList.add('spot--lit')
  }
  if (!lit) return
  const rect = lit.getBoundingClientRect()
  lit.style.setProperty('--sx', `${e.clientX - rect.left}px`)
  lit.style.setProperty('--sy', `${e.clientY - rect.top}px`)
}

function onMove(e: PointerEvent) {
  if (e.pointerType !== 'mouse') return
  lastEvent = e
  if (!frame) frame = requestAnimationFrame(update)
}

function onLeave() {
  lit?.classList.remove('spot--lit')
  lit = null
}

export function installSpotlight(): void {
  if (typeof window === 'undefined') return
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  document.addEventListener('pointermove', onMove, { passive: true })
  document.documentElement.addEventListener('pointerleave', onLeave)
}
