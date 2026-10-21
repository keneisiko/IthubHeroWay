import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import ithubLogo from '../assets/other/лого-26 1.svg'
import api from '../api'
import { clearAuthTokens } from '../auth'
import { onBalanceChanged } from '../lib/balance'
import RollNumber from './RollNumber'
import Avatar from './Avatar'
import { hasFrame, type AppliedItems } from '../lib/cosmetics'
import { formatRating } from '../lib/apiData'
import { flyCoins } from '../lib/coinFly'

interface ProfileData {
  callsign: string
  coins_balance: number
  avatar?: string | null
  applied_items?: AppliedItems
}

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const loadProfile = useCallback(() => {
    api.get('/api/v1/profile/me/').then(res => setProfile(res.data)).catch(() => {})
  }, [])

  // Шапка живёт всю сессию, поэтому профиль перечитывается, когда баланс
  // поменяли на странице (покупка) и когда пользователь вернулся во вкладку:
  // награды за квесты начисляет куратор, пока студент занят другим.
  useEffect(() => {
    loadProfile()
    const offBalance = onBalanceChanged(loadProfile)
    const onVisible = () => {
      if (document.visibilityState === 'visible') loadProfile()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      offBalance()
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [loadProfile])

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
  const coins = profile?.coins_balance ?? 0

  // Короткий «пульс» монетки, когда баланс изменился уже после загрузки
  const [pulse, setPulse] = useState<'up' | 'down' | null>(null)
  const prevCoins = useRef<number | null>(null)
  const coinRef = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (!profile) return
    const prev = prevCoins.current
    prevCoins.current = coins
    if (prev === null || prev === coins) return
    setPulse(coins > prev ? 'up' : 'down')
    // монеты видно в полёте: награда — в счётчик, покупка — из него
    flyCoins(coinRef.current, coins > prev ? 'in' : 'out', Math.min(9, 4 + Math.round(Math.abs(coins - prev) / 15)))
    const timer = setTimeout(() => setPulse(null), 700)
    return () => clearTimeout(timer)
  }, [coins, profile])

  return (
    <header className="top-header" style={{ position: 'relative', zIndex: 90 }}>
      <div className="top-header__brand">
        <img src={ithubLogo} alt="IThub" className="top-header__logo-image" />
        <span className="top-header__divider" />
        <span className="top-header__title">Путь героя</span>
      </div>
      <div className="top-header__user" style={{ position: 'relative', zIndex: 100 }} ref={menuRef}>
        {/* имя, монеты и аватар — одна кнопка меню: попасть можно
            в любую часть блока, а не только в кружок аватара */}
        <button
          type="button"
          className="top-header__trigger"
          onClick={() => setMenuOpen((v) => !v)}
          aria-expanded={menuOpen}
          aria-haspopup="menu"
        >
          <span className="top-header__user-meta">
            <span className="top-header__username">{username}</span>
            <span className={`top-header__money${pulse ? ` top-header__money--${pulse}` : ''}`}>
              <span className="top-header__coin" aria-hidden="true" ref={coinRef} />
              <strong><RollNumber value={formatRating(coins)} /></strong>
            </span>
          </span>
          <Avatar
            src={profile?.avatar}
            name={username}
            framed={hasFrame(profile?.applied_items)}
            className="top-header__avatar top-header__avatar--initials"
          />
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