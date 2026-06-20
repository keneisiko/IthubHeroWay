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
  const [indicatorH, setIndicatorH] = useState(72)
  const [hovered, setHovered] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({})
  const sidebarRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const update = () => {
      const el = itemRefs.current[location.pathname]
      const sidebar = sidebarRef.current
      if (!el || !sidebar) return
      const sRect = sidebar.getBoundingClientRect()
      const eRect = el.getBoundingClientRect()
      setIndicatorY(eRect.top - sRect.top)
      setIndicatorH(eRect.height)
      setReady(true)
    }
    // Небольшой delay чтобы layout успел отрисоваться
    const t = setTimeout(update, 50)
    return () => clearTimeout(t)
  }, [location.pathname])

  return (
    <aside className="right-sidebar" ref={sidebarRef} style={{ position: 'absolute' }}>
      {/* Скользящий индикатор */}
      {ready && (
        <div style={{
          position: 'absolute',
          left: '6px',
          width: '3px',
          borderRadius: '3px',
          background: 'linear-gradient(180deg, #a855f7, #6d28d9)',
          boxShadow: '0 0 10px 2px #9a33f4bb',
          top: indicatorY,
          height: indicatorH,
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

            <div style={{
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