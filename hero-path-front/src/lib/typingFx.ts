/**
 * Отклик на ввод во всех полях приложения: из-под каретки вылетает
 * пиксель (каждый пятый — жёлтый, как монета), поле коротко вспыхивает.
 * Тот же мотив, что на странице входа, но без холста: один элемент на
 * нажатие, удаляется по окончании анимации.
 *
 * Подключается один раз, слушает input на документе — страницам ничего
 * знать не нужно. Поля входа (.lp-field__input) и пароли пропускаем:
 * у входа свой отклик, а позиция каретки в пароле выдаёт длину.
 */

const SKIP = '.lp-field__input, [type="password"], [type="file"], [type="checkbox"], [type="radio"], [type="range"]'

let layer: HTMLDivElement | null = null
let count = 0
let measure: CanvasRenderingContext2D | null = null

function getLayer(): HTMLDivElement {
  if (layer && document.body.contains(layer)) return layer
  layer = document.createElement('div')
  layer.className = 'type-fx'
  layer.setAttribute('aria-hidden', 'true')
  document.body.appendChild(layer)
  return layer
}

function caretPoint(el: HTMLInputElement | HTMLTextAreaElement): { x: number; y: number } {
  const rect = el.getBoundingClientRect()
  const cs = getComputedStyle(el)
  if (el instanceof HTMLTextAreaElement) {
    // в многострочном поле точную позицию каретки не измерить дёшево —
    // искра вылетает из правого нижнего угла, где растёт текст
    return { x: rect.right - 18, y: rect.bottom - 16 }
  }
  if (!measure) measure = document.createElement('canvas').getContext('2d')
  let width = 0
  if (measure) {
    measure.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`
    const caret = el.selectionStart ?? el.value.length
    width = measure.measureText(el.value.slice(0, caret)).width
  }
  const left = rect.left + parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth)
  const right = rect.right - parseFloat(cs.paddingRight)
  return { x: Math.min(right, left + width - el.scrollLeft), y: rect.top + rect.height / 2 }
}

function onInput(e: Event) {
  const el = e.target
  if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement)) return
  if (el.matches(SKIP)) return
  const ie = e as InputEvent
  if (ie.inputType && !ie.inputType.startsWith('insert')) return

  // поле вспыхивает: переключаем имя анимации, чтобы она перезапускалась
  const host = el.closest<HTMLElement>('.leaderboard-search, .squad-members__search') ?? el
  host.dataset.typing = host.dataset.typing === 'a' ? 'b' : 'a'

  const { x, y } = caretPoint(el)
  const px = document.createElement('i')
  count = (count + 1) % 5
  px.className = count === 0 ? 'type-fx__px type-fx__px--coin' : 'type-fx__px'
  px.style.left = `${x}px`
  px.style.top = `${y}px`
  px.style.setProperty('--dx', `${Math.round((Math.random() - 0.5) * 18)}px`)
  px.addEventListener('animationend', () => px.remove(), { once: true })
  getLayer().appendChild(px)
}

export function installTypingFx(): void {
  if (typeof window === 'undefined') return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  document.addEventListener('input', onInput, true)
}
