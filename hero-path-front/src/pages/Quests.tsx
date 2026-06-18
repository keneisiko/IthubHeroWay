import { useState, useEffect, useCallback } from 'react'
import api from '../api'

const TABS = ['Активные', 'Выполненные', 'История наград'] as const

interface Quest {
  id: number
  kind: string
  leftDays: string
  progress: string
  title: string
  desc: string
  reward: string
  note: string
  confirm: boolean
  teamNote: string
}

interface Activity {
  id: number
  title: string
  reward: string
  time: string
}

const FALLBACK_QUESTS: Quest[] = [
  { id: 1, kind: 'Ежедневный',  leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы', reward: '+999 монет', note: 'Выполняется автоматически', confirm: false, teamNote: '' },
  { id: 2, kind: 'Еженедельный', leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы', reward: '+999 монет', note: '', confirm: true, teamNote: '' },
  { id: 3, kind: 'Сезонный',    leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы', reward: '+999 монет', note: 'Выполняется автоматически', confirm: false, teamNote: '' },
  { id: 4, kind: 'Личный',      leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы', reward: '+999 монет', note: '', confirm: true, teamNote: '' },
  { id: 5, kind: 'Командный',   leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы', reward: '+999 монет', note: '', confirm: false, teamNote: '8 из 10 сдали КТ' },
]

const FALLBACK_ACTIVITY: Activity[] = [
  { id: 1, title: 'Название', reward: 'полученные монеты', time: 'Дата выполнения' },
  { id: 2, title: 'Название', reward: 'полученные монеты', time: '1 час назад' },
  { id: 3, title: 'Название', reward: 'полученные монеты', time: '1 час назад' },
]

function Modal({
  open, onClose, title, children
}: {
  open: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
}) {
  const [visible, setVisible] = useState(false)
  const [closing, setClosing] = useState(false)

  useEffect(() => {
    if (open) {
      setClosing(false)
      const t = setTimeout(() => setVisible(true), 10)
      return () => clearTimeout(t)
    } else {
      setClosing(true)
      const t = setTimeout(() => setVisible(false), 220)
      return () => clearTimeout(t)
    }
  }, [open])

  if (!visible && !open) return null

  return (
    <div className={`overlay${closing ? ' overlay--closing' : ''}`} onClick={onClose}>
      <div className={`popup popup--link${closing ? ' popup--closing' : ''}`} onClick={e => e.stopPropagation()}>
        {title && <h3 className="popup__title">{title}</h3>}
        {children}
      </div>
    </div>
  )
}

export default function Quests() {
  const [activeTab, setActiveTab] = useState(0)
  const [showReport, setShowReport] = useState(false)
  const [reportText, setReportText] = useState('')
  const [confirmQuestId, setConfirmQuestId] = useState<number | null>(null)
  const [confirmLink, setConfirmLink] = useState('')
  const [selectedWeekly, setSelectedWeekly] = useState<'A' | 'B' | null>(null)
  const [quests, setQuests] = useState<Quest[]>(FALLBACK_QUESTS)
  const [activity, setActivity] = useState<Activity[]>(FALLBACK_ACTIVITY)

  useEffect(() => {
    api.get('/api/v1/quests/active/').then(res => {
      if (res.data?.length) setQuests(res.data)
    }).catch(() => {})

    api.get('/api/v1/quests/completed/').then(res => {
      if (res.data?.length) setActivity(res.data)
    }).catch(() => {})
  }, [])

  const handleReportSubmit = useCallback(() => {
    setShowReport(false)
    setReportText('')
  }, [])

  const handleConfirmSubmit = useCallback(() => {
    setConfirmQuestId(null)
    setConfirmLink('')
  }, [])

  return (
    <div className="q1 page-enter">
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

        <section className="q1__quests">
          <h2 className="q1__quests-title">Активный квест</h2>
          <div className="q1__quests-slot">
            <div className="q1__quests-slot-inner">
              {quests.map((q) => (
                <article key={q.id} className="q1__card hover-lift">
                  <div className="q1__card-body">
                    <div className="q1__card-top">
                      <span className="q1__card-kind">{q.kind}</span>
                      <span className="q1__card-kind-ic" aria-hidden="true" />
                      <span className="q1__card-left">
                        Осталось <span className="q1__card-left-accent">{q.leftDays}</span>
                      </span>
                      <span className="q1__card-pct">{q.progress}</span>
                    </div>
                    <div className="q1__card-mid">
                      <div className="q1__card-name">{q.title}</div>
                      <div className="q1__card-desc">{q.desc}</div>
                      {q.teamNote && <div className="q1__card-team">{q.teamNote}</div>}
                    </div>
                    <div className="q1__card-steps" aria-hidden="true">
                      <span className="q1__step q1__step--red" />
                      <span className="q1__step-seg q1__step-seg--red" />
                      <span className="q1__step q1__step--yellow" />
                      <span className="q1__step-seg q1__step-seg--yellow" />
                      <span className="q1__step q1__step--violet" />
                      <div className="q1__step-rail">
                        <div className="q1__step-fill" style={{ width: q.progress }} />
                      </div>
                      <span className="q1__step q1__step--green" />
                    </div>
                    <div className="q1__card-reward">
                      Награда: <span className="q1__card-reward-coins">{q.reward}</span>
                    </div>
                    {q.confirm && (
                      <button type="button" className="q1__card-confirm btn-press" onClick={() => setConfirmQuestId(q.id)}>
                        Подтвердить
                      </button>
                    )}
                    {q.note && <div className="q1__card-note">{q.note}</div>}
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="q1__weekly">
          <h2 className="q1__weekly-title">Еженедельный выбор</h2>
          <div className="q1__weekly-inner">
            <p className="q1__weekly-prompt">Выбери одно из двух заданий</p>
            <div className="q1__weekly-cards">
              <article className={`q1__wcard hover-lift${selectedWeekly === 'A' ? ' q1__wcard--selected' : ''}`}>
                <h3 className="q1__wcard-title">Вариант A</h3>
                <div className="q1__wcard-desc">
                  <p>Сдать все КТ недели</p>
                  <p>Помочь однокурснику с проектом</p>
                </div>
                <div className="q1__wcard-reward">+10 монет</div>
                <button type="button" className="q1__wcard-pick btn-press" onClick={() => setSelectedWeekly('A')}>
                  {selectedWeekly === 'A' ? 'Выбрано' : 'Выбрать'}
                </button>
              </article>
              <article className={`q1__wcard hover-lift${selectedWeekly === 'B' ? ' q1__wcard--selected' : ''}`}>
                <h3 className="q1__wcard-title">Вариант B</h3>
                <div className="q1__wcard-desc">
                  <p>Помочь однокурснику с проектом</p>
                  <p>Сдать КТ по Python до пятницы</p>
                </div>
                <div className="q1__wcard-reward">+10 монет</div>
                <button type="button" className="q1__wcard-pick btn-press" onClick={() => setSelectedWeekly('B')}>
                  {selectedWeekly === 'B' ? 'Выбрано' : 'Выбрать'}
                </button>
              </article>
            </div>
          </div>
        </section>
      </div>

      <aside className="q1__right">
        <div className="q1__report">
          <button type="button" className="q1__report-btn q1__report-btn--primary btn-press" onClick={() => setShowReport(true)}>
            Самоотчёт
          </button>
          <button type="button" className="q1__report-btn q1__report-btn--dark btn-press" onClick={() => alert('Функция жалобы будет доступна позже')}>
            Пожаловаться
          </button>
        </div>

        <section className="q1__series">
          <div className="q1__series-head">
            <div className="q1__series-icon" aria-hidden="true" />
            <div className="q1__series-text">
              <div className="q1__series-label">Серия:</div>
              <div className="q1__series-sub">12 дней без опозданий</div>
            </div>
          </div>
          <div className="q1__series-progress">
            <div className="q1__series-marks">
              <span className="q1__series-m q1__series-m--muted">7 дней</span>
              <span className="q1__series-m q1__series-m--dark">14 дней</span>
            </div>
            <div className="q1__series-bar">
              <span className="q1__series-dot" />
              <div className="q1__series-rail"><div className="q1__series-fill" style={{ width: '55%' }} /></div>
              <span className="q1__series-dot" />
            </div>
            <div className="q1__series-marks">
              <span className="q1__series-m q1__series-m--muted">+5 монет</span>
              <span className="q1__series-m q1__series-m--purple">+15 монет</span>
            </div>
          </div>
        </section>

        <section className="q1__activity">
          <h3 className="q1__activity-title">Список выполненных квестов за последние 30 дней</h3>
          <div className="q1__activity-list">
            {activity.map((a) => (
              <article key={a.id} className="q1__acard">
                <div className="q1__acard-body">
                  <div className="q1__acard-name">{a.title}</div>
                  <div className="q1__acard-reward">{a.reward}</div>
                  <div className="q1__acard-time">{a.time}</div>
                </div>
              </article>
            ))}
          </div>
          <button type="button" className="q1__activity-more btn-press">Показать ещё</button>
        </section>
      </aside>

      <Modal open={showReport} onClose={() => setShowReport(false)} title="Самоотчёт">
        <label className="popup__label">Ссылка на работу</label>
        <input
          type="url" value={reportText} onChange={e => setReportText(e.target.value)}
          placeholder="https://..."
          className="popup__input"
        />
        <button type="button" className="popup__submit btn-press" onClick={handleReportSubmit}>
          Отправить
        </button>
      </Modal>

      <Modal open={confirmQuestId !== null} onClose={() => setConfirmQuestId(null)} title="Подтверждение квеста">
        <label className="popup__label">Прикрепите подтверждение выполнения</label>
        <input
          type="url" value={confirmLink} onChange={e => setConfirmLink(e.target.value)}
          placeholder="Ссылка на доказательство"
          className="popup__input"
        />
        <button type="button" className="popup__submit btn-press" onClick={handleConfirmSubmit}>
          Отправить
        </button>
      </Modal>
    </div>
  )
}