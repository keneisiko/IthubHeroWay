import { useState, useEffect, useCallback, useRef } from 'react'
import api from '../api'
import LoadError from '../components/LoadError'
import seriesIcon from '../assets/other/Group 11.svg'
import {
  mapCompletedQuests,
  mapRewardActivities,
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

export default function Quests() {
  const [activeTab, setActiveTab] = useState(0)
  const [quests, setQuests] = useState<UiQuest[]>([])
  const [completedQuests, setCompletedQuests] = useState<UiQuest[]>([])
  const [activity, setActivity] = useState<Activity[]>([])
  const [selfReportQuestCode, setSelfReportQuestCode] = useState<string | null>(null)
  const [lateStrike, setLateStrike] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
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
      setSelfReportQuestCode(pickSelfReportQuestCode(activeRes.data))
      setLateStrike(dashRes.data?.strike?.late_strike ?? null)
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
          <div className="q1__tabs-row">
            {TABS.map((t, i) => (
              <button
                key={t} type="button" role="tab"
                aria-selected={i === activeTab}
                className={`q1__tab${i === activeTab ? ' q1__tab--active' : ''} btn-press`}
                onClick={() => setActiveTab(i)}
              >{t}</button>
            ))}
          </div>
          <div className="q1__tabs-track" aria-hidden="true">
            <span className="q1__tabs-line" />
            <span className="q1__tabs-pill" style={{ left: `calc(${activeTab} * 33.333% + 16.666%)` }} />
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
            <h2 className="q1__quests-title">
              {activeTab === 0 ? 'Активные квесты' : 'Выполненные квесты'}
              <span className="q1__quests-count">{currentQuests.length}</span>
            </h2>
            <div className="q1__quests-slot">
              <div className="q1__quests-slot-inner">
                {currentQuests.map((q, i) => (
                  <article key={q.id} className={`q1__card hover-lift ${q.completed ? 'q1__card--completed' : ''}`} style={{ animationDelay: `${i * 80}ms` }}>
                    <div className="q1__card-body">
                      <div className="q1__card-top">
                        <span className="q1__card-kind">{q.kind}</span>
                        <span className="q1__card-kind-ic" aria-hidden="true" />
                        <span className="q1__card-left">
                          {q.completed ? 'Завершён' : <>Осталось <span className="q1__card-left-accent">{q.leftDays}</span></>}
                        </span>
                        <span className="q1__card-pct" style={{ background: q.completed ? '#6cd63e' : '#121212' }}>
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
                        Награда: <span className="q1__card-reward-coins">{q.reward}</span>
                      </div>
                      {!q.completed && q.confirm && (
                        <button type="button" className="q1__card-confirm btn-press" onClick={() => openConfirm(q.code)}>
                          Подтвердить
                        </button>
                      )}
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
            </div>
          </section>
        )}
      </div>

      <aside className="q1__right">
        <div className="q1__report">
          <button type="button" className="q1__report-btn q1__report-btn--primary btn-press" onClick={reportModal.show} disabled={!selfReportQuestCode}>
            Самоотчёт
          </button>
        </div>

        <section className="q1__series">
          <div className="q1__series-head">
            <img className="q1__series-icon-img" src={seriesIcon} alt="" aria-hidden="true" />
            <div className="q1__series-text">
              <div className="q1__series-label">Серия без опозданий</div>
              <div className="q1__series-sub">
                {lateStrike != null
                  ? `${lateStrike} ${lateStrike === 1 ? 'день' : lateStrike >= 2 && lateStrike <= 4 ? 'дня' : 'дней'} подряд`
                  : 'Данные обновляются после синхронизации с HikCentral'}
              </div>
            </div>
          </div>
        </section>

        <section className="q1__activity">
          <h3 className="q1__activity-title">Последние награды</h3>
          <div className="q1__activity-list">
            {activity.slice(0, 3).map((a) => (
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