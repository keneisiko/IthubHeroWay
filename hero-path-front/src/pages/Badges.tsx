import { useCallback, useEffect, useMemo, useState } from 'react'
import api from '../api'
import LoadError from '../components/LoadError'
import { useToasts } from '../useToasts'
import { RARITY_LABELS, formatDateRu, unwrapList } from '../lib/apiData'

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

export default function Badges() {
  const [catalog, setCatalog] = useState<Badge[]>([])
  const [earned, setEarned] = useState<EarnedBadge[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [category, setCategory] = useState<string>('')
  const { toasts, addToast } = useToasts()

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

  const earnedByCode = useMemo(
    () => new Map(earned.map((row) => [row.badge.code, row])),
    [earned],
  )

  const categories = useMemo(() => {
    const codes = new Set(catalog.map((badge) => badge.category).filter(Boolean))
    return [...codes]
  }, [catalog])

  const visible = useMemo(() => {
    const rows = catalog.filter((badge) => {
      if (category && badge.category !== category) return false
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
  }, [catalog, category, filter, earnedByCode])

  const togglePin = (badge: Badge) => {
    const row = earnedByCode.get(badge.code)
    if (!row) return
    const request = row.is_pinned
      ? api.delete(`/api/v1/badges/${encodeURIComponent(badge.code)}/pin/`)
      : api.post(`/api/v1/badges/${encodeURIComponent(badge.code)}/pin/`)
    request
      .then(() => {
        addToast(row.is_pinned ? 'Нашивка откреплена' : 'Нашивка закреплена', 'success')
        return load()
      })
      .catch(() => addToast('Не удалось изменить нашивку', 'error'))
  }

  if (loading) {
    return (
      <div className="badges-page">
        <div className="loading-spinner">
          <span className="loading-spinner-dot" />
          <span className="loading-spinner-dot" />
          <span className="loading-spinner-dot" />
        </div>
        <p className="loading-text">Загрузка...</p>
      </div>
    )
  }

  if (loadError) {
    return (
      <LoadError
        className="badges-page"
        onRetry={() => {
          setLoading(true)
          load()
        }}
      />
    )
  }

  const percent = catalog.length ? Math.round((earned.length / catalog.length) * 100) : 0

  return (
    <div className="badges-page page-enter">
      <div className="badges-toasts">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast--${toast.type}`}>{toast.message}</div>
        ))}
      </div>

      <section className="badges-head card-entrance">
        <h1 className="badges-head__title">Нашивки</h1>
        <p className="badges-head__count">
          Получено <strong>{earned.length}</strong> из <strong>{catalog.length}</strong>
        </p>
        <div className="badges-head__bar">
          <div className="badges-head__fill" style={{ width: `${percent}%` }} />
        </div>
      </section>

      <div className="badges-filters">
        <div className="badges-filters__group" role="tablist" aria-label="Состояние">
          {([
            ['all', 'Все'],
            ['earned', 'Полученные'],
            ['locked', 'Осталось получить'],
          ] as [Filter, string][]).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={filter === value}
              className={`badges-chip${filter === value ? ' badges-chip--active' : ''} btn-press`}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>

        {categories.length > 1 && (
          <div className="badges-filters__group" role="tablist" aria-label="Категория">
            <button
              type="button"
              role="tab"
              aria-selected={category === ''}
              className={`badges-chip${category === '' ? ' badges-chip--active' : ''} btn-press`}
              onClick={() => setCategory('')}
            >
              Все категории
            </button>
            {categories.map((code) => (
              <button
                key={code}
                type="button"
                role="tab"
                aria-selected={category === code}
                className={`badges-chip${category === code ? ' badges-chip--active' : ''} btn-press`}
                onClick={() => setCategory(code)}
              >
                {CATEGORY_LABELS[code] ?? code}
              </button>
            ))}
          </div>
        )}
      </div>

      {visible.length === 0 ? (
        <p className="badges-empty">Здесь пока пусто</p>
      ) : (
        <div className="badges-grid">
          {visible.map((badge, i) => {
            const row = earnedByCode.get(badge.code)
            const isEarned = Boolean(row)
            return (
              <article
                key={badge.code}
                className={`badge-card${isEarned ? '' : ' badge-card--locked'} card-entrance`}
                style={{ animationDelay: `${Math.min(i, 12) * 50}ms` }}
              >
                <div className={`badge-card__icon badge-card__icon--${badge.rarity}`} aria-hidden="true" />
                <h3 className="badge-card__title">{badge.title}</h3>
                <p className="badge-card__desc">{badge.description || 'Условие уточняется'}</p>

                <div className="badge-card__meta">
                  <span className={`badge-card__rarity badge-card__rarity--${badge.rarity}`}>
                    {RARITY_LABELS[badge.rarity] ?? badge.rarity}
                  </span>
                  {badge.reward_coins > 0 && (
                    <span className="badge-card__coins">+{badge.reward_coins} монет</span>
                  )}
                </div>

                {isEarned ? (
                  <div className="badge-card__footer">
                    <span className="badge-card__date">
                      Получена {formatDateRu(row!.acquired_at)}
                    </span>
                    <button
                      type="button"
                      className="badge-card__pin btn-press"
                      onClick={() => togglePin(badge)}
                    >
                      {row!.is_pinned ? 'Открепить' : 'Закрепить'}
                    </button>
                  </div>
                ) : (
                  <div className="badge-card__footer">
                    <span className="badge-card__date badge-card__date--locked">Ещё не получена</span>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
