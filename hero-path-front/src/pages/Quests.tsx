import { useState } from 'react'

const TABS = ['Активные', 'Выполненные', 'История наград'] as const

const QUESTS = [
  { id: 1, kind: 'Ежедневный',  leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы пппаа', reward: '+999 монет', note: 'Выполняется автоматически', confirm: false, teamNote: '' },
  { id: 2, kind: 'Еженедельный',leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы пппаа', reward: '+999 монет', note: '',  confirm: true,  teamNote: '' },
  { id: 3, kind: 'Сезонный',    leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы пппаа', reward: '+999 монет', note: 'Выполняется автоматически', confirm: false, teamNote: '' },
  { id: 4, kind: 'Личный',      leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы пппаа', reward: '+999 монет', note: '',  confirm: true,  teamNote: '' },
  { id: 5, kind: 'Командный',   leftDays: '2 дня', progress: '77%', title: 'Название', desc: 'Сдать КТ по Python до пятницы пппаа', reward: '+999 монет', note: '',  confirm: false, teamNote: '8 из 10 сдали КТ' },
]

const ACTIVITY = [
  { id: 1, title: 'Название', reward: 'полученные монеты', time: 'Дата выполнения' },
  { id: 2, title: 'Название', reward: 'полученные монеты', time: '1 час назад' },
  { id: 3, title: 'Название', reward: 'полученные монеты', time: '1 час назад' },
]

export default function Quests() {
  const [activeTab, setActiveTab] = useState(0)

  return (
    <div className="q1">
      {/* ─── левая колонка ─── */}
      <div className="q1__left">

        {/* вкладки */}
        <div className="q1__tabs-card">
          <div className="q1__tabs-row">
            {TABS.map((t, i) => (
              <button
                key={t} type="button" role="tab"
                aria-selected={i === activeTab}
                className={`q1__tab${i === activeTab ? ' q1__tab--active' : ''}`}
                onClick={() => setActiveTab(i)}
              >{t}</button>
            ))}
          </div>
          <div className="q1__tabs-track" aria-hidden="true">
            <span className="q1__tabs-line" />
            <span className="q1__tabs-pill" style={{ left: `calc(${activeTab} * 33.333% + 16.666%)` }} />
          </div>
        </div>

        {/* блок квестов */}
        <section className="q1__quests">
          <h2 className="q1__quests-title">Активный квест</h2>
          <div className="q1__quests-slot">
            <div className="q1__quests-slot-inner">
              {QUESTS.map((q) => (
                <article key={q.id} className="q1__card">
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
                        <div className="q1__step-fill" style={{ width: '40%' }} />
                      </div>
                      <span className="q1__step q1__step--green" />
                    </div>

                    <div className="q1__card-reward">
                      Награда: <span className="q1__card-reward-coins">{q.reward}</span>
                    </div>

                    {q.confirm && (
                      <button type="button" className="q1__card-confirm">Подтвердить</button>
                    )}
                    {q.note && (
                      <div className="q1__card-note">{q.note}</div>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* еженедельный выбор */}
        <section className="q1__weekly">
          <h2 className="q1__weekly-title">Еженедельный выбор</h2>
          <div className="q1__weekly-inner">
            <p className="q1__weekly-prompt">Выбери одно из двух заданий</p>
            <div className="q1__weekly-cards">
              <article className="q1__wcard">
                <h3 className="q1__wcard-title">Вариант A</h3>
                <div className="q1__wcard-desc">
                  <p>Сдать все КТ недели</p>
                  <p>Помочь однокурснику с проектом</p>
                </div>
                <div className="q1__wcard-reward">+10 монет</div>
                <button type="button" className="q1__wcard-pick">Выбрать</button>
              </article>
              <article className="q1__wcard">
                <h3 className="q1__wcard-title">Вариант B</h3>
                <div className="q1__wcard-desc">
                  <p>Помочь однокурснику с проектом</p>
                  <p>Сдать КТ по Python до пятницы</p>
                </div>
                <div className="q1__wcard-reward">+10 монет</div>
              </article>
            </div>
          </div>
        </section>
      </div>

      {/* ─── правая колонка ─── */}
      <aside className="q1__right">

        {/* самоотчёт */}
        <div className="q1__report">
          <button type="button" className="q1__report-btn q1__report-btn--primary">Самоотчёт</button>
          <button type="button" className="q1__report-btn q1__report-btn--dark">Пожаловаться</button>
        </div>

        {/* серия */}
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

        {/* лента */}
        <section className="q1__activity">
          <h3 className="q1__activity-title">Список выполненных квестов за последние 30 дней</h3>
          <div className="q1__activity-list">
            {ACTIVITY.map((a) => (
              <article key={a.id} className="q1__acard">
                <div className="q1__acard-body">
                  <div className="q1__acard-name">{a.title}</div>
                  <div className="q1__acard-reward">{a.reward}</div>
                  <div className="q1__acard-time">{a.time}</div>
                </div>
              </article>
            ))}
          </div>
          <button type="button" className="q1__activity-more">Показать ещё</button>
        </section>
      </aside>
    </div>
  )
}
