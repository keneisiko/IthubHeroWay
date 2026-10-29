import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { navItems } from './components/navItems'

// Порядок разделов в меню: переход «вперёд» по меню бежит вправо, назад — влево
const ORDER = navItems.map((item) => item.path)
const orderOf = (path: string) => ORDER.findIndex((p) => path.startsWith(p))

const ROUTE_COLORS: Record<string, string> = {
  '/dashboard':   '#9a33f4',
  '/profile':     '#6d28d9',
  '/quests':      '#7c3aed',
  '/shop':        '#a855f7',
  '/leaderboard': '#5b21b6',
  '/squads':      '#8b5cf6',
  '/badges':      '#9333ea',
  '/rules':       '#7c3aed',
}

export default function PageTransition({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const color = ROUTE_COLORS[location.pathname] ?? '#9a33f4'
  const [displayed, setDisplayed] = useState(children)
  const [phase, setPhase] = useState<'idle' | 'cover' | 'uncover'>('idle')
  const [reduce, setReduce] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const prevPath = useRef(location.pathname)
  const prevPathForDir = useRef(location.pathname)
  const pendingChildren = useRef(children)
  // таймеры прошлого перехода: быстрый второй тап по навигации не должен
  // снять шторку посреди нового перехода
  const timers = useRef<number[]>([])
  const [run, setRun] = useState({ id: 0, dir: 1 })

  useEffect(() => {
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onMotionChange = () => {
      setReduce(motionQuery.matches)
      setDisplayed(pendingChildren.current)
      if (!motionQuery.matches || !timers.current.length) return
      timers.current.forEach(window.clearTimeout)
      timers.current = []
      setPhase('idle')
      window.scrollTo(0, 0)
    }
    motionQuery.addEventListener('change', onMotionChange)
    return () => {
      motionQuery.removeEventListener('change', onMotionChange)
      timers.current.forEach(window.clearTimeout)
      timers.current = []
    }
  }, [])

  useEffect(() => {
    pendingChildren.current = children
    if (location.pathname === prevPath.current) return
    prevPath.current = location.pathname

    const from = orderOf(prevPathForDir.current)
    const to = orderOf(location.pathname)
    prevPathForDir.current = location.pathname
    const dir = from >= 0 && to >= 0 && to < from ? -1 : 1

    timers.current.forEach(window.clearTimeout)
    timers.current = []
    if (reduce) {
      window.scrollTo(0, 0)
      return
    }
    setRun((r) => ({ id: r.id + 1, dir }))
    setPhase('cover')

    timers.current = [window.setTimeout(() => {
      setDisplayed(pendingChildren.current)
      setPhase('uncover')
      // Новая страница открывается сверху. Без этого после длинного списка
      // лидеров профиль открывался промотанным вниз. Прыжок происходит,
      // пока страница закрыта шторкой, поэтому его не видно. Числовая форма
      // вместо { behavior: 'instant' }: старый Safari на ней бросает
      // исключение, и страница осталась бы под шторкой.
      window.scrollTo(0, 0)
    }, 280), window.setTimeout(() => {
      setPhase('idle')
      timers.current = []
    }, 620)]
  }, [location.pathname, children, reduce])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Контент */}
      <div
        className={phase === 'uncover' ? 'route-in' : undefined}
        style={{
          width: '100%', height: '100%',
          // уходящая страница сдвигается против хода, новая въезжает по ходу
          opacity: phase === 'cover' ? 0 : 1,
          transform: phase === 'cover' ? `translateX(${-run.dir * 14}px)` : 'none',
          transition: phase === 'cover' ? 'opacity 0.2s ease, transform 0.25s cubic-bezier(0.4, 0, 1, 1)' : 'none',
          '--route-dx': `${run.dir * 18}px`,
        } as React.CSSProperties}
      >
        {reduce ? children : displayed}
      </div>

      {/* Пиксель-герой пробегает по верху экрана со следом — тот же знак,
          что ходит по сетке на странице входа */}
      {phase !== 'idle' && (
        <div
          key={run.id}
          className={`route-runner${run.dir < 0 ? ' route-runner--back' : ''}`}
          style={{ '--runner': color } as React.CSSProperties}
          aria-hidden="true"
        >
          <i className="route-runner__trail" />
          <i className="route-runner__head" />
        </div>
      )}

      {/* Полная штора */}
      <div style={{
        position: 'fixed',
        inset: 0,
        background: `linear-gradient(135deg, ${color}22 0%, ${color}08 100%)`,
        zIndex: 9998,
        opacity: phase === 'cover' ? 1 : 0,
        transition: phase === 'cover'
          ? 'opacity 0.2s ease'
          : 'opacity 0.35s ease',
        pointerEvents: 'none',
      }} />

      {/* Ambient */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: -1, pointerEvents: 'none',
        background: `radial-gradient(ellipse 50% 40% at 90% 5%, ${color}14 0%, transparent 70%)`,
        transition: 'background 1.5s ease',
      }} />
    </div>
  )
}
