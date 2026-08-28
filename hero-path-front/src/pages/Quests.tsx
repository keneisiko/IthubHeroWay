import { useState, useEffect, useCallback, useRef } from 'react'
import api from '../api'
import LoadError from '../components/LoadError'
import { useTabIndicator } from '../useTabIndicator'
import seriesIcon from '../assets/other/Group 11.svg'
import {
  mapCompletedQuests,
  mapRewardActivities,
  mapRecentRewardActivities,
  mergeActiveQuests,
  pickSelfReportQuestCode,
  type UiQuest,
} from '../lib/quests'

const TABS = ['Активные', 'Выполненные', 'История наград'] as const

interface Activity {
  id: number
  title: string
  reward: string
  time: string
}

function useModal(initial = false) {
  const [open, setOpen] = useState(initial)
  const ref = useRef<HTMLDivElement>(null)
  const show = () => setOpen(true)
  const hide = () => setOpen(false)

  useEffect(() => {
    if (!open) return
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') hide() }
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) hide()
    }
    document.addEventListener('keydown', handleEsc)
    document.addEventListener('mousedown', handleClick)
    return () => {
      document.removeEventListener('keydown', handleEsc)
      document.removeEventListener('mousedown', handleClick)
    }
  }, [open])

  return { open, ref, show, hide }
}

// Склонение дней для подписи серии
function dayWord(days: number) {
  if (days === 1) return 'день'
  if (days >= 2 && days <= 4) return 'дня'
  return 'дней'
}

