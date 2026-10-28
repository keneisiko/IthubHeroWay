import { useEffect, useRef, useState } from 'react'
import BadgeEmblem from './BadgeEmblem'
import BadgeHolders from './BadgeHolders'
import { RARITY_LABELS, formatDateRu } from '../lib/apiData'
import { CATEGORY_LABELS, ownersLabel, tiltHandlers, type Badge, type EarnedBadge } from '../lib/badges'
import '../styles/badges.css'

// Нашивки, условие которых выполняется где-то ещё: ведём туда сразу.
const BADGE_LINKS: Record<string, { href: string; label: string }> = {
  'telegram-linked': { href: 'https://t.me/ItHubHeroWaybot', label: 'Открыть бота в Telegram' },
}

interface SheetProps {
  stamp?: number
  badge: Badge | null
  earned: EarnedBadge | undefined
  isNew?: boolean
  pinning?: boolean
  onClose: () => void
  /** Нет обработчика — нашивка чужая, закреплять нечего. */
  onTogglePin?: (badge: Badge) => void
}

export default function BadgeSheet({ stamp = 0, badge, earned, isNew = false, pinning = false, onClose, onTogglePin }: SheetProps) {
  // держим последнюю нашивку, пока шторка уезжает
  const [shown, setShown] = useState<Badge | null>(badge)
  const [closing, setClosing] = useState(false)
  const panelRef = useRef<HTMLElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)
  const badgeCode = badge?.code

  if (badge && badge !== shown) {
    setShown(badge)
    setClosing(false)
  }
  if (!badge && shown && !closing) setClosing(true)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    const panel = panelRef.current
    if (!badgeCode || !panel) return
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    closeRef.current?.focus({ preventScroll: true })
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCloseRef.current()
        return
      }
      if (e.key !== 'Tab') return
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(
        'button, a[href], input, select, textarea, [tabindex]',
      )).filter((element) => element.tabIndex >= 0 && !element.matches(':disabled') && element.getClientRects().length > 0)
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      if (!focusable.some((element) => element === active) || (e.shiftKey ? active === first : active === last)) {
        e.preventDefault()
        const target = e.shiftKey ? last : first
        target?.focus({ preventScroll: true })
      }
    }
    document.addEventListener('keydown', onKey)
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true })
    }
  }, [badgeCode])

  if (!shown) return null
  const isEarned = Boolean(earned)
  const rarityLabel = RARITY_LABELS[shown.rarity] ?? shown.rarity

  return (
    <div
      className={`bd-sheet${closing ? ' bd-sheet--closing' : ''}`}
      onAnimationEnd={(e) => {
        if (closing && e.target === e.currentTarget) {
          setShown(null)
          setClosing(false)
        }
      }}
    >
      <div className="bd-sheet__scrim" onClick={onClose} />
      <section
        ref={panelRef}
        className={`bd-sheet__panel bd-sheet__panel--${shown.rarity}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="bd-sheet-title"
      >
        <span className="bd-sheet__grip" aria-hidden="true" />
        <button ref={closeRef} type="button" className="bd-sheet__close" onClick={onClose} aria-label="Закрыть">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>

        <div className="bd-sheet__stage" {...tiltHandlers()}>
          <span className="bd-sheet__halo" aria-hidden="true" />
          <span className="bd-sheet__float" data-stamp={stamp ? (stamp % 2 ? 'a' : 'b') : undefined}>
            <BadgeEmblem
              code={shown.code}
              rarity={shown.rarity}
              locked={!isEarned}
              size={168}
              className="bd-sheet__emblem"
            />
          </span>
        </div>

        <div className="bd-sheet__body">
          <div className="bd-sheet__chips">
            <span className={`bd-chip bd-chip--${shown.rarity}`}>{rarityLabel}</span>
            {shown.reward_coins > 0 && (
              <span className="bd-coins"><i aria-hidden="true" />+{shown.reward_coins}</span>
            )}
            {CATEGORY_LABELS[shown.category] && (
              <span className="bd-chip bd-chip--ghost">{CATEGORY_LABELS[shown.category]}</span>
            )}
          </div>
          <h2 id="bd-sheet-title" className="bd-sheet__title">{shown.title}</h2>
          <p className="bd-sheet__desc">{shown.description || 'Условие уточняется'}</p>
          {BADGE_LINKS[shown.code] && !isEarned && (
            <a
              className="bd-sheet__link btn-press"
              href={BADGE_LINKS[shown.code].href}
              target="_blank"
              rel="noopener noreferrer"
            >
              {BADGE_LINKS[shown.code].label}
            </a>
          )}
          {ownersLabel(shown.owners_percent) && (
            <p className="bd-owners">{ownersLabel(shown.owners_percent)}</p>
          )}

          {isEarned ? (
            <>
              <p className="bd-sheet__status">
                {isNew && <span className="bd-new">Новая</span>}
                Получена {formatDateRu(earned!.acquired_at)}
              </p>
              {onTogglePin && (
                <button
                  type="button"
                  className={`bd-sheet__action${earned!.is_pinned ? ' bd-sheet__action--ghost' : ''}`}
                  onClick={() => onTogglePin(shown)}
                  disabled={pinning}
                >
                  {earned!.is_pinned ? 'Открепить из профиля' : 'Закрепить в профиле'}
                </button>
              )}
            </>
          ) : (
            <p className="bd-sheet__status bd-sheet__status--locked">
              Ещё не получена — условие выше
            </p>
          )}

          <BadgeHolders code={shown.code} onNavigate={onClose} />
        </div>
      </section>
    </div>
  )
}
