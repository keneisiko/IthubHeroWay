import { useState, useEffect, useCallback, useRef } from 'react'
import api from '../api'
import LoadError from '../components/LoadError'
import DialogClose from '../components/DialogClose'
import { useModal } from '../useModal'
import { useTabIndicator } from '../useTabIndicator'
import { plural } from '../lib/plural'
import { celebrate } from '../lib/celebrate'
import { apiErrorMessage } from '../lib/apiData'
import seriesIcon from '../assets/other/Group 11.svg'
import {
  mapCompletedQuests,
  mapRewardActivities,
  mapRecentRewardActivities,
  mergeActiveQuests,
  type UiQuest,
} from '../lib/quests'
import '../styles/quests.css'

const TABS = ['Активные', 'Выполненные', 'История наград'] as const

interface Activity {
  id: number
  title: string
  reward: string
  time: string
}

// Склонение дней для подписи серии
// сколько квестов видно до «Показать все»
const MOBILE_QUESTS = 3

export default function Quests() {
  const [showAllQuests, setShowAllQuests] = useState(false)
  const [activeTab, setActiveTab] = useState(0)
  const [quests, setQuests] = useState<UiQuest[]>([])
  const [completedQuests, setCompletedQuests] = useState<UiQuest[]>([])
  const [activity, setActivity] = useState<Activity[]>([])
  const [recentActivity, setRecentActivity] = useState<Activity[]>([])
  // Цель недели хранится на сервере: раньше выбор жил только здесь,
  // сбрасывался при перезагрузке и ни на что не влиял.
  const [weeklyChoice, setWeeklyChoice] = useState<string | null>(null)
  const [focusBonus, setFocusBonus] = useState<{ coins: number; rating: number }>({ coins: 0, rating: 0 })
  // Подсветка карточки до нажатия «Выбрать»: сам выбор отправляется явно.
  const [focusPreview, setFocusPreview] = useState<string | null>(null)
  const [picking, setPicking] = useState<string | null>(null)
  const pickingRef = useRef(false)
  const [strike, setStrike] = useState<{
    late_strike: number
    bonus_at_7: number
    bonus_at_21: number
    overall_progress_percent: number
  } | null>(null)
  const [loading, setLoading] = useState(true)
  // ref отдельно от состояния: в одном объекте линтер React считал рефом всё.
  const {
    containerRef: tabsContainerRef,
    registerTab,
    indicator: tabIndicatorBox,
  } = useTabIndicator(activeTab, loading)
  const [loadError, setLoadError] = useState(false)
  const [toasts, setToasts] = useState<{ id: number; message: string; type: 'success' | 'error' }[]>([])

  const { ref: confirmModalRef, ...confirmModal } = useModal()
  const [confirmComment, setConfirmComment] = useState('')
  const [confirmQuestCode, setConfirmQuestCode] = useState<string | null>(null)
  const [confirmQuestTitle, setConfirmQuestTitle] = useState('')
  const [confirmLink, setConfirmLink] = useState('')

  // useCallback: функция попадает в зависимости других колбэков, и без
  // мемоизации они пересоздавались на каждый рендер.
  const addToast = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3000)
  }, [])

  // quiet — обновить после отправки отчёта или выбора цели без лоадера
  // на всю страницу и без прыжка прокрутки
  const loadQuests = useCallback(({ quiet = false }: { quiet?: boolean } = {}) => {
    return Promise.all([
      api.get('/api/v1/quests/active/'),
      api.get('/api/v1/quests/my-progress/', { params: { completed: false } }),
      api.get('/api/v1/quests/my-progress/', { params: { completed: true } }),
      api.get('/api/v1/quests/rewards/history/'),
      api.get('/api/v1/dashboard/'),
      api.get('/api/v1/quests/weekly-focus/'),
    ]).then(([activeRes, progressRes, completedRes, historyRes, dashRes, focusRes]) => {
      setQuests(mergeActiveQuests(activeRes.data, progressRes.data, completedRes.data))
      setCompletedQuests(mapCompletedQuests(completedRes.data))
      setActivity(mapRewardActivities(historyRes.data))
      setRecentActivity(mapRecentRewardActivities(historyRes.data))
      setStrike(dashRes.data?.strike ?? null)
      setWeeklyChoice(focusRes.data?.quest_code || null)
      setFocusBonus({
        coins: focusRes.data?.bonus_coins ?? 0,
        rating: focusRes.data?.bonus_rating ?? 0,
      })
    }).catch(() => {
      if (quiet) {
        addToast('Не удалось обновить квесты', 'error')
        return
      }
      setQuests([])
      setCompletedQuests([])
      setActivity([])
      setLoadError(true)
    }).finally(() => setLoading(false))
  }, [addToast])

  // «Загружается» при первом показе уже стоит в начальном состоянии;
  // повтор ставит его сам. Синхронный setState в эффекте давал лишний
  // каскадный рендер.
  useEffect(() => {
    loadQuests()
  }, [loadQuests])

  const retryQuests = () => {
    setLoading(true)
    setLoadError(false)
    loadQuests()
  }

  // Самоотчёт всегда привязан к квесту: его открывают с карточки квеста или
  // выбирают квест в окне. Раньше кнопка «Самоотчёт» сама брала первый
  // попавшийся квест-самоотчёт, и куратор получал отчёт не о том.
  const reportableQuests = quests.filter((q) => q.confirm && q.reviewStatus !== 'pending')

  const handleConfirmSubmit = useCallback(() => {
    if (!confirmQuestCode) {
      addToast('Выберите квест, по которому отчёт', 'error')
      return
    }
    const link = confirmLink.trim()
    const comment = confirmComment.trim()
    if (!link && comment.length < 10) {
      addToast('Приложите ссылку или опишите, что сделали (от 10 символов)', 'error')
      return
    }
    api.post(`/api/v1/quests/${confirmQuestCode}/complete/`, { proof_payload: { link, comment } })
      .then(() => {
        addToast('Отправлено куратору на проверку', 'success')
        celebrate('small')
        confirmModal.hide()
        setConfirmQuestCode(null)
        setConfirmLink('')
        setConfirmComment('')
        loadQuests({ quiet: true })
      })
      .catch((err) => addToast(apiErrorMessage(err, 'Не удалось отправить самоотчёт'), 'error'))
  }, [confirmQuestCode, confirmLink, confirmComment, confirmModal, addToast, loadQuests])

  // code = null — окно открыто общей кнопкой «Самоотчёт», квест выбирают в нём
  const openConfirm = (code: string | null, title: string) => {
    setConfirmQuestCode(code)
    setConfirmQuestTitle(title)
    confirmModal.show()
  }

  // Выбор отмечается сразу — на карточку ставится знак, кнопка
  // перекрашивается; ответ сервера только подтверждает, ошибка откатывает.
  const pickWeeklyFocus = useCallback((code: string, title: string) => {
    if (pickingRef.current) return
    pickingRef.current = true
    const previous = weeklyChoice
    setWeeklyChoice(code)
    setFocusPreview(code)
    setPicking(code)
    api.post('/api/v1/quests/weekly-focus/', { quest_code: code })
      .then(() => {
        addToast(`Цель недели: ${title}`)
        return loadQuests({ quiet: true })
      })
      .catch(() => {
        setWeeklyChoice(previous)
        setFocusPreview(previous)
        addToast('Не удалось выбрать цель недели', 'error')
      })
      .finally(() => {
        pickingRef.current = false
        setPicking(null)
      })
  }, [addToast, loadQuests, weeklyChoice])

  const rawQuests = activeTab === 0 ? quests : activeTab === 1 ? completedQuests : []
  // Цель недели — первой в списке: студент сам назначил её приоритетом.
  const currentQuests = weeklyChoice
    ? [...rawQuests].sort((a, b) => Number(b.code === weeklyChoice) - Number(a.code === weeklyChoice))
    : rawQuests
  // Целью недели может стать любой активный еженедельный квест. Раньше
  // в блок попадали первые два по порядку — произвольная пара, а выбранный
  // третий квест не показывался вовсе.
  const weeklyOptions = quests.filter((q) => !q.completed && q.kind === 'Еженедельный')
  const focusedWeekly = focusPreview ?? weeklyChoice ?? weeklyOptions[0]?.code ?? null

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
        <LoadError className="q1__loading" onRetry={retryQuests} />
      </div>
    )
  }

  return (
    <div className="q1 page-enter">
      {/* Тосты — правый верхний угол, поверх всего */}
      <div className="toast-container toast-container--fixed-right">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast--${toast.type}`}>
            {toast.message}
          </div>
        ))}
      </div>

      <div className="q1__left">
        <div className="q1__tabs-card">
          <div className="q1__tabs-row" ref={tabsContainerRef}>
            {TABS.map((t, i) => (
              <button
                key={t} type="button" role="tab"
                ref={registerTab(i)}
                aria-selected={i === activeTab}
                className={`q1__tab${i === activeTab ? ' q1__tab--active' : ''} btn-press`}
                onClick={() => { setActiveTab(i); setShowAllQuests(false) }}
              >{t}</button>
            ))}
          </div>
          <div className="q1__tabs-track" aria-hidden="true">
            <span className="q1__tabs-line" />
            <span
              className="q1__tabs-pill"
              style={{ left: tabIndicatorBox.left, width: tabIndicatorBox.width }}
            />
          </div>
        </div>

        {activeTab === 2 ? (
          <section className="q1__activity" style={{ background: '#f5f5f5', borderRadius: '24px', padding: '20px' }}>
            <h3 className="q1__activity-title">История наград</h3>
            <div className="q1__activity-list">
              {activity.map((a, i) => (
                <article key={a.id} className="q1__acard hover-lift spot" style={{ animationDelay: `${i * 80}ms` }}>
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
              <div className={`q1__quests-slot-inner${showAllQuests ? ' q1__quests-slot-inner--all' : ''}`}>
                {currentQuests.map((q, i) => (
                  <article
                    key={q.id}
                    className={`q1__card hover-lift spot ${q.completed ? 'q1__card--completed' : ''}${q.confirm && q.reviewStatus !== 'pending' ? ' q1__card--reportable' : ''}`}
                    style={{ animationDelay: `${i * 80}ms` }}
                    onClick={q.confirm && q.reviewStatus !== 'pending' ? () => openConfirm(q.code, q.title) : undefined}
                  >
                    <div className="q1__card-body">
                      <div className="q1__card-top">
                        <span className="q1__card-kind">{q.kind}</span>
                        {q.code === weeklyChoice && (
                          <span className="q1__card-focus" title="Выбрана целью недели">
                            Цель недели
                          </span>
                        )}
                        <span className="q1__card-kind-ic" aria-hidden="true" />
                        <span className="q1__card-left">
                          {q.completed
                            ? 'Завершён'
                            : q.leftDays
                              ? <>Осталось&nbsp;<span className="q1__card-left-accent">{q.leftDays}</span></>
                              : 'Без срока'}
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
                      {/* на телефоне прогресс виден полоской, процент — в углу */}
                      <div className="q1__card-bar" aria-hidden="true">
                        <span style={{ width: `${q.progress}%` }} />
                      </div>
                      <div className="q1__card-reward">
                        Награда:&nbsp;<span className="q1__card-reward-coins">{q.reward}</span>
                      </div>
                      {q.reviewStatus === 'pending' ? (
                        <div className="q1__card-review q1__card-review--pending">
                          Отправлено куратору, ждёт проверки
                        </div>
                      ) : q.confirm && (
                        <button
                          type="button"
                          className="q1__card-confirm btn-press"
                          onClick={(e) => { e.stopPropagation(); openConfirm(q.code, q.title) }}
                        >
                          {q.reviewStatus === 'rejected' ? 'Отправить заново' : 'Отправить самоотчёт'}
                        </button>
                      )}
                      {q.reviewStatus === 'rejected' && (
                        <div className="q1__card-review q1__card-review--rejected">
                          Куратор отклонил подтверждение
                        </div>
                      )}
                    </div>
                  </article>
                ))}
                {currentQuests.length === 0 && (
                  <div className="q1__empty" style={{ textAlign: 'center', padding: '40px', color: '#848484' }}>
                    <p>{activeTab === 0 ? 'Нет активных квестов' : 'Нет выполненных квестов'}</p>
                  </div>
                )}
              </div>
              {/* сначала видны три квеста, остальные — по кнопке */}
              {currentQuests.length > MOBILE_QUESTS && (
                <button
                  type="button"
                  className="q1__quests-more btn-press"
                  onClick={() => setShowAllQuests((v) => !v)}
                  aria-expanded={showAllQuests}
                >
                  {showAllQuests ? 'Свернуть' : `Показать все (${currentQuests.length})`}
                </button>
              )}


            </div>

            {weeklyOptions.length > 1 && (
              <section className="q1__choice">
                <h3 className="q1__choice-title">Еженедельный выбор</h3>
                <div className="q1__choice-box">
                  <p className="q1__choice-lead">
                    Выбери цель недели{focusBonus.coins || focusBonus.rating
                      ? `: +${focusBonus.coins} монет и +${focusBonus.rating} рейтинга сверху за неё`
                      : ''}
                  </p>
                  <div className="q1__choice-options">
                    {weeklyOptions.map((option) => {
                      const isFocused = option.code === focusedWeekly
                      return (
                        <article
                          key={option.code}
                          className={`q1__option${isFocused ? ' q1__option--focused' : ''}`}
                          onClick={() => setFocusPreview(option.code)}
                        >
                          {option.code === weeklyChoice && <span className="q1__option-mark" aria-hidden="true" />}
                          <h4 className="q1__option-title">{option.title}</h4>
                          <p className="q1__option-task">{option.desc}</p>
                          <div className="q1__option-reward">{option.reward}</div>
                          <button
                            type="button"
                            className={`q1__option-pick btn-press${
                              option.code === weeklyChoice ? ' q1__option-pick--current' : ''
                            }${picking === option.code ? ' q1__option-pick--busy' : ''}`}
                            onClick={() => pickWeeklyFocus(option.code, option.title)}
                            disabled={picking !== null || option.code === weeklyChoice}
                          >
                            <span key={String(option.code === weeklyChoice)} className="q1__option-pick-label">
                              {option.code === weeklyChoice ? 'Цель недели' : 'Выбрать'}
                            </span>
                          </button>
                        </article>
                      )
                    })}
                  </div>
                </div>
              </section>
            )}
          </section>
        )}
      </div>

      <aside className="q1__right">
        <div className="q1__report">
          <button type="button" className="q1__report-btn q1__report-btn--primary btn-press" onClick={() => openConfirm(null, '')} disabled={reportableQuests.length === 0}>
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
          <div className="series__header">
            <img className="series__icon-image" src={seriesIcon} alt="" aria-hidden="true" />
            <div className="series__title-wrap">
              <h3>Серия:</h3>
              <p>
                {strike
                  ? `${strike.late_strike} ${plural(strike.late_strike, ['день', 'дня', 'дней'])} без опозданий`
                  : 'Данные обновляются после синхронизации с HikCentral'}
              </p>
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

        {/* во вкладке «История наград» этот же список уже на экране */}
        {activeTab !== 2 && (
        <section className="q1__activity">
          <h3 className="q1__activity-title">Список выполненных квестов за последние 30 дней</h3>
          <div className="q1__activity-list">
            {recentActivity.slice(0, 3).map((a) => (
              <article key={a.id} className="q1__acard hover-lift spot">
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
        )}
      </aside>

      {/* Самоотчёт по квесту: квест известен с карточки или выбирается здесь */}
      {confirmModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content popup--closable" ref={confirmModalRef} role="dialog" aria-modal="true" aria-label="Самоотчёт" tabIndex={-1}>
            <DialogClose onClose={confirmModal.hide} />
            <h3 className="popup__title">Самоотчёт</h3>
            {confirmQuestTitle ? (
              <p className="popup__label">Квест: <b>{confirmQuestTitle}</b></p>
            ) : (
              <>
                <p className="popup__label" id="report-quest">По какому квесту</p>
                <div className="report-quests" role="radiogroup" aria-labelledby="report-quest">
                  {reportableQuests.map((q) => (
                    <button
                      key={q.code}
                      type="button"
                      role="radio"
                      aria-checked={confirmQuestCode === q.code}
                      className={`report-quests__item btn-press${confirmQuestCode === q.code ? ' report-quests__item--on' : ''}`}
                      onClick={() => setConfirmQuestCode(q.code)}
                    >
                      <span className="report-quests__title">{q.title}</span>
                      <span className="report-quests__meta">{q.kind} · {q.reward}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
            <label className="popup__label" htmlFor="report-comment">Что сделали</label>
            <textarea
              id="report-comment"
              value={confirmComment} onChange={e => setConfirmComment(e.target.value)}
              placeholder="Коротко опишите выполненное"
              className="popup__input"
              rows={3}
            />
            <label className="popup__label" htmlFor="report-link">
              Ссылка на работу — её проверит куратор, награда придёт после одобрения
            </label>
            <input
              id="report-link"
              type="url" value={confirmLink} onChange={e => setConfirmLink(e.target.value)}
              placeholder="https://…"
              className="popup__input"
            />
            <button type="button" className="popup__submit btn-press" onClick={handleConfirmSubmit}>
              Отправить на проверку
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
