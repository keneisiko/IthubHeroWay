import { useEffect, useMemo, useRef, useState } from 'react'
import { Radar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from 'chart.js'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

const radarData = {
  labels: ['Ритм', 'Фокус', 'Мощность', 'Связь', 'Отдача'],
  datasets: [
    {
      label: 'Внешний контур',
      data: [17, 17, 17, 17, 17],
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
      label: 'Внутренний контур',
      data: [14, 14, 14, 14, 14],
      backgroundColor: 'rgba(154, 51, 244, 0.08)',
      borderColor: '#9A33F4',
      borderWidth: 4,
      borderDash: [8, 6],
      pointRadius: 0,
      pointHoverRadius: 0,
    },
  ],
}

const radarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      beginAtZero: true,
      max: 20,
      ticks: { display: false, stepSize: 5 },
      grid: { color: 'rgba(154, 51, 244, 1)', lineWidth: 4 },
      angleLines: { color: 'rgba(154, 51, 244, 1)', lineWidth: 4 },
      pointLabels: { display: false },
    },
  },
  layout: { padding: 0 },
  elements: { line: { tension: 0 } },
  animation: { duration: 0 },
  plugins: { legend: { display: false }, tooltip: { enabled: false } },
} as const

export default function Profile() {
  const tabs = useMemo(
    () => ['Путь', 'Ритм', 'Мастерство', 'Сообщество', 'Вклад', 'Статус', 'Особые'],
    [],
  )
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>('Путь')
  const [activeAxis, setActiveAxis] = useState<string | null>(null)
  const tabsRef = useRef<HTMLDivElement | null>(null)
  const tabButtonRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const [indicatorStyle, setIndicatorStyle] = useState<{ left: number; width: number }>({ left: 0, width: 65 })
  const achievementsPreview = [
    { name: 'Название', rarity: 'Обычный', rarityClass: 'ach__rarity--common' },
    { name: 'Название', rarity: 'Редкий', rarityClass: 'ach__rarity--rare' },
    { name: 'Название', rarity: 'Эпический', rarityClass: 'ach__rarity--epic' },
  ] as const
  const pathCards = [
    { name: 'Название', rarity: 'Обычный', rarityClass: 'path-card__chip--common', iconClass: 'path-card__icon--common' },
    { name: 'Название', rarity: 'Редкий', rarityClass: 'path-card__chip--rare', iconClass: 'path-card__icon--rare' },
    { name: 'Название', rarity: 'Эпический', rarityClass: 'path-card__chip--epic', iconClass: 'path-card__icon--epic' },
    { name: 'Название', rarity: 'Легендарный', rarityClass: 'path-card__chip--legendary', iconClass: 'path-card__icon--legendary' },
  ] as const
  const toggleAxis = (axis: string) => {
    setActiveAxis((current) => (current === axis ? null : axis))
  }
  const historyByAxis: Record<string, number[]> = {
    Мощность: [4, 7, 9, 11, 14, 17],
    Связь: [3, 6, 8, 10, 12, 17],
    Фокус: [5, 7, 8, 11, 13, 17],
    Ритм: [2, 5, 7, 10, 13, 17],
    Отдача: [4, 6, 9, 10, 12, 17],
  }
  const activeHistory = activeAxis ? historyByAxis[activeAxis] : historyByAxis.Мощность

  useEffect(() => {
    const updateIndicator = () => {
      const container = tabsRef.current
      const activeButton = tabButtonRefs.current[activeTab]
      if (!container || !activeButton) return

      const containerRect = container.getBoundingClientRect()
      const activeRect = activeButton.getBoundingClientRect()
      setIndicatorStyle({
        left: activeRect.left - containerRect.left,
        width: activeRect.width,
      })
    }

    updateIndicator()
    window.addEventListener('resize', updateIndicator)
    return () => window.removeEventListener('resize', updateIndicator)
  }, [activeTab])

  return (
    <div className="profile">
      <div className="profile__top">
        <div className="profile__left">
          <section className="profile-card profile-card--primary">
            <div className="profile-card__header">
              <div className="profile-card__avatar" role="img" aria-label="Аватар">
                ИП
              </div>
              <div className="profile-card__names">
                <div className="profile-card__nickname">Никнейм</div>
                <div className="profile-card__fio">ФИО</div>
              </div>
            </div>

            <div className="profile-card__rows">
              <div className="profile-row">
                <span className="profile-row__label">Трек:</span>
                <span className="profile-row__chip profile-row__chip--dark">Код - программирование</span>
              </div>
              <div className="profile-row">
                <span className="profile-row__label">Отряд:</span>
                <span className="profile-row__chip profile-row__chip--light">Учебная группа</span>
              </div>
              <div className="profile-row">
                <span className="profile-row__label">Статус и уровень:</span>
                <span className="profile-row__chip profile-row__chip--dark">Стажёр ур. 3</span>
              </div>
            </div>
          </section>

          <section className="profile-card profile-card--map">
            <h3 className="profile-map__title">Карта пути:</h3>
            <div className="profile-map__body">
              <div className="profile-map__row">
                <button className="profile-map__node profile-map__node--done" type="button" aria-label="Вход" />
                <span className="profile-map__line profile-map__line--done" />
                <button className="profile-map__node profile-map__node--done profile-map__node--shadow" type="button" aria-label="Первая победа" />
                <span className="profile-map__line profile-map__line--done" />
                <button className="profile-map__node profile-map__node--current" type="button" aria-label="Первый провал" />
                <span className="profile-map__line profile-map__line--idle" />
                <button className="profile-map__node profile-map__node--idle profile-map__node--shadow" type="button" aria-label="Первая миссия" />
              </div>
              <div className="profile-map__labels profile-map__labels--top">
                <span>Вход</span>
                <span>Первая<br />победа</span>
                <span>Первый<br />провал</span>
                <span>Первая<br />миссия</span>
              </div>

              <div className="profile-map__row profile-map__row--bottom">
                <span className="profile-map__line profile-map__line--idle profile-map__line--first" />
                <button className="profile-map__node profile-map__node--idle profile-map__node--shadow" type="button" aria-label="Продукт" />
                <span className="profile-map__line profile-map__line--idle" />
                <button className="profile-map__node profile-map__node--idle profile-map__node--shadow" type="button" aria-label="Стажировка" />
                <span className="profile-map__line profile-map__line--idle" />
                <button className="profile-map__node profile-map__node--idle profile-map__node--shadow" type="button" aria-label="Выпуск" />
              </div>
              <div className="profile-map__labels profile-map__labels--bottom">
                <span>Продукт</span>
                <span>Стажировка</span>
                <span>Выпуск</span>
              </div>
            </div>
          </section>
        </div>

        <section className="profile-card profile-card--aside">
          <button className="profile-aside__btn">Настроить профиль</button>
          <div className="profile-aside__divider" />

          <h3 className="profile-aside__title">Статистика:</h3>
          <div className="profile-aside__stats">
            <span className="profile-aside__pill">Выполнено квестов: 47</span>
            <span className="profile-aside__pill">Получено нашивок: 12 из 42</span>
            <span className="profile-aside__pill">Побед в дуелях: 5</span>
          </div>

          <h3 className="profile-aside__title profile-aside__title--sp">Шефство:</h3>
          <button className="profile-aside__mentee">@подшефный</button>
          <button className="profile-aside__mentor-btn">Стать наставником</button>
        </section>
      </div>

      <section className="profile-radar">
        <div className="profile-radar__chart">
          <Radar data={radarData} options={radarOptions} />
        </div>

        <button className="profile-radar__axis profile-radar__axis--top" type="button" onClick={() => toggleAxis('Мощность')}>
          <span className="profile-radar__axis-icon" aria-hidden="true" />
          <span>Мощность</span>
        </button>
        <button className="profile-radar__axis profile-radar__axis--left" type="button" onClick={() => toggleAxis('Связь')}>
          <span className="profile-radar__axis-icon" aria-hidden="true" />
          <span>Связь</span>
        </button>
        <button className="profile-radar__axis profile-radar__axis--right" type="button" onClick={() => toggleAxis('Фокус')}>
          <span className="profile-radar__axis-icon" aria-hidden="true" />
          <span>Фокус</span>
        </button>
        <button className="profile-radar__axis profile-radar__axis--bottom-left" type="button" onClick={() => toggleAxis('Ритм')}>
          <span className="profile-radar__axis-icon" aria-hidden="true" />
          <span>Ритм</span>
        </button>
        <button className="profile-radar__axis profile-radar__axis--bottom-right" type="button" onClick={() => toggleAxis('Отдача')}>
          <span className="profile-radar__axis-icon" aria-hidden="true" />
          <span>Отдача</span>
        </button>

        <span className="profile-radar__value profile-radar__value--outer-top">17</span>
        <span className="profile-radar__value profile-radar__value--outer-left">17</span>
        <span className="profile-radar__value profile-radar__value--outer-right">17</span>
        <span className="profile-radar__value profile-radar__value--outer-bottom-left">17</span>
        <span className="profile-radar__value profile-radar__value--outer-bottom-right">17</span>

        <span className="profile-radar__value profile-radar__value--inner-top profile-radar__value--inner">14</span>
        <span className="profile-radar__value profile-radar__value--inner-left profile-radar__value--inner">14</span>
        <span className="profile-radar__value profile-radar__value--inner-right profile-radar__value--inner">14</span>
        <span className="profile-radar__value profile-radar__value--inner-bottom-left profile-radar__value--inner">14</span>
        <span className="profile-radar__value profile-radar__value--inner-bottom-right profile-radar__value--inner">14</span>

        <section className={activeAxis ? 'profile-history profile-history--visible' : 'profile-history'} aria-hidden={!activeAxis}>
          <span className="profile-history__title">История{activeAxis ? `: ${activeAxis}` : ''}</span>
          <div className="profile-history__chart">
            <div className="profile-history__grid" aria-hidden="true">
              {Array.from({ length: 5 }).map((_, i) => (
                <span key={i} className="profile-history__grid-line" />
              ))}
            </div>
            <div className="profile-history__y">
              <span>20</span>
              <span>15</span>
              <span>10</span>
              <span>5</span>
              <span>0</span>
            </div>
            <div className="profile-history__plot">
              {activeHistory.map((v, i) => (
                <span
                  key={`${v}-${i}`}
                  className="profile-history__dot"
                  style={{ left: `${(i / (activeHistory.length - 1)) * 100}%`, bottom: `${(v / 20) * 100}%` }}
                />
              ))}
              <svg className="profile-history__line" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                <polyline
                  points={activeHistory.map((v, i) => `${(i / (activeHistory.length - 1)) * 100},${100 - (v / 20) * 100}`).join(' ')}
                />
              </svg>
            </div>
            <div className="profile-history__x">
              <span>1</span>
              <span>2</span>
              <span>3</span>
              <span>4</span>
              <span>5</span>
              <span>6</span>
            </div>
            <span className="profile-history__x-label">Недели</span>
          </div>
        </section>
      </section>

      <section className="profile-path profile-card">
        <h3 className="profile-achievements__title">Достижения:</h3>
        <div className="profile-achievements__row">
          {achievementsPreview.map((item) => (
            <button key={`${item.name}-${item.rarity}`} className="ach ach--preview" type="button">
              <span className="ach__icon ach__icon--preview" aria-hidden="true">
                <span className="ach__glyph ach__glyph--preview" />
              </span>
              <span className="ach__name">{item.name}</span>
              <span className="ach__rarity">Редкость</span>
            </button>
          ))}
        </div>

        <div className="profile-path__tabs" ref={tabsRef}>
          {tabs.map((t) => (
            <button
              key={t}
              type="button"
              ref={(el) => {
                tabButtonRefs.current[t] = el
              }}
              className={t === activeTab ? 'profile-path__tab profile-path__tab--active' : 'profile-path__tab'}
              onClick={() => setActiveTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="profile-path__underline" aria-hidden="true">
          <div className="profile-path__indicator" style={{ width: `${indicatorStyle.width}px`, left: `${indicatorStyle.left}px` }} />
        </div>

        <div className="profile-path__grid">
          {pathCards.map((card) => (
            <button key={card.rarity} className="path-card" type="button">
              <span className={`path-card__icon ${card.iconClass}`} aria-hidden="true">
                <span className="path-card__glyph" />
              </span>
              <span className="path-card__name">Название</span>
              <span className={`path-card__chip ${card.rarityClass}`}>{card.rarity}</span>
            </button>
          ))}
          {Array.from({ length: 8 }).map((_, i) => (
            <button key={`locked-${i}`} className="path-card path-card--locked" type="button" disabled>
              <span className="path-card__icon path-card__icon--locked" aria-hidden="true">
                <span className="path-card__glyph path-card__glyph--locked" />
              </span>
              <span className="path-card__locked">Условие не выполнено</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}

