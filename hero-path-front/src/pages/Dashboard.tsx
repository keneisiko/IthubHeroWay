import { useState, useEffect, useRef, useCallback } from 'react'
import { Radar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from 'chart.js'
import seriesIcon from '../assets/other/Group 11.svg'
import LoadError from '../components/LoadError'
import api from '../api'
import { useToasts } from '../useToasts'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

const AXIS_LABELS = ['Ритм', 'Фокус', 'Мощность', 'Связь', 'Отдача']

const radarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      beginAtZero: true,
      max: 100,
      // в макете пятиугольник состоит ровно из 5 колец
      ticks: { display: false, stepSize: 20 },
      grid: { color: 'rgba(154, 51, 244, 0.55)', lineWidth: 3, circular: false },
      angleLines: { color: 'rgba(154, 51, 244, 0.55)', lineWidth: 3 },
      pointLabels: { display: false },
    },
  },
  layout: { padding: 0 },
  elements: { line: { tension: 0 } },
  animation: { duration: 1100, easing: 'easeOutExpo' as const },
  plugins: { legend: { display: false } },
}

type QuestTab = 'daily' | 'weekly'

interface DashboardData {
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

// плавный счётчик — рейтинг "доезжает" до значения, а не появляется сразу
function useCountUp(target: number, duration = 1100) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    let raf = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic
      setValue(Math.round(target * eased))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return value
}

// модалка с нормальным закрытием — фейд-аут, а не мгновенное исчезновение
function useDismissable() {
  const [open, setOpen] = useState(false)
  const [closing, setClosing] = useState(false)
  const show = () => { setClosing(false); setOpen(true) }
  const hide = () => {
    setClosing(true)
    setTimeout(() => { setOpen(false); setClosing(false) }, 220)
  }
  return { open, closing, show, hide }
}

// лёгкий 3D-tilt по курсору на карточке радара
function useTilt(maxDeg = 7) {
  const ref = useRef<HTMLDivElement>(null)
  const onMouseMove = (e: React.MouseEvent) => {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width - 0.5
    const y = (e.clientY - rect.top) / rect.height - 0.5
    el.style.transform = `perspective(900px) rotateX(${(-y * maxDeg).toFixed(2)}deg) rotateY(${(x * maxDeg).toFixed(2)}deg)`
  }
  const onMouseLeave = () => {
    const el = ref.current
    if (el) el.style.transform = 'perspective(900px) rotateX(0deg) rotateY(0deg)'
  }
  return { ref, onMouseMove, onMouseLeave }
}

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

/* ---------- общая модалка вместо двух дублей ---------- */

