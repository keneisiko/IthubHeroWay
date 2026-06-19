import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import ithubLogo from '../assets/other/лого-26 1.svg'
import api from '../api'
import { clearAuthTokens } from '../auth'

interface ProfileData {
  callsign: string
  coins: number
  avatar?: string
}

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/api/v1/profile/me/').then(res => setProfile(res.data)).catch(() => {})
  }, [])

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEsc)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [menuOpen])

  const username = profile?.callsign || 'Агент'
  const coins = profile?.coins ?? 0
  const avatarUrl = profile?.avatar
  const initials = username.slice(0, 2).toUpperCase()

  return (
    <header className="top-header" style={{ position: 'relative', zIndex: 90 }}>
      <div className="top-header__brand">
        <img src={ithubLogo} alt="IThub" className="top-header__logo-image" />
        <span className="top-header__divider" />
        <span className="top-header__title">Путь героя</span>
      </div>
      <div className="top-header__user" style={{ position: 'relative', zIndex: 100 }} ref={menuRef}>
        <div className="top-header__user-meta">
          <div className="top-header__username">{username}</div>
          <div className="top-header__money">
            <span className="top-header__coin" aria-hidden="true" />
            <strong>{coins}</strong>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, position: 'relative', zIndex: 101 }}
          aria-expanded={menuOpen}
          aria-haspopup="menu"
        >
          {avatarUrl ? (
            <img src={avatarUrl} alt="Аватар пользователя" className="top-header__avatar" style={{ pointerEvents: 'none' }} />
          ) : (
            <div className="top-header__avatar top-header__avatar--initials" style={{ pointerEvents: 'none' }}>
              {initials}
            </div>
          )}
        </button>

        {menuOpen && (
          <div
            className="header-user-menu"
            role="menu"
            style={{ zIndex: 102 }}
          >
            <button
              type="button"
              role="menuitem"
              onClick={(e) => { e.stopPropagation(); setMenuOpen(false); navigate('/profile') }}
              className="header-user-menu__item"
            >
              <svg width="24" height="24" viewBox="0 0 32 32" fill="none">
                <circle cx="16" cy="10" r="5" fill="#9a33f4" />
                <path d="M6 28c0-5.523 4.477-10 10-10s10 4.477 10 10" fill="#9a33f4" />
              </svg>
              <span>Профиль</span>
            </button>
            <div className="header-user-menu__divider" />
            <button
              type="button"
              role="menuitem"
              onClick={(e) => { e.stopPropagation(); setMenuOpen(false); clearAuthTokens(); navigate('/login') }}
              className="header-user-menu__item"
            >
              <svg width="24" height="24" viewBox="0 0 32 32" fill="none">
                <rect x="8" y="6" width="16" height="20" rx="2" fill="#9a33f4" opacity="0.3" />
                <path d="M18 16h8m0 0l-4-4m4 4l-4 4" stroke="#9a33f4" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>Выйти</span>
            </button>
          </div>
        )}
      </div>
    </header>
  )
}