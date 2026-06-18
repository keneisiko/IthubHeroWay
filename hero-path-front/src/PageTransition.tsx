import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'

const ROUTE_COLORS: Record<string, string> = {
  '/dashboard':   '#9a33f4',
  '/profile':     '#6d28d9',
  '/quests':      '#7c3aed',
  '/shop':        '#a855f7',
  '/leaderboard': '#5b21b6',
  '/squads':      '#8b5cf6',
}

export default function PageTransition({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const color = ROUTE_COLORS[location.pathname] ?? '#9a33f4'
  const [displayed, setDisplayed] = useState(children)
  const [phase, setPhase] = useState<'idle' | 'cover' | 'uncover'>('idle')
  const prevPath = useRef(location.pathname)
  const pendingChildren = useRef(children)

  useEffect(() => {
    if (location.pathname === prevPath.current) return
    prevPath.current = location.pathname
    pendingChildren.current = children

    setPhase('cover')

    setTimeout(() => {
      setDisplayed(pendingChildren.current)
      setPhase('uncover')
    }, 350)

    setTimeout(() => {
      setPhase('idle')
    }, 700)
  }, [location.pathname, children])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Контент */}
      <div style={{
        width: '100%', height: '100%',
        opacity: phase === 'cover' ? 0 : 1,
        transform: phase === 'cover' ? 'translateY(8px)' : 'translateY(0)',
        transition: phase === 'uncover'
          ? 'opacity 0.35s cubic-bezier(0.22,1,0.36,1), transform 0.35s cubic-bezier(0.22,1,0.36,1)'
          : 'opacity 0.2s ease, transform 0.2s ease',
      }}>
        {displayed}
      </div>

      {/* Штора */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '3px',
        background: color,
        boxShadow: `0 0 20px 4px ${color}, 0 0 60px 8px ${color}88`,
        zIndex: 9999,
        transformOrigin: 'left center',
        transform: phase === 'idle'
          ? 'scaleX(0) translateX(-100%)'
          : phase === 'cover'
          ? 'scaleX(1) translateX(0%)'
          : 'scaleX(1) translateX(100%)',
        transition: phase === 'cover'
          ? 'transform 0.35s cubic-bezier(0.76, 0, 0.24, 1)'
          : phase === 'uncover'
          ? 'transform 0.35s cubic-bezier(0.76, 0, 0.24, 1)'
          : 'none',
        pointerEvents: 'none',
      }} />

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
        backdropFilter: phase === 'cover' ? 'blur(4px)' : 'blur(0px)',
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