import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import api from '../api'
import LoadError from '../components/LoadError'
import BrandLoader from '../components/BrandLoader'
import BadgeEmblem from '../components/BadgeEmblem'
import { useToasts } from '../useToasts'
import { useTabIndicator } from '../useTabIndicator'
import { celebrate } from '../lib/celebrate'
import { RARITY_LABELS, formatDateRu, unwrapList } from '../lib/apiData'
import '../styles/badges.css'

interface Badge {
  code: string
  title: string
  description: string
  category: string
  rarity: string
  reward_coins: number
}

interface EarnedBadge {
  id: number
  badge: Badge
  acquired_at: string
  is_pinned?: boolean
}

// Категории приходят с бэка кодами (BadgeCategory), подписи — здесь.
const CATEGORY_LABELS: Record<string, string> = {
  progress: 'Прогресс',
  academic: 'Учёба',
  social: 'Сообщество',
  special: 'Особые',
}

const RARITY_ORDER = ['common', 'rare', 'epic', 'legendary']

type Filter = 'all' | 'earned' | 'locked'

const FILTERS: [Filter, string][] = [
  ['all', 'Все'],
  ['earned', 'Полученные'],
  ['locked', 'Осталось'],
]

// Какие нашивки студент уже видел: новые встречаем салютом один раз.
const SEEN_KEY = 'hp:badges-seen'

function readSeen(): Set<string> | null {
  try {
    const raw = localStorage.getItem(SEEN_KEY)
    return raw ? new Set(JSON.parse(raw) as string[]) : null
  } catch {
    return null
  }
}

function writeSeen(codes: string[]) {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(codes))
  } catch {
    // без хранилища новые нашивки просто не подсвечиваются
  }
}

// В карточке дата короткая: «17 окт.», год — только если не текущий.
// Полная «17 октября 2026 г.» переносила «г.» отдельной строкой.
function shortDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const sameYear = date.getFullYear() === new Date().getFullYear()
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    ...(sameYear ? {} : { year: 'numeric' }),
  }).format(date)
}

const canHover = () => window.matchMedia('(hover: hover) and (pointer: fine)').matches

/** Наклон эмблемы за курсором: только CSS-переменные, без перерисовки React. */
function tiltHandlers() {
  return {
    onPointerMove: (e: React.PointerEvent<HTMLElement>) => {
      if (e.pointerType !== 'mouse' || !canHover()) return
      const el = e.currentTarget
      const rect = el.getBoundingClientRect()
      const x = (e.clientX - rect.left) / rect.width - 0.5
      const y = (e.clientY - rect.top) / rect.height - 0.5
      el.style.setProperty('--tilt-x', `${(-y * 14).toFixed(2)}deg`)
      el.style.setProperty('--tilt-y', `${(x * 18).toFixed(2)}deg`)
    },
    onPointerLeave: (e: React.PointerEvent<HTMLElement>) => {
      e.currentTarget.style.setProperty('--tilt-x', '0deg')
      e.currentTarget.style.setProperty('--tilt-y', '0deg')
    },
  }
}

interface SheetProps {
  badge: Badge | null
  earned: EarnedBadge | undefined
  isNew: boolean
  pinning: boolean
  onClose: () => void
  onTogglePin: (badge: Badge) => void
}

