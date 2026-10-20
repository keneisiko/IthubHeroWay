/**
 * Убирает заставку из index.html, когда на экране уже есть настоящая
 * страница. Заставка держится не меньше MIN_MS с открытия вкладки —
 * иначе знак не успевает собраться и мелькает обрывком.
 *
 * Промис разрешается, когда заставка начала уезжать: страница может
 * придержать свою анимацию появления до этого момента, чтобы она не
 * отыграла под заставкой.
 */
const MIN_MS = 900

let released: Promise<void> | null = null

export function releaseBoot(): Promise<void> {
  if (released) return released
  const el = document.getElementById('boot')
  if (!el) {
    released = Promise.resolve()
    return released
  }
  released = new Promise((resolve) => {
    const wait = Math.max(0, MIN_MS - performance.now())
    window.setTimeout(() => {
      el.classList.add('boot--out')
      resolve()
      const remove = () => el.remove()
      el.addEventListener('animationend', (e) => { if (e.target === el) remove() })
      window.setTimeout(remove, 1200)
    }, wait)
  })
  return released
}
