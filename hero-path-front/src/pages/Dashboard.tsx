import { useState, useEffect, useCallback } from 'react'
import seriesIcon from '../assets/other/Group 11.svg'
import LoadError from '../components/LoadError'
import api from '../api'
import { useToasts } from '../useToasts'
import { formatDateTimeRu, formatRating, unwrapList } from '../lib/apiData'
import RollNumber from '../components/RollNumber'
import CharacteristicsRadar, { type CharacteristicItem } from '../components/CharacteristicsRadar'
import PixelText from '../components/PixelText'
import ActiveBoostNotice from '../components/BoostPlaque'
import '../styles/dashboard.css'

interface DashboardData {
  // false до запуска платформы: ничего не начисляется
  accruals_enabled?: boolean
  user: {
    callsign: string
    level: number
    rating_current: number
    skills?: Record<string, number>
    skills_peak?: Record<string, number>
  }
  current_quest: {
    code: string
    title: string
    quest_type: string
    progress_value: number
    reward_coins: number
    auto_verify?: boolean
    manual_complete_allowed?: boolean
    verification_message?: string
  } | null
  strike?: {
    late_strike: number
    bonus_at_7: number
    bonus_at_14: number
    bonus_at_21: number
    overall_progress_percent: number
  } | null
  rating_progress?: {
    zone_label: string
    next_zone_label: string | null
    points_to_next: number
    progress_percent: number
  } | null
  feed: { text: string; time: string }[]
}

/* ---------- маленькие хуки для "живости" интерфейса ---------- */

/* ---------- подсветка в ленте активности ----------
   в макете внутри строки фиолетовым выделены <нашивка>, @ник и награда «+N монет» */

const FEED_HIGHLIGHT = /(<[^>]+>|@[a-zа-яё\d_.-]+|\+\d+\s+монет[а-яё]*)/iu

