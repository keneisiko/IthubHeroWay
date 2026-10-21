import { useEffect, useRef, useState } from 'react'
import BadgeEmblem from './BadgeEmblem'
import { RARITY_LABELS, formatDateRu } from '../lib/apiData'
import { CATEGORY_LABELS, tiltHandlers, type Badge, type EarnedBadge } from '../lib/badges'
import '../styles/badges.css'

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
  const closeRef = useRef<HTMLButtonElement>(null)
  const returnFocus = useRef<HTMLElement | null>(null)

  if (badge && badge !== shown) {
    setShown(badge)
    setClosing(false)
  }
  if (!badge && shown && !closing) setClosing(true)

  useEffect(() => {
    if (!badge) return
    returnFocus.current = document.activeElement as HTMLElement | null
    closeRef.current?.focus({ preventScroll: true })
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      returnFocus.current?.focus({ preventScroll: true })
    }
  }, [badge, onClose])

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
        </div>
      </section>
    </div>
  )
}
