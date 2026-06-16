import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import ithubLogo from '../assets/other/лого-26 1.svg'
import userAvatar from '../assets/branding/user-avatar.png'
import api from '../api'

interface ProfileData {
  callsign: string
  coins: number
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
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [menuOpen])

  const username = profile?.callsign || localStorage.getItem('username') || 'имя пользователя'
  const coins = profile?.coins ?? 0

  return (
    <header className="top-header">
      <div className="top-header__brand">
        <img src={ithubLogo} alt="IThub" className="top-header__logo-image" />
        <span className="top-header__divider" />
        <span className="top-header__title">Путь героя</span>
      </div>
      <div className="top-header__user" style={{ position: 'relative' }} ref={menuRef}>
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
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
        >
          <img src={userAvatar} alt="Аватар пользователя" className="top-header__avatar" />
        </button>

        {menuOpen && (
          <div
            className="popup"
            style={{
              position: 'absolute',
              top: '56px',
              right: 0,
              background: '#f5f5f5',
              borderRadius: '12px',
              border: '4px solid #9a33f4',
              boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)',
              padding: '12px 20px',
              minWidth: '200px',
              zIndex: 60,
            }}
          >
            <button
              type="button"
              onClick={() => { setMenuOpen(false); navigate('/profile') }}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                background: 'none', border: 'none', cursor: 'pointer', width: '100%',
                padding: '8px 0', fontFamily: 'Montserrat, sans-serif', fontWeight: 600,
                fontSize: '16px', color: '#9a33f4', transition: 'opacity 0.2s',
              }}
            >
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                <circle cx="16" cy="10" r="5" fill="#9a33f4" />
                <path d="M6 28c0-5.523 4.477-10 10-10s10 4.477 10 10" fill="#9a33f4" />
              </svg>
              Профиль
            </button>
            <div style={{ height: '4px', background: '#9a33f4', borderRadius: '5px', margin: '4px 0' }} />
            <button
              type="button"
              onClick={() => { setMenuOpen(false); localStorage.clear(); navigate('/login') }}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                background: 'none', border: 'none', cursor: 'pointer', width: '100%',
                padding: '8px 0', fontFamily: 'Montserrat, sans-serif', fontWeight: 600,
                fontSize: '16px', color: '#9a33f4', transition: 'opacity 0.2s',
              }}
            >
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                <rect x="8" y="6" width="16" height="20" rx="2" fill="#9a33f4" opacity="0.3" />
                <path d="M18 16h8m0 0l-4-4m4 4l-4 4" stroke="#9a33f4" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Выйти
            </button>
          </div>
        )}
      </div>
    </header>
  )
}