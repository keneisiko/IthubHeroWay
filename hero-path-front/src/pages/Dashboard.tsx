import { useState } from 'react'
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

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

const AXIS_LABELS = ['Ритм', 'Фокус', 'Мощность', 'Связь', 'Отдача']
const AXIS_VALUES = { current: [80, 60, 70, 50, 65], peak: [90, 75, 80, 65, 75] }

const radarData = {
  labels: AXIS_LABELS,
  datasets: [
    {
      label: 'Текущий',
      data: AXIS_VALUES.current,
      backgroundColor: 'rgba(154, 51, 244, 0.2)',
      borderColor: '#9A33F4',
      borderWidth: 6,
      pointBackgroundColor: '#9A33F4',
      pointBorderColor: '#f5f5f5',
      pointBorderWidth: 6,
      pointRadius: 12,
      pointHoverRadius: 14,
    },
    {
      label: 'Пик',
      data: AXIS_VALUES.peak,
      backgroundColor: 'rgba(154, 51, 244, 0.08)',
      borderColor: 'rgba(154, 51, 244, 0.65)',
      borderWidth: 4,
      borderDash: [8, 8],
      pointRadius: 0,
    },
  ],
}

const radarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      beginAtZero: true,
      max: 100,
      ticks: { display: false },
      grid: { color: 'rgba(154, 51, 244, 1)', lineWidth: 4 },
      angleLines: { color: 'rgba(154, 51, 244, 1)', lineWidth: 4 },
      pointLabels: { display: false },
    },
  },
  layout: { padding: 0 },
  elements: { line: { tension: 0 } },
  animation: { duration: 800, easing: 'easeOutQuart' as const },
  plugins: { legend: { display: false } },
}

type QuestTab = 'daily' | 'weekly'

