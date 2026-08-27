import { Link, useLocation } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import {
  IconHome, IconProfile, IconQuests,
  IconShop, IconLeaders, IconSquads
} from './icons'

const navItems = [
  { path: '/dashboard',   Icon: IconHome,    label: 'Главная'  },
  { path: '/profile',     Icon: IconProfile, label: 'Профиль'  },
  { path: '/quests',      Icon: IconQuests,  label: 'Квесты'   },
  { path: '/shop',        Icon: IconShop,    label: 'Магазин'  },
  { path: '/leaderboard', Icon: IconLeaders, label: 'Лидеры'   },
  { path: '/squads',      Icon: IconSquads,  label: 'Отряды'   },
]

export default function Sidebar() {
  const location = useLocation()
  const [indicatorY, setIndicatorY] = useState(0)
  const [hovered, setHovered] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({})
  const sidebarRef = useRef<HTMLElement>(null)

  useEffect(() => {
    // offsetTop не зависит от трансформов: пункты масштабируются при
    // наведении и при появлении, и getBoundingClientRect в эти моменты
    // отдаёт смещённые значения — маркер вставал мимо иконки.
    const update = () => {
      const el = itemRefs.current[location.pathname]
      if (!el) return
      // маркер центрируется по иконке пункта, а не по всему пункту с подписью
      const icon = el.querySelector<HTMLElement>('.right-sidebar__icon')
      const center = icon
        ? el.offsetTop + icon.offsetTop + icon.offsetHeight / 2
        : el.offsetTop + el.offsetHeight / 2
      setIndicatorY(center)
      setReady(true)
    }
    update()

    const sidebar = sidebarRef.current
    if (!sidebar) return
    const observer = new ResizeObserver(update)
    observer.observe(sidebar)
    document.fonts?.ready.then(update)
    return () => observer.disconnect()
  }, [location.pathname])

  return (
    <aside className="right-sidebar" ref={sidebarRef} style={{ position: 'absolute' }}>
      {/* Скользящий индикатор */}
      {ready && (
        <div style={{
          position: 'absolute',
          right: '-7px',
          width: '14px',
          borderRadius: '4px',
          background: '#9a33f4',
          boxShadow: '5px 5px 17.1px 2px #9a33f4',
          top: indicatorY - 32,
          height: '64px',
          transition: 'top 0.4s cubic-bezier(0.22,1,0.36,1)',
          pointerEvents: 'none',
          zIndex: 2,
        }} />
      )}

      {navItems.map((item) => {
        const isActive = location.pathname === item.path
        const isHovered = hovered === item.path
        const Icon = item.Icon

        return (
          <Link
            key={item.path}
            to={item.path}
            ref={el => { itemRefs.current[item.path] = el }}
            className={`right-sidebar__item ${isActive ? 'right-sidebar__item--active' : ''}`}
            onMouseEnter={() => setHovered(item.path)}
            onMouseLeave={() => setHovered(null)}
            style={{
              transition: 'transform 0.25s cubic-bezier(0.22,1,0.36,1)',
              transform: isHovered ? 'translateX(-4px) scale(1.05)' : 'translateX(0) scale(1)',
            }}
          >
            {isActive && (
              <div style={{
                position: 'absolute', inset: 0, borderRadius: '12px',
                background: 'radial-gradient(ellipse at center, #9a33f422 0%, transparent 70%)',
                animation: 'sidebarPulse 2s ease-in-out infinite',
                pointerEvents: 'none',
              }} />
            )}

            <div className="right-sidebar__icon" style={{
              transform: isHovered ? 'scale(1.15) rotate(-5deg)' : 'scale(1) rotate(0deg)',
              transition: 'transform 0.3s cubic-bezier(0.34,1.56,0.64,1)',
              filter: isActive ? 'drop-shadow(0 0 6px #9a33f4)' : 'none',
            }}>
              {Icon && <Icon active={isActive} />}
            </div>

            <span style={{
              transition: 'letter-spacing 0.25s ease',
              letterSpacing: isHovered ? '0.03em' : '0',
            }}>
              {item.label}
            </span>
          </Link>
        )
      })}

      <style>{`
        @keyframes sidebarPulse {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
      `}</style>
    </aside>
  )
}