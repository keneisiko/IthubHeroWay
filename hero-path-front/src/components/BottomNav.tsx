import { Link, useLocation } from 'react-router-dom'
import { useCallback, useEffect, useRef, useState } from 'react'
import { navItems } from './navItems'

/**
 * Навигация мобильной версии: в макете боковая панель уезжает вниз
 * и превращается в панель с одними иконками.
 *
 * Панель и боковой сайдбар рендерятся оба, а показывает нужный
 * медиазапрос — так переключение при повороте экрана не требует
 * слушателей resize и не сбрасывает состояние страницы.
 */
export default function BottomNav() {
  const location = useLocation()
  const navRef = useRef<HTMLElement>(null)
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({})
  const [pill, setPill] = useState<{ left: number; width: number } | null>(null)
  const [hidden, setHidden] = useState(false)

  // Пилюля активного пункта едет к нему, как маркер у боковой панели.
  // Панель position: fixed, поэтому offsetLeft пунктов уже отсчитан от неё.
  const measure = useCallback(() => {
    const el = itemRefs.current[location.pathname]
    if (!el) { setPill(null); return }
    setPill({ left: el.offsetLeft, width: el.offsetWidth })
  }, [location.pathname])

  useEffect(() => {
    measure()
    const nav = navRef.current
    if (!nav) return
    const observer = new ResizeObserver(measure)
    observer.observe(nav)
    return () => observer.disconnect()
  }, [measure])

  // На телефоне экран маленький: при прокрутке вниз панель уходит,
  // при любом движении вверх, у самого верха и в самом низу страницы —
  // возвращается: дочитал до конца, дальше нужна навигация.
  useEffect(() => {
    let lastY = window.scrollY
    let frame = 0
    const onScroll = () => {
      if (frame) return
      frame = requestAnimationFrame(() => {
        frame = 0
        const y = window.scrollY
        const delta = y - lastY
        const atBottom = window.innerHeight + y >= document.documentElement.scrollHeight - 2
        if (y < 80 || atBottom || delta < -6) setHidden(false)
        else if (delta > 6) setHidden(true)
        if (Math.abs(delta) > 6) lastY = y
      })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      cancelAnimationFrame(frame)
    }
  }, [])

  // на новой странице панель всегда на виду
  useEffect(() => { setHidden(false) }, [location.pathname])

  return (
    <nav
      ref={navRef}
      className={`bottom-nav${hidden ? ' bottom-nav--hidden' : ''}${pill ? ' bottom-nav--measured' : ''}`}
      aria-label="Основная навигация"
    >
      {pill && (
        <span
          className="bottom-nav__pill"
          aria-hidden="true"
          style={{ width: pill.width, transform: `translateX(${pill.left}px)` }}
        />
      )}
      {navItems.map(({ path, Icon, label }) => {
        const isActive = location.pathname === path
        return (
          <Link
            key={path}
            to={path}
            ref={el => { itemRefs.current[path] = el }}
            className={`bottom-nav__item${isActive ? ' bottom-nav__item--active' : ''}`}
            aria-current={isActive ? 'page' : undefined}
            aria-label={label}
            onFocus={() => setHidden(false)}
          >
            <span className="bottom-nav__icon">
              <Icon active={isActive} />
            </span>
          </Link>
        )
      })}
    </nav>
  )
}
