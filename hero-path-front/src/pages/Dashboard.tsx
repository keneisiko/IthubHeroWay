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

const radarData = {
  labels: ['Ритм', 'Фокус', 'Мощность', 'Связь', 'Отдача'],
  datasets: [
    {
      label: 'Текущий',
      data: [80, 60, 70, 50, 65],
      backgroundColor: 'rgba(154, 51, 244, 0.2)',
      borderColor: '#9A33F4',
      borderWidth: 6,
      pointBackgroundColor: '#9A33F4',
      pointBorderColor: '#f5f5f5',
      pointBorderWidth: 6,
      pointRadius: 12,
      pointHoverRadius: 12,
    },
    {
      label: 'Пик',
      data: [90, 75, 80, 65, 75],
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
  layout: {
    padding: 0,
  },
  elements: {
    line: { tension: 0 },
  },
  animation: { duration: 0 },
  plugins: { legend: { display: false } },
}

export default function Dashboard() {
  const activity = [
    { text: 'Получена нашивка «Железный ритм»', time: '1 час назад' },
    { text: '+3 монеты от @ivan за респект', time: '2 часа назад', highlight: '@ivan' },
    { text: 'Серия 7 дней · +5 монет', time: '3 часа назад' },
  ]

  return (
    <div className="dashboard">
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
              <span>7 дней</span>
              <span>14 дней</span>
            </div>
            <div className="series__progress-row">
              <span className="series__circle series__circle--left" />
              <div className="series__progress">
                <div className="series__progress-fill" />
              </div>
              <span className="series__circle series__circle--right" />
            </div>
            <div className="series__meta series__meta--bottom">
              <span>+5 монет</span>
              <span>+15 монет</span>
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
              <div className="rating__progress">
                <div className="rating__progress-fill" />
              </div>
              <span className="rating__circle rating__circle--right" />
            </div>
            <div className="rating__meta">
              <span>Игрок</span>
              <span>Лидер</span>
            </div>
          </section>
        </div>

        <section className="radar-card">
          <span className="radar-card__label">Ритм</span>
          <div className="radar-card__canvas">
            <Radar data={radarData} options={radarOptions} />
          </div>
        </section>
      </div>

      <div className="dashboard__bottom">
        <section className="activity-card">
          <h3 className="section-title">Лента активности</h3>
          <div className="activity">
            {activity.map((item) => (
              <article key={item.text} className="activity__item">
                <span>
                  {item.highlight ? (
                    <>
                      {item.text.split(item.highlight)[0]}
                      <span className="activity__highlight">{item.highlight}</span>
                      {item.text.split(item.highlight)[1]}
                    </>
                  ) : (
                    item.text
                  )}
                </span>
                <time>{item.time}</time>
              </article>
            ))}
          </div>
        </section>

        <section className="quest">
          <h3>Активный квест</h3>
          <div className="quest__tabs">
            <button className="quest__tab quest__tab--active">Ежедневный</button>
            <button className="quest__tab">Еженедельный</button>
          </div>
          <div className="quest__progress">
            <div className="quest__head">
              <span>Сдать КТ по Python</span>
              <strong>77%</strong>
            </div>
            <div className="quest__steps">
              <span className="quest-step">
                <span className="dot dot--red" />
                <span className="quest-step__bar quest-step__bar--red" />
              </span>
              <span className="quest-step">
                <span className="dot dot--yellow" />
                <span className="quest-step__bar quest-step__bar--yellow" />
              </span>
              <span className="quest-step">
                <span className="dot dot--blue" />
                <span className="quest-step__bar quest-step__bar--blue" />
              </span>
              <span className="dot dot--green" />
            </div>
          </div>
          <button className="quest__confirm">Подтвердить</button>
          <div className="quest__row">
            <span>Текст</span>
            <span>+</span>
          </div>
          <button className="quest__self">Самоотчёт</button>
        </section>
      </div>
    </div>
  )
}