function FeedText({ text }: { text: string }) {
  const parts = text.split(new RegExp(FEED_HIGHLIGHT.source, 'giu'))
  return (
    <span>
      {parts.map((part, i) =>
        FEED_HIGHLIGHT.test(part) ? (
          <mark
            key={i}
            className={`activity__mark${part.startsWith('@') ? ' activity__mark--user' : ''}`}
          >
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </span>
  )
}

export default function Dashboard() {
  const [characteristics, setCharacteristics] = useState<CharacteristicItem[]>([])
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  const { toasts, addToast } = useToasts()

  // quiet — обновить после действия без лоадера на весь экран
  const loadDashboard = useCallback(({ quiet = false }: { quiet?: boolean } = {}) => {
    // Пятиугольник тот же, что в профиле, — и данные те же. Ошибка тут не
    // ломает главную: без характеристик пятиугольник просто не рисуется.
    api.get('/api/v1/profile/me/characteristics/')
      .then(res => setCharacteristics(unwrapList<CharacteristicItem>(res.data)))
      .catch(() => setCharacteristics([]))
    api.get('/api/v1/dashboard/')
      .then(res => setData(res.data))
      .catch(() => {
        if (quiet) {
          addToast('Не удалось обновить главную', 'error')
          return
        }
        setData(null)
        setLoadError(true)
        addToast('Не удалось загрузить дашборд', 'error')
      })
      .finally(() => setLoading(false))
  }, [addToast])

  // «Загружается» при первом показе уже стоит в начальном состоянии;
  // повтор ставит его сам. Синхронный setState в эффекте давал лишний
  // каскадный рендер.
  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  const retryDashboard = () => {
    setLoadError(false)
    setLoading(true)
    loadDashboard()
  }

  // Цепочка обрывалась после data?: ответ без user ронял страницу в белый экран
  const rating = data?.user?.rating_current ?? 0
  const level = data?.user?.level ?? 0

  if (loadError) {
    return (
      <div className="dashboard page-enter">
        <LoadError className="profile-loading" onRetry={retryDashboard} />
      </div>
    )
  }

  if (loading || !data) {
    return (
      <div className="dashboard page-enter">
        <div className="profile-loading">
          <div className="loading-spinner">
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
          </div>
          <p className="loading-text">Загрузка дашборда...</p>
        </div>
      </div>
    )
  }

  const strike = data?.strike
  const lateDays = strike?.late_strike ?? 0
  const strikeProgress = strike?.overall_progress_percent ?? 0
  const ratingProgress = data?.rating_progress
  const activity = data?.feed ?? []

  return (
    <div className="dashboard dashboard--home page-enter">
      <div className="dash-glow dash-glow--a" aria-hidden="true" />
      <div className="dash-glow dash-glow--b" aria-hidden="true" />

      <ActiveBoostNotice />

      {data?.accruals_enabled === false && (
        <p className="dashboard__accruals-notice" role="status">
          Начисления стартуют с запуска платформы
        </p>
      )}

      <div className="dashboard__top">
        <div className="dashboard__left-col">
          <section className="card card--light dash-in" style={{ animationDelay: '0ms' }}>
            <div className="series__header">
              <img className="series__icon-image" src={seriesIcon} alt="" aria-hidden="true" />
              <div className="series__title-wrap">
                <h3><PixelText text="Серия:" /></h3>
                <p>{lateDays} {lateDays === 1 ? 'день' : lateDays >= 2 && lateDays <= 4 ? 'дня' : 'дней'} без опозданий</p>
              </div>
            </div>
            <div className="series__meta series__meta--top">
              <span>7 дней</span><span>14 дней</span>
            </div>
            <div className="series__progress-row">
              <span className="series__circle series__circle--left" />
              <div className="series__progress">
                <div className="series__progress-fill" style={{ width: `${Math.min(100, strikeProgress)}%` }} />
              </div>
              <span className="series__circle series__circle--right" />
            </div>
            <div className="series__meta series__meta--bottom">
              <span>+{strike?.bonus_at_7 ?? 5} монет</span><span>+{strike?.bonus_at_21 ?? 15} монет</span>
            </div>
          </section>

          <section className="card card--purple dash-in" style={{ animationDelay: '90ms' }}>
            <h3 className="rating__title"><PixelText text="Текущий рейтинг:" /></h3>
            <div className="rating__value"><RollNumber value={formatRating(rating)} /></div>
            <div className="rating__line">
              <span>Статус:</span>
              <span className="chip chip--light rating__chip">{ratingProgress?.zone_label ?? '—'}</span>
              <span className="chip chip--light rating__chip">{level} ур.</span>
            </div>
            {ratingProgress?.next_zone_label && (
              <>
                <div className="rating__line">
                  <span>до</span>
                  <span className="chip chip--dark rating__chip rating__chip--leader">{ratingProgress.next_zone_label}</span>
                  <span>осталось:</span>
                </div>
                <span className="chip chip--light rating__target">{ratingProgress.points_to_next} баллов</span>
              </>
            )}
            <div className="rating__progress-row">
              <span className="rating__circle rating__circle--left" />
              <div className="rating__progress">
                <div
                  className="rating__progress-fill"
                  style={{ width: `${Math.min(100, ratingProgress?.progress_percent ?? 0)}%` }}
                />
              </div>
              <span className="rating__circle rating__circle--right" />
            </div>
            <div className="rating__meta">
              <span>{ratingProgress?.zone_label ?? '—'}</span>
              <span>{ratingProgress?.next_zone_label ?? 'Макс.'}</span>
            </div>
          </section>
        </div>

        <CharacteristicsRadar
          characteristics={characteristics}
          className="dash-in profile-radar--compact"
          style={{ animationDelay: '160ms' }}
        />
      </div>

      <div className="dashboard__bottom">
        <section className="activity-card dash-in" style={{ animationDelay: '240ms' }}>
          <h3 className="section-title">
            <span className="live-dot" aria-hidden="true" />
            <PixelText text="Лента активности" />
          </h3>
          <div className="activity">
            {activity.length === 0 ? (
              <p className="loading-text" style={{ padding: '12px 0' }}>Лента пока пуста</p>
            ) : activity.map((item, i) => (
              <article
                key={`${item.text}-${i}`}
                className="activity__item dash-in-item spot"
                style={{ animationDelay: `${320 + i * 80}ms` }}
              >
                <FeedText text={item.text} />
                <time dateTime={item.time}>{formatDateTimeRu(item.time)}</time>
              </article>
            ))}
          </div>
        </section>

      </div>

      {/* Тосты */}
      <div className="toast-container toast-container--fixed-right">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast--${toast.type}`}>
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  )
}