function LinkModal({
  open, closing, label, value, placeholder, onChange, onClose, onSubmit,
}: {
  open: boolean
  closing: boolean
  label: string
  value: string
  placeholder: string
  onChange: (v: string) => void
  onClose: () => void
  onSubmit: () => void
}) {
  if (!open) return null
  return (
    <div className={`overlay${closing ? ' overlay--closing' : ''}`} onClick={onClose}>
      <div
        className={`popup popup--link${closing ? ' popup--closing' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <label className="popup__label">{label}</label>
        <input
          type="url"
          autoFocus
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="popup__input"
        />
        <button type="button" className="popup__submit btn-press" onClick={onSubmit}>
          Отправить
        </button>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [hoveredRadar, setHoveredRadar] = useState<string | null>(null)
  const confirm = useDismissable()
  const report = useDismissable()
  const [confirmLink, setConfirmLink] = useState('')
  const [reportText, setReportText] = useState('')
  const [questTab, setQuestTab] = useState<QuestTab>('daily')
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const tilt = useTilt()
  const { toasts, addToast } = useToasts()

  const loadDashboard = useCallback(() => {
    setLoadError(false)
    setLoading(true)
    api.get('/api/v1/dashboard/')
      .then(res => setData(res.data))
      .catch(() => {
        setData(null)
        setLoadError(true)
        addToast('Не удалось загрузить дашборд', 'error')
      })
      .finally(() => setLoading(false))
  }, [addToast])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  const rating = data?.user.rating_current ?? 0
  const ratingDisplay = useCountUp(rating)
  const level = data?.user.level ?? 0
  const questTitle = data?.current_quest?.title ?? 'На сегодня всё. Отдыхай.'
  const questProgress = data?.current_quest?.progress_value ?? 0
  const hasQuest = Boolean(data?.current_quest)
  const isDaily = data?.current_quest?.quest_type === 'daily'
  const questAutoVerify = data?.current_quest?.auto_verify ?? false
  const questManualAllowed = data?.current_quest?.manual_complete_allowed !== false

  if (loadError) {
    return (
      <div className="dashboard page-enter">
        <LoadError className="profile-loading" onRetry={loadDashboard} />
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

  const radarValues = AXIS_LABELS.map(label =>
    data?.user?.skills?.[label] ?? 0
  )
  const radarPeakValues = AXIS_LABELS.map(label =>
    data?.user?.skills_peak?.[label] ?? radarValues[AXIS_LABELS.indexOf(label)] ?? 0
  )
  const strike = data?.strike
  const lateDays = strike?.late_strike ?? 0
  const strikeProgress = strike?.overall_progress_percent ?? 0
  const ratingProgress = data?.rating_progress
  const radarData = {
    labels: AXIS_LABELS,
    datasets: [
      {
        label: 'Текущий',
        data: radarValues,
        backgroundColor: 'rgba(154, 51, 244, 0.18)',
        borderColor: '#9A33F4',
        borderWidth: 5,
        pointBackgroundColor: '#f5f5f5',
        pointBorderColor: '#9A33F4',
        pointBorderWidth: 5,
        pointRadius: 9,
        pointHoverRadius: 12,
      },
      {
        label: 'Пик',
        data: radarPeakValues,
        backgroundColor: 'rgba(154, 51, 244, 0.08)',
        borderColor: 'rgba(154, 51, 244, 0.65)',
        borderWidth: 3,
        borderDash: [8, 7],
        pointRadius: 0,
      },
    ],
  }

  const activity = data?.feed ?? []

  return (
    <div className="dashboard page-enter">
      <div className="dash-glow dash-glow--a" aria-hidden="true" />
      <div className="dash-glow dash-glow--b" aria-hidden="true" />

      <div className="dashboard__top">
        <div className="dashboard__left-col">
          <section className="card card--light dash-in" style={{ animationDelay: '0ms' }}>
            <div className="series__header">
              <img className="series__icon-image" src={seriesIcon} alt="" aria-hidden="true" />
              <div className="series__title-wrap">
                <h3>Серия:</h3>
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
            <h3 className="rating__title">Текущий рейтинг:</h3>
            <div className="rating__value">{ratingDisplay}</div>
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

        <section
          className="radar-card dash-in"
          style={{ animationDelay: '160ms' }}
          onMouseMove={tilt.onMouseMove}
          onMouseLeave={() => { tilt.onMouseLeave(); setHoveredRadar(null) }}
        >
          <div className="radar-card__tilt" ref={tilt.ref}>
            <span className="radar-card__label">
              {hoveredRadar ? `${hoveredRadar}: ${radarValues[AXIS_LABELS.indexOf(hoveredRadar)]}%` : 'Ритм'}
            </span>
            <div className="radar-card__canvas">
              <Radar
                data={radarData}
                options={{
                  ...radarOptions,
                  plugins: {
                    legend: { display: false },
                    tooltip: {
                      enabled: true,
                      backgroundColor: '#9a33f4',
                      titleFont: { family: 'TT Firs Neue', size: 16, weight: 700 },
                      bodyFont: { family: 'Montserrat', size: 14 },
                      padding: 10,
                      cornerRadius: 12,
                      displayColors: false,
                      callbacks: {
                        title: (items: any) => items[0]?.label || '',
                        label: (item: any) =>
                          item.datasetIndex === 0 ? `Текущий: ${item.raw}%` : `Пик: ${item.raw}%`,
                      },
                    },
                  },
                  onHover: (_: any, elements: any[]) => {
                    if (elements.length > 0 && elements[0].datasetIndex === 0) {
                      setHoveredRadar(AXIS_LABELS[elements[0].index])
                    } else {
                      setHoveredRadar(null)
                    }
                  },
                }}
              />
            </div>
          </div>
        </section>
      </div>

      <div className="dashboard__bottom">
        <section className="activity-card dash-in" style={{ animationDelay: '240ms' }}>
          <h3 className="section-title">
            <span className="live-dot" aria-hidden="true" />
            Лента активности
          </h3>
          <div className="activity">
            {activity.length === 0 ? (
              <p className="loading-text" style={{ padding: '12px 0' }}>Лента пока пуста</p>
            ) : activity.map((item, i) => (
              <article
                key={`${item.text}-${i}`}
                className="activity__item dash-in-item"
                style={{ animationDelay: `${320 + i * 80}ms` }}
              >
                <FeedText text={item.text} />
                <time>{item.time}</time>
              </article>
            ))}
          </div>
        </section>

        <section className="quest dash-in" style={{ animationDelay: '320ms' }}>
          <h3>Активный квест</h3>
          {!hasQuest ? (
            <p className="loading-text" style={{ padding: '16px 0' }}>На сегодня всё. Отдыхай.</p>
          ) : (
          <>
          <div className="quest__tabs">
            <button
              className={`quest__tab${questTab === 'daily' ? ' quest__tab--active' : ''}`}
              onClick={() => setQuestTab('daily')}
            >Ежедневный</button>
            <button
              className={`quest__tab${questTab === 'weekly' ? ' quest__tab--active' : ''}`}
              onClick={() => setQuestTab('weekly')}
            >Еженедельный</button>
          </div>
          <div className="quest__progress">
            <div className="quest__progress-inner">
              <div className="quest__head">
                <span>{isDaily ? questTitle : 'Завершить 5 задач'}</span>
                <strong>{questProgress}%</strong>
              </div>
              <div className="quest__steps">
                <span className="quest-step"><span className="dot dot--red" /><span className="quest-step__bar quest-step__bar--red" /></span>
                <span className="quest-step"><span className="dot dot--yellow" /><span className="quest-step__bar quest-step__bar--yellow" /></span>
                <span className="quest-step"><span className="dot dot--blue" /><span className="quest-step__bar quest-step__bar--blue" /></span>
                <span className="dot dot--green" />
              </div>
            </div>
          </div>
          <button
            className="quest__confirm btn-press"
            onClick={confirm.show}
            disabled={questAutoVerify || !questManualAllowed}
          >
            {questAutoVerify ? 'Проверяется автоматически' : 'Подтвердить'}
          </button>
          {questAutoVerify && data?.current_quest?.verification_message && (
            <p className="loading-text" style={{ marginTop: 8 }}>{data.current_quest.verification_message}</p>
          )}
          <div className="quest__row">
            <span>Текст</span><span>+</span>
          </div>
          <button className="quest__self btn-press" onClick={report.show}>Самоотчёт</button>
          </>
          )}
        </section>
      </div>

      <LinkModal
        open={confirm.open}
        closing={confirm.closing}
        label="Прикрепите подтверждение выполнения"
        value={confirmLink}
        placeholder="Ссылка на доказательство"
        onChange={setConfirmLink}
        onClose={confirm.hide}
        onSubmit={() => {
          const code = data?.current_quest?.code
          if (!code) {
            addToast('Нет активного квеста', 'error')
            return
          }
          const proof = confirmLink.trim() ? { link: confirmLink.trim() } : {}
          api.post(`/api/v1/quests/${code}/complete/`, { proof_payload: proof })
            .then(() => { confirm.hide(); setConfirmLink(''); addToast('Квест подтверждён!', 'success'); loadDashboard() })
            .catch(() => addToast('Ошибка подтверждения', 'error'))
        }}
      />

      <LinkModal
        open={report.open}
        closing={report.closing}
        label="Ссылка на работу"
        value={reportText}
        placeholder="https://..."
        onChange={setReportText}
        onClose={report.hide}
        onSubmit={() => {
          const code = data?.current_quest?.code
          if (!code) {
            addToast('Нет квеста для самоотчёта', 'error')
            return
          }
          const comment = reportText.trim()
          if (comment.length < 10) {
            addToast('Комментарий минимум 10 символов', 'error')
            return
          }
          api.post(`/api/v1/quests/${code}/self-report/`, { comment })
            .then(() => { report.hide(); setReportText(''); addToast('Самоотчёт отправлен!', 'success') })
            .catch(() => addToast('Ошибка отправки', 'error'))
        }}
      />

      {/* Тосты */}
      <div className="toast-container toast-container--fixed-right">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast--${toast.type}`}>
            {toast.type === 'success' ? '✓ ' : '✕ '}
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  )
}