export default function Quests() {
  const [activeTab, setActiveTab] = useState(0)
  const [quests, setQuests] = useState<UiQuest[]>([])
  const [completedQuests, setCompletedQuests] = useState<UiQuest[]>([])
  const [activity, setActivity] = useState<Activity[]>([])
  const [recentActivity, setRecentActivity] = useState<Activity[]>([])
  const [selfReportQuestCode, setSelfReportQuestCode] = useState<string | null>(null)
  const [strike, setStrike] = useState<{
    late_strike: number
    bonus_at_7: number
    bonus_at_21: number
    overall_progress_percent: number
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const tabIndicator = useTabIndicator(activeTab, loading)
  const [loadError, setLoadError] = useState(false)
  const [toasts, setToasts] = useState<{ id: number; message: string; type: 'success' | 'error' }[]>([])

  const reportModal = useModal()
  const confirmModal = useModal()
  const [reportText, setReportText] = useState('')
  const [confirmQuestCode, setConfirmQuestCode] = useState<string | null>(null)
  const [confirmLink, setConfirmLink] = useState('')

  const addToast = (message: string, type: 'success' | 'error' = 'success') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3000)
  }

  const loadQuests = useCallback(() => {
    setLoading(true)
    setLoadError(false)
    Promise.all([
      api.get('/api/v1/quests/active/'),
      api.get('/api/v1/quests/my-progress/', { params: { completed: false } }),
      api.get('/api/v1/quests/my-progress/', { params: { completed: true } }),
      api.get('/api/v1/quests/rewards/history/'),
      api.get('/api/v1/dashboard/'),
    ]).then(([activeRes, progressRes, completedRes, historyRes, dashRes]) => {
      setQuests(mergeActiveQuests(activeRes.data, progressRes.data))
      setCompletedQuests(mapCompletedQuests(completedRes.data))
      setActivity(mapRewardActivities(historyRes.data))
      setRecentActivity(mapRecentRewardActivities(historyRes.data))
      setSelfReportQuestCode(pickSelfReportQuestCode(activeRes.data))
      setStrike(dashRes.data?.strike ?? null)
    }).catch(() => {
      setQuests([])
      setCompletedQuests([])
      setActivity([])
      setLoadError(true)
    }).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadQuests()
  }, [loadQuests])

  const handleReportSubmit = useCallback(() => {
    if (!selfReportQuestCode) {
      addToast('Нет квеста для самоотчёта', 'error')
      return
    }
    const comment = reportText.trim()
    if (comment.length < 10) {
      addToast('Комментарий минимум 10 символов', 'error')
      return
    }
    api.post(`/api/v1/quests/${selfReportQuestCode}/self-report/`, { comment })
      .then(() => {
        addToast('Самоотчёт отправлен!', 'success')
        reportModal.hide()
        setReportText('')
        loadQuests()
      })
      .catch(() => addToast('Ошибка отправки', 'error'))
  }, [reportText, selfReportQuestCode, loadQuests])

  const handleConfirmSubmit = useCallback(() => {
    if (!confirmQuestCode) return
    const proof = confirmLink.trim()
      ? { link: confirmLink.trim() }
      : {}
    api.post(`/api/v1/quests/${confirmQuestCode}/complete/`, { proof_payload: proof })
      .then(() => {
        addToast('Квест подтверждён!', 'success')
        confirmModal.hide()
        setConfirmQuestCode(null)
        setConfirmLink('')
        loadQuests()
      })
      .catch(() => addToast('Ошибка подтверждения', 'error'))
  }, [confirmQuestCode, confirmLink, loadQuests])

  const openConfirm = (code: string) => {
    setConfirmQuestCode(code)
    confirmModal.show()
  }

  const getProgressColor = (progress: number) => {
    if (progress >= 80) return '#6cd63e'
    if (progress >= 50) return '#ffd900'
    if (progress >= 30) return '#ff9f00'
    return '#fd4e4e'
  }

  const currentQuests = activeTab === 0 ? quests : activeTab === 1 ? completedQuests : []
  // В макете подтверждение и пометка об автопроверке — общие для блока
  const confirmableQuest = currentQuests.find((q) => !q.completed && q.confirm)
  const autoQuest = currentQuests.find((q) => !q.completed && q.autoVerify)

  if (loading) {
    return (
      <div className="q1 page-enter">
        <div className="q1__loading">
          <div className="loading-spinner">
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
          </div>
          <p className="loading-text">Загрузка квестов...</p>
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="q1 page-enter">
        <LoadError className="q1__loading" onRetry={loadQuests} />
      </div>
    )
  }

  return (
    <div className="q1 page-enter">
      {/* Тосты — правый верхний угол, поверх всего */}
      <div className="toast-container toast-container--fixed-right">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast--${toast.type}`}>
            {toast.type === 'success' ? '✓ ' : '✕ '}
            {toast.message}
          </div>
        ))}
      </div>

      <div className="q1__left">
        <div className="q1__tabs-card">
          <div className="q1__tabs-row" ref={tabIndicator.containerRef}>
            {TABS.map((t, i) => (
              <button
                key={t} type="button" role="tab"
                ref={tabIndicator.registerTab(i)}
                aria-selected={i === activeTab}
                className={`q1__tab${i === activeTab ? ' q1__tab--active' : ''} btn-press`}
                onClick={() => setActiveTab(i)}
              >{t}</button>
            ))}
          </div>
          <div className="q1__tabs-track" aria-hidden="true">
            <span className="q1__tabs-line" />
            <span
              className="q1__tabs-pill"
              style={{ left: tabIndicator.indicator.left, width: tabIndicator.indicator.width }}
            />
          </div>
        </div>

        {activeTab === 2 ? (
          <section className="q1__activity" style={{ background: '#f5f5f5', borderRadius: '24px', padding: '20px' }}>
            <h3 className="q1__activity-title">История наград</h3>
            <div className="q1__activity-list">
              {activity.map((a, i) => (
                <article key={a.id} className="q1__acard hover-lift" style={{ animationDelay: `${i * 80}ms` }}>
                  <div className="q1__acard-body">
                    <div className="q1__acard-name">{a.title}</div>
                    <div className="q1__acard-reward">{a.reward}</div>
                    <div className="q1__acard-time">{a.time}</div>
                  </div>
                </article>
              ))}
              {activity.length === 0 && (
                <div className="q1__empty" style={{ textAlign: 'center', padding: '40px', color: '#848484' }}>
                  <p>Пока нет истории наград</p>
                </div>
              )}
            </div>
          </section>
        ) : (
          <section className="q1__quests">
            <div className="q1__quests-slot">
              <h2 className="q1__quests-title">
                {activeTab === 0 ? 'Активный квест' : 'Выполненные квесты'}
              </h2>
              <div className="q1__quests-slot-inner">
                {currentQuests.map((q, i) => (
                  <article key={q.id} className={`q1__card hover-lift ${q.completed ? 'q1__card--completed' : ''}`} style={{ animationDelay: `${i * 80}ms` }}>
                    <div className="q1__card-body">
                      <div className="q1__card-top">
                        <span className="q1__card-kind">{q.kind}</span>
                        <span className="q1__card-kind-ic" aria-hidden="true" />
                        <span className="q1__card-left">
                          {q.completed
                            ? 'Завершён'
                            : <>Осталось&nbsp;<span className="q1__card-left-accent">{q.leftDays}</span></>}
                        </span>
                        <span
                          className="q1__card-pct"
                          style={q.completed ? { color: '#6cd63e', opacity: 1 } : undefined}
                        >
                          {q.progress}%
                        </span>
                      </div>
                      <div className="q1__card-mid">
                        <div className="q1__card-name">{q.title}</div>
                        <div className="q1__card-desc">{q.desc}</div>
                        {q.note && <div className="q1__card-team">{q.note}</div>}
                      </div>
                      <div className="q1__card-steps" aria-hidden="true">
                        <span className="q1__step q1__step--red" style={{ opacity: q.progress >= 25 ? 1 : 0.3 }} />
                        <span className="q1__step-seg q1__step-seg--red">
                          <span className="q1__step-fill" style={{ width: `${Math.min(100, q.progress / 25 * 100)}%`, background: getProgressColor(q.progress) }} />
                        </span>
                        <span className="q1__step q1__step--yellow" style={{ opacity: q.progress >= 50 ? 1 : 0.3 }} />
                        <span className="q1__step-seg q1__step-seg--yellow">
                          <span className="q1__step-fill" style={{ width: `${Math.min(100, (q.progress - 25) / 25 * 100)}%`, background: getProgressColor(q.progress) }} />
                        </span>
                        <span className="q1__step q1__step--violet" style={{ opacity: q.progress >= 75 ? 1 : 0.3 }} />
                        <div className="q1__step-rail">
                          <div className="q1__step-fill" style={{ width: `${q.progress}%`, background: getProgressColor(q.progress), transition: 'width 1s cubic-bezier(0.16, 1, 0.3, 1)' }} />
                        </div>
                        <span className="q1__step q1__step--green" style={{ opacity: q.progress >= 100 ? 1 : 0.3 }} />
                      </div>
                      <div className="q1__card-reward">
                        Награда:&nbsp;<span className="q1__card-reward-coins">{q.reward}</span>
                      </div>
                      {q.note && <div className="q1__card-note">{q.note}</div>}
                    </div>
                  </article>
                ))}
                {currentQuests.length === 0 && (
                  <div className="q1__empty" style={{ textAlign: 'center', padding: '40px', color: '#848484' }}>
                    <p>{activeTab === 0 ? 'Нет активных квестов' : 'Нет выполненных квестов'}</p>
                  </div>
                )}
              </div>

              {confirmableQuest && (
                <button
                  type="button"
                  className="q1__slot-confirm btn-press"
                  onClick={() => openConfirm(confirmableQuest.code)}
                >
                  Подтвердить
                </button>
              )}
              {autoQuest && (
                <div className="q1__slot-auto">Выполняется автоматически</div>
              )}
            </div>
          </section>
        )}
      </div>

      <aside className="q1__right">
        <div className="q1__report">
          <button type="button" className="q1__report-btn q1__report-btn--primary btn-press" onClick={reportModal.show} disabled={!selfReportQuestCode}>
            Самоотчёт
          </button>
          <button
            type="button"
            className="q1__report-btn q1__report-btn--dark btn-press"
            onClick={() => addToast('Приём жалоб пока не подключён на бэкенде', 'error')}
          >
            Пожаловаться
          </button>
        </div>

        <section className="q1__series">
          <div className="q1__series-head">
            <img className="q1__series-icon-img" src={seriesIcon} alt="" aria-hidden="true" />
            <div className="q1__series-text">
              <div className="q1__series-label">Серия:</div>
              <div className="q1__series-sub">
                {strike
                  ? `${strike.late_strike} ${dayWord(strike.late_strike)} без опозданий`
                  : 'Данные обновляются после синхронизации с HikCentral'}
              </div>
            </div>
          </div>

          {strike && (
            <div className="q1__series-progress">
              <div className="series__meta series__meta--top">
                <span>7 дней</span><span>14 дней</span>
              </div>
              <div className="series__progress-row">
                <span className="series__circle series__circle--left" />
                <div className="series__progress">
                  <div
                    className="series__progress-fill"
                    style={{ width: `${Math.min(100, strike.overall_progress_percent)}%` }}
                  />
                </div>
                <span className="series__circle series__circle--right" />
              </div>
              <div className="series__meta series__meta--bottom">
                <span>+{strike.bonus_at_7} монет</span><span>+{strike.bonus_at_21} монет</span>
              </div>
            </div>
          )}
        </section>

        <section className="q1__activity">
          <h3 className="q1__activity-title">Список выполненных квестов за последние 30 дней</h3>
          <div className="q1__activity-list">
            {recentActivity.slice(0, 3).map((a) => (
              <article key={a.id} className="q1__acard hover-lift">
                <div className="q1__acard-body">
                  <div className="q1__acard-name">{a.title}</div>
                  <div className="q1__acard-reward">{a.reward}</div>
                  <div className="q1__acard-time">{a.time}</div>
                </div>
              </article>
            ))}
          </div>
          <button type="button" className="q1__activity-more btn-press" onClick={() => setActiveTab(2)}>Показать ещё</button>
        </section>
      </aside>

      {/* Модалка самоотчёта */}
      {reportModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={reportModal.ref}>
            <h3 className="popup__title">Самоотчёт</h3>
            <label className="popup__label">Комментарий или ссылка на работу</label>
            <textarea
              value={reportText} onChange={e => setReportText(e.target.value)}
              placeholder="Опишите выполненное задание (мин. 10 символов)"
              className="popup__input"
              rows={4}
            />
            <button type="button" className="popup__submit btn-press" onClick={handleReportSubmit}>
              Отправить
            </button>
          </div>
        </div>
      )}

      {/* Модалка подтверждения квеста */}
      {confirmModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={confirmModal.ref}>
            <h3 className="popup__title">Подтверждение квеста</h3>
            <label className="popup__label">Прикрепите подтверждение выполнения</label>
            <input
              type="url" value={confirmLink} onChange={e => setConfirmLink(e.target.value)}
              placeholder="Ссылка на доказательство"
              className="popup__input"
            />
            <button type="button" className="popup__submit btn-press" onClick={handleConfirmSubmit}>
              Отправить
            </button>
          </div>
        </div>
      )}
    </div>
  )
}