export default function Dashboard() {
  const [hoveredRadar, setHoveredRadar] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [confirmLink, setConfirmLink] = useState('')
  const [questTab, setQuestTab] = useState<QuestTab>('daily')
  const [showReport, setShowReport] = useState(false)
  const [reportText, setReportText] = useState('')

  const activity = [
    { text: 'Получена нашивка «Железный ритм»', time: '1 час назад' },
    { text: '+3 монеты от @ivan за респект', time: '2 часа назад', highlight: '@ivan' },
    { text: 'Серия 7 дней · +5 монет', time: '3 часа назад' },
  ]

  return (
    <div className="dashboard page-enter">
      <div className="dashboard__top">
        <div className="dashboard__left-col">
          <section className="card card--light">
            <div className="series__header">
              <img className="series__icon-image" src={seriesIcon} alt="" aria-hidden="true" />
              <div className="series__title-wrap">
                <h3>Серия:</h3>
                <p>12 дней без опозданий</p>
              </div>
            </div>
            <div className="series__meta series__meta--top">
              <span>7 дней</span><span>14 дней</span>
            </div>
            <div className="series__progress-row">
              <span className="series__circle series__circle--left" />
              <div className="series__progress"><div className="series__progress-fill" /></div>
              <span className="series__circle series__circle--right" />
            </div>
            <div className="series__meta series__meta--bottom">
              <span>+5 монет</span><span>+15 монет</span>
            </div>
          </section>

          <section className="card card--purple">
            <h3 className="rating__title">Текущий рейтинг:</h3>
            <div className="rating__value">199</div>
            <div className="rating__line">
              <span>Статус:</span>
              <span className="chip chip--light rating__chip">Игрок</span>
              <span className="chip chip--light rating__chip">6 ур.</span>
            </div>
            <div className="rating__line">
              <span>до</span>
              <span className="chip chip--dark rating__chip rating__chip--leader">Лидера</span>
              <span>осталось:</span>
            </div>
            <span className="chip chip--light rating__target">150 баллов</span>
            <div className="rating__progress-row">
              <span className="rating__circle rating__circle--left" />
              <div className="rating__progress"><div className="rating__progress-fill" /></div>
              <span className="rating__circle rating__circle--right" />
            </div>
            <div className="rating__meta">
              <span>Игрок</span><span>Лидер</span>
            </div>
          </section>
        </div>

        <section className="radar-card">
          <span className="radar-card__label" style={{
            opacity: hoveredRadar ? 1 : 0,
            transition: 'opacity 0.25s ease-out',
          }}>
            {hoveredRadar ? `${hoveredRadar}: ${AXIS_VALUES.current[AXIS_LABELS.indexOf(hoveredRadar)]}%` : 'Ритм'}
          </span>
          <div
            className="radar-card__canvas"
            onMouseLeave={() => setHoveredRadar(null)}
          >
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
                        item.datasetIndex === 0
                          ? `Текущий: ${item.raw}%`
                          : `Пик: ${item.raw}%`,
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
        </section>
      </div>

      <div className="dashboard__bottom">
        <section className="activity-card">
          <h3 className="section-title">Лента активности</h3>
          <div className="activity">
            {activity.map((item) => (
              <article key={item.text} className="activity__item" style={{ animation: 'slideUp 0.4s ease-out' }}>
                <span>
                  {item.highlight ? (
                    <>
                      {item.text.split(item.highlight)[0]}
                      <span className="activity__highlight">{item.highlight}</span>
                      {item.text.split(item.highlight)[1]}
                    </>
                  ) : item.text}
                </span>
                <time>{item.time}</time>
              </article>
            ))}
          </div>
        </section>

        <section className="quest">
          <h3>Активный квест</h3>
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
            <div className="quest__head">
              <span>{questTab === 'daily' ? 'Сдать КТ по Python' : 'Завершить 5 задач'}</span>
              <strong>{questTab === 'daily' ? '77%' : '40%'}</strong>
            </div>
            <div className="quest__steps">
              <span className="quest-step"><span className="dot dot--red" /><span className="quest-step__bar quest-step__bar--red" /></span>
              <span className="quest-step"><span className="dot dot--yellow" /><span className="quest-step__bar quest-step__bar--yellow" /></span>
              <span className="quest-step"><span className="dot dot--blue" /><span className="quest-step__bar quest-step__bar--blue" /></span>
              <span className="dot dot--green" />
            </div>
          </div>
          <button className="quest__confirm" onClick={() => setShowConfirm(true)}>Подтвердить</button>
          <div className="quest__row">
            <span>Текст</span><span>+</span>
          </div>
          <button className="quest__self" onClick={() => setShowReport(true)}>Самоотчёт</button>
        </section>
      </div>

      {/* Confirm quest popup */}
      {showConfirm && (
        <div className="overlay" onClick={() => setShowConfirm(false)}>
          <div className="popup" onClick={(e) => e.stopPropagation()} style={{
            background: '#f5f5f5', borderRadius: '12px', border: '4px solid #9a33f4',
            boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '20px',
            width: '460px', maxWidth: '90vw', display: 'flex', flexDirection: 'column', gap: '16px',
          }}>
            <label style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '20px', color: '#848484' }}>
              Прикрепите подтверждение выполнения
            </label>
            <input
              type="url"
              value={confirmLink}
              onChange={(e) => setConfirmLink(e.target.value)}
              placeholder="Ссылка на доказательство"
              style={{
                height: '38px', borderRadius: '12px', border: '4px solid #9a33f4',
                padding: '0 12px', fontFamily: 'Montserrat, sans-serif', fontSize: '16px',
                outline: 'none', background: '#fff', color: '#121212',
              }}
            />
            <button type="button" onClick={() => { setShowConfirm(false); setConfirmLink('') }} style={{
              background: '#9a33f4', height: '48px', borderRadius: '48px',
              border: '4px solid #f5f5f5', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)',
              padding: '3px 24px', fontFamily: 'Montserrat, sans-serif', fontWeight: 700,
              fontSize: '24px', color: '#f5f5f5', cursor: 'pointer', transition: 'opacity 0.2s',
            }}>
              Отправить
            </button>
          </div>
        </div>
      )}

      {/* Self-report popup (Frame142) */}
      {showReport && (
        <div className="overlay" onClick={() => setShowReport(false)}>
          <div className="popup" onClick={(e) => e.stopPropagation()} style={{
            background: '#f5f5f5', borderRadius: '12px', border: '4px solid #9a33f4',
            boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '20px',
            width: '460px', maxWidth: '90vw', display: 'flex', flexDirection: 'column', gap: '16px',
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '20px', color: '#848484' }}>
                Ссылка на работу
              </label>
              <input
                type="url"
                value={reportText}
                onChange={(e) => setReportText(e.target.value)}
                placeholder="https://..."
                style={{
                  height: '38px', borderRadius: '12px', border: '4px solid #9a33f4',
                  padding: '0 12px', fontFamily: 'Montserrat, sans-serif', fontSize: '16px',
                  outline: 'none', background: '#fff', color: '#121212',
                }}
              />
            </div>
            <button type="button" onClick={() => { setShowReport(false); setReportText('') }} style={{
              background: '#9a33f4', height: '48px', borderRadius: '48px',
              border: '4px solid #f5f5f5', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)',
              padding: '3px 24px', fontFamily: 'Montserrat, sans-serif', fontWeight: 700,
              fontSize: '24px', color: '#f5f5f5', cursor: 'pointer', transition: 'opacity 0.2s',
            }}>
              Отправить
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