function BadgeSheet({ badge, earned, isNew, pinning, onClose, onTogglePin }: SheetProps) {
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
          <span className="bd-sheet__float">
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
              <button
                type="button"
                className={`bd-sheet__action${earned!.is_pinned ? ' bd-sheet__action--ghost' : ''}`}
                onClick={() => onTogglePin(shown)}
                disabled={pinning}
              >
                {earned!.is_pinned ? 'Открепить из профиля' : 'Закрепить в профиле'}
              </button>
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

export default function Badges() {
  const [catalog, setCatalog] = useState<Badge[]>([])
  const [earned, setEarned] = useState<EarnedBadge[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [category, setCategory] = useState<string>('')
  const [openCode, setOpenCode] = useState<string | null>(null)
  const [pinning, setPinning] = useState(false)
  const [fresh, setFresh] = useState<Set<string>>(() => new Set())
  const { toasts, addToast } = useToasts()
  const { containerRef: tabsRef, registerTab, indicator } = useTabIndicator(filter, !loading)

  // Состояние меняется только в колбэках промиса: вызов setState прямо в теле
  // эффекта запускает каскад повторных отрисовок (react-hooks/set-state-in-effect).
  const load = useCallback(
    () =>
      Promise.all([api.get('/api/v1/badges/'), api.get('/api/v1/badges/my/')])
        .then(([catalogRes, myRes]) => {
          setCatalog(unwrapList<Badge>(catalogRes.data))
          setEarned(unwrapList<EarnedBadge>(myRes.data))
          setLoadError(false)
        })
        .catch(() => setLoadError(true))
        .finally(() => setLoading(false)),
    [],
  )

  useEffect(() => {
    load()
  }, [load])

  // Новые с прошлого захода — салют и пометка «Новая» на карточке.
  // В первый заход запоминаем всё молча: старые нашивки не новость.
  const greeted = useRef(false)
  useEffect(() => {
    if (loading || loadError || greeted.current) return
    greeted.current = true
    const codes = earned.map((row) => row.badge.code)
    const seen = readSeen()
    writeSeen(codes)
    if (!seen) return
    const added = codes.filter((code) => !seen.has(code))
    if (added.length === 0) return
    const timer = window.setTimeout(() => {
      setFresh(new Set(added))
      celebrate(added.length > 1 ? 'big' : 'small')
    }, 500)
    return () => window.clearTimeout(timer)
  }, [loading, loadError, earned])

  const earnedByCode = useMemo(
    () => new Map(earned.map((row) => [row.badge.code, row])),
    [earned],
  )

  const categories = useMemo(() => {
    const codes = new Set(catalog.map((badge) => badge.category).filter(Boolean))
    return [...codes]
  }, [catalog])

  const inCategory = useMemo(
    () => catalog.filter((badge) => !category || badge.category === category),
    [catalog, category],
  )

  const counts = useMemo(() => {
    const got = inCategory.filter((badge) => earnedByCode.has(badge.code)).length
    return { all: inCategory.length, earned: got, locked: inCategory.length - got }
  }, [inCategory, earnedByCode])

  const visible = useMemo(() => {
    const rows = inCategory.filter((badge) => {
      const isEarned = earnedByCode.has(badge.code)
      if (filter === 'earned') return isEarned
      if (filter === 'locked') return !isEarned
      return true
    })
    // Полученные сверху, дальше по редкости: так видно и достижения, и цель.
    return rows.sort((a, b) => {
      const gotA = earnedByCode.has(a.code) ? 0 : 1
      const gotB = earnedByCode.has(b.code) ? 0 : 1
      if (gotA !== gotB) return gotA - gotB
      return RARITY_ORDER.indexOf(a.rarity) - RARITY_ORDER.indexOf(b.rarity)
    })
  }, [inCategory, filter, earnedByCode])

  // Ближайшая цель — самая доступная из неполученных
  const nextGoal = useMemo(
    () =>
      catalog
        .filter((badge) => !earnedByCode.has(badge.code))
        .sort((a, b) => RARITY_ORDER.indexOf(a.rarity) - RARITY_ORDER.indexOf(b.rarity))[0],
    [catalog, earnedByCode],
  )

  const pinned = useMemo(() => earned.filter((row) => row.is_pinned), [earned])

  const togglePin = (badge: Badge) => {
    const row = earnedByCode.get(badge.code)
    if (!row || pinning) return
    setPinning(true)
    const request = row.is_pinned
      ? api.delete(`/api/v1/badges/${encodeURIComponent(badge.code)}/pin/`)
      : api.post(`/api/v1/badges/${encodeURIComponent(badge.code)}/pin/`)
    request
      .then(() => {
        addToast(row.is_pinned ? 'Нашивка откреплена' : 'Нашивка закреплена', 'success')
        return load()
      })
      .catch(() => addToast('Не удалось изменить нашивку', 'error'))
      .finally(() => setPinning(false))
  }

  const closeSheet = useCallback(() => setOpenCode(null), [])

  if (loading) {
    return (
      <div className="bd">
        <BrandLoader label="Загружаем нашивки" />
      </div>
    )
  }

  if (loadError) {
    return (
      <LoadError
        className="bd bd--state"
        onRetry={() => {
          setLoading(true)
          load()
        }}
      />
    )
  }

  const total = catalog.length
  const percent = total ? Math.round((earned.length / total) * 100) : 0
  const openBadge = openCode ? catalog.find((badge) => badge.code === openCode) ?? null : null

  return (
    <div className="bd page-enter">
      <div className="bd-toasts">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast--${toast.type}`}>{toast.message}</div>
        ))}
      </div>

      <div className="bd__main">
        <div className="q1__tabs-card bd__tabs">
          <div className="q1__tabs-row" ref={tabsRef} role="tablist" aria-label="Какие нашивки показать">
            {FILTERS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                ref={registerTab(value)}
                aria-selected={filter === value}
                className={`q1__tab${filter === value ? ' q1__tab--active' : ''} btn-press`}
                onClick={() => setFilter(value)}
              >
                {label}
                <span className="bd__tab-count">{counts[value]}</span>
              </button>
            ))}
          </div>
          <div className="q1__tabs-track" aria-hidden="true">
            <span className="q1__tabs-line" />
            <span className="q1__tabs-pill" style={{ left: indicator.left, width: indicator.width }} />
          </div>
        </div>

        <section className="bd__slot">
          <h2 className="bd__slot-title">
            Коллекция
            <span className="bd__slot-count">{visible.length}</span>
          </h2>

          {visible.length === 0 ? (
            <div className="bd__empty">
              <BadgeEmblem code="empty" rarity="common" locked size={64} />
              <p>
                {filter === 'earned'
                  ? 'Здесь появятся полученные нашивки. Начни с ближайшей цели справа.'
                  : 'Все нашивки этой категории уже твои.'}
              </p>
            </div>
          ) : (
            <div className="bd__grid" key={`${filter}-${category}`}>
              {visible.map((badge, i) => {
                const row = earnedByCode.get(badge.code)
                const isEarned = Boolean(row)
                const isFresh = fresh.has(badge.code)
                return (
                  <button
                    key={badge.code}
                    type="button"
                    className={`bd-card bd-card--${badge.rarity}${isEarned ? '' : ' bd-card--locked'}${isFresh ? ' bd-card--fresh' : ''}`}
                    style={{ animationDelay: `${Math.min(i, 11) * 45}ms` }}
                    onClick={() => setOpenCode(badge.code)}
                    aria-haspopup="dialog"
                    {...tiltHandlers()}
                  >
                    <span className="bd-card__emblem">
                      <BadgeEmblem code={badge.code} rarity={badge.rarity} locked={!isEarned} size={76} />
                      {row?.is_pinned && <span className="bd-card__pin">В профиле</span>}
                    </span>
                    <span className="bd-card__text">
                      <span className="bd-card__title">{badge.title}</span>
                      <span className="bd-card__desc">{badge.description || 'Условие уточняется'}</span>
                    </span>
                    <span className="bd-card__meta">
                      <span className={`bd-chip bd-chip--${badge.rarity}`}>
                        {RARITY_LABELS[badge.rarity] ?? badge.rarity}
                      </span>
                      {badge.reward_coins > 0 && (
                        <span className="bd-coins"><i aria-hidden="true" />+{badge.reward_coins}</span>
                      )}
                    </span>
                    <span className="bd-card__foot">
                      {isFresh && <span className="bd-new">Новая</span>}
                      {isEarned ? `Получена ${shortDate(row!.acquired_at)}` : 'Ещё не получена'}
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </section>
      </div>

      <section className="bd-summary" aria-label="Прогресс коллекции">
        <h2 className="bd-summary__title">Собрано:</h2>
        <div className="bd-summary__plate">
          <strong>{earned.length}</strong>
          <span>из {total}</span>
        </div>
        {total > 0 && total <= 48 ? (
          <div className="bd-summary__cells" aria-hidden="true">
            {catalog.map((badge, i) => (
              <i
                key={badge.code}
                className={earnedByCode.has(badge.code) ? 'is-on' : ''}
                style={{ animationDelay: `${300 + i * 35}ms` }}
              />
            ))}
          </div>
        ) : (
          <div className="bd-summary__bar" aria-hidden="true">
            <span style={{ width: `${percent}%` }} />
          </div>
        )}
        <p className="bd-summary__percent">{percent}% коллекции</p>

        {nextGoal && (
          <button type="button" className="bd-goal" onClick={() => setOpenCode(nextGoal.code)} aria-haspopup="dialog">
            <BadgeEmblem code={nextGoal.code} rarity={nextGoal.rarity} size={52} />
            <span className="bd-goal__text">
              <span className="bd-goal__label">Ближайшая цель</span>
              <span className="bd-goal__title">{nextGoal.title}</span>
            </span>
            {nextGoal.reward_coins > 0 && (
              <span className="bd-coins bd-coins--small"><i aria-hidden="true" />+{nextGoal.reward_coins}</span>
            )}
          </button>
        )}
      </section>

      <div className="bd-side">
        {categories.length > 1 && (
          <section className="bd-side__card">
            <h3 className="bd-side__title">Категории</h3>
            <div className="bd-cats" role="tablist" aria-label="Категория">
              {[['', 'Все'] as const, ...categories.map((code) => [code, CATEGORY_LABELS[code] ?? code] as const)].map(
                ([code, label]) => (
                  <button
                    key={code || 'all'}
                    type="button"
                    role="tab"
                    aria-selected={category === code}
                    className={`bd-cat${category === code ? ' bd-cat--active' : ''} btn-press`}
                    onClick={() => setCategory(code)}
                  >
                    {label}
                  </button>
                ),
              )}
            </div>
          </section>
        )}

        <section className="bd-side__card bd-side__card--pinned">
          <h3 className="bd-side__title">В профиле</h3>
          {pinned.length > 0 ? (
            <div className="bd-pinned">
              {pinned.map((row) => (
                <button
                  key={row.badge.code}
                  type="button"
                  className="bd-pinned__item"
                  onClick={() => setOpenCode(row.badge.code)}
                  title={row.badge.title}
                  aria-label={row.badge.title}
                >
                  <BadgeEmblem code={row.badge.code} rarity={row.badge.rarity} size={56} />
                </button>
              ))}
            </div>
          ) : (
            <p className="bd-side__hint">Открой полученную нашивку и закрепи её — она появится в профиле.</p>
          )}
        </section>
      </div>

      <BadgeSheet
        badge={openBadge}
        earned={openBadge ? earnedByCode.get(openBadge.code) : undefined}
        isNew={openBadge ? fresh.has(openBadge.code) : false}
        pinning={pinning}
        onClose={closeSheet}
        onTogglePin={togglePin}
      />
    </div>
  )
}
