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
import api from '../api'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

const AXIS_KEYS = ['Мощность', 'Связь', 'Фокус', 'Ритм', 'Отдача'] as const

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
  animation: { duration: 600, easing: 'easeOutQuart' as const },
  plugins: { legend: { display: false }, tooltip: { enabled: false } },
} as const

const AXES = [
  { key: 'Мощность', position: 'profile-radar__axis--top' },
  { key: 'Связь',    position: 'profile-radar__axis--left' },
  { key: 'Фокус',    position: 'profile-radar__axis--right' },
  { key: 'Ритм',     position: 'profile-radar__axis--bottom-left' },
  { key: 'Отдача',   position: 'profile-radar__axis--bottom-right' },
] as const

const VALUE_POSITIONS = [
  { outer: 'profile-radar__value--outer-top',          inner: 'profile-radar__value--inner-top' },
  { outer: 'profile-radar__value--outer-left',         inner: 'profile-radar__value--inner-left' },
  { outer: 'profile-radar__value--outer-right',        inner: 'profile-radar__value--inner-right' },
  { outer: 'profile-radar__value--outer-bottom-left',  inner: 'profile-radar__value--inner-bottom-left' },
  { outer: 'profile-radar__value--outer-bottom-right', inner: 'profile-radar__value--inner-bottom-right' },
]

interface ProfileData {
  callsign: string
  full_name: string
  track: string
  squad: string
  level: number
  status: string
  quests_completed: number
  badges_count: number
  duel_wins: number
  skills: Record<string, { current: number; peak: number; history: number[] }>
}

export default function Profile() {
  const tabs = useMemo(() => ['Путь', 'Ритм', 'Мастерство', 'Сообщество', 'Вклад', 'Статус', 'Особые'], [])
  const [activeTab, setActiveTab] = useState<string>('Путь')
  const [activeAxis, setActiveAxis] = useState<string | null>(null)
  const [hoveredAxis, setHoveredAxis] = useState<string | null>(null)
  const tabsRef = useRef<HTMLDivElement | null>(null)
  const tabButtonRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const [indicatorStyle, setIndicatorStyle] = useState<{ left: number; width: number }>({ left: 0, width: 65 })
  const [profile, setProfile] = useState<ProfileData | null>(null)

  useEffect(() => {
    api.get('/api/v1/profile/me/').then(res => setProfile(res.data)).catch(() => {})
  }, [])

  const getSkill = (key: string) => profile?.skills?.[key] ?? { current: 17, peak: 14, history: [4, 7, 9, 11, 14, 17] }

  const radarData = {
    labels: ['Ритм', 'Фокус', 'Мощность', 'Связь', 'Отдача'],
    datasets: [
      {
        label: 'Текущий',
        data: AXIS_KEYS.map(k => getSkill(k).current),
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
        data: AXIS_KEYS.map(k => getSkill(k).peak),
        backgroundColor: 'rgba(154, 51, 244, 0.08)',
        borderColor: '#9A33F4',
        borderWidth: 4,
        borderDash: [8, 6],
        pointRadius: 0,
        pointHoverRadius: 0,
      },
    ],
  }

  const activeHistory = activeAxis ? getSkill(activeAxis).history : getSkill('Мощность').history
  const toggleAxis = (axis: string) => setActiveAxis(cur => cur === axis ? null : axis)

  useEffect(() => {
    const updateIndicator = () => {
      const container = tabsRef.current
      const activeButton = tabButtonRefs.current[activeTab]
      if (!container || !activeButton) return
      const containerRect = container.getBoundingClientRect()
      const activeRect = activeButton.getBoundingClientRect()
      setIndicatorStyle({ left: activeRect.left - containerRect.left, width: activeRect.width })
    }
    updateIndicator()
    window.addEventListener('resize', updateIndicator)
    return () => window.removeEventListener('resize', updateIndicator)
  }, [activeTab])

  const initials = profile?.callsign?.slice(0, 2).toUpperCase() ?? 'ИП'

  return (
    <div className="profile page-enter">
      <div className="profile__top">
        <div className="profile__left">
          <section className="profile-card profile-card--primary">
            <div className="profile-card__header">
              <div className="profile-card__avatar" role="img" aria-label="Аватар">{initials}</div>
              <div className="profile-card__names">
                <div className="profile-card__nickname">{profile?.callsign ?? 'Никнейм'}</div>
                <div className="profile-card__fio">{profile?.full_name ?? 'ФИО'}</div>
              </div>
            </div>
            <div className="profile-card__rows">
              <div className="profile-row">
                <span className="profile-row__label">Трек:</span>
                <span className="profile-row__chip profile-row__chip--dark">{profile?.track ?? 'Код - программирование'}</span>
              </div>
              <div className="profile-row">
                <span className="profile-row__label">Отряд:</span>
                <span className="profile-row__chip profile-row__chip--light">{profile?.squad ?? 'Учебная группа'}</span>
              </div>
              <div className="profile-row">
                <span className="profile-row__label">Статус и уровень:</span>
                <span className="profile-row__chip profile-row__chip--dark">{profile?.status ?? 'Стажёр'} ур. {profile?.level ?? 3}</span>
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
                <span>Вход</span><span>Первая<br />победа</span><span>Первый<br />провал</span><span>Первая<br />миссия</span>
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
                <span>Продукт</span><span>Стажировка</span><span>Выпуск</span>
              </div>
            </div>
          </section>
        </div>

        <section className="profile-card profile-card--aside">
          <button className="profile-aside__btn">Настроить профиль</button>
          <div className="profile-aside__divider" />
          <h3 className="profile-aside__title">Статистика:</h3>
          <div className="profile-aside__stats">
            <span className="profile-aside__pill">Выполнено квестов: {profile?.quests_completed ?? 0}</span>
            <span className="profile-aside__pill">Получено нашивок: {profile?.badges_count ?? 0}</span>
            <span className="profile-aside__pill">Побед в дуэлях: {profile?.duel_wins ?? 0}</span>
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

        {AXES.map(({ key, position }) => {
          const skill = getSkill(key)
          const isHovered = hoveredAxis === key
          const isTop = position === 'profile-radar__axis--top'
          const isBottom = position.includes('bottom')
          const isLeft = position === 'profile-radar__axis--left'
          const tooltipStyle: React.CSSProperties = isTop
            ? { bottom: 'calc(100% + 8px)', left: '50%', transform: 'translateX(-50%)' }
            : isBottom
              ? { top: 'calc(100% + 8px)', left: '50%', transform: 'translateX(-50%)' }
              : isLeft
                ? { right: 'calc(100% + 8px)', top: '50%', transform: 'translateY(-50%)' }
                : { left: 'calc(100% + 8px)', top: '50%', transform: 'translateY(-50%)' }
          return (
            <div
              key={key}
              className={`profile-radar__axis ${position}`}
              onMouseEnter={() => setHoveredAxis(key)}
              onMouseLeave={() => setHoveredAxis(null)}
              onClick={() => toggleAxis(key)}
              style={{ cursor: 'pointer' }}
            >
              <span className="profile-radar__axis-icon" aria-hidden="true" />
              <span>{key}</span>
              {isHovered && (
                <span className="tooltip" style={tooltipStyle}>
                  {key}: {skill.current} / 20
                </span>
              )}
            </div>
          )
        })}

        {VALUE_POSITIONS.map((pos, i) => {
          const skill = getSkill(AXES[i].key)
          return (
            <span key={`outer-${i}`} className={`profile-radar__value ${pos.outer}`}>
              {skill.current}
            </span>
          )
        })}

        {VALUE_POSITIONS.map((pos, i) => {
          const skill = getSkill(AXES[i].key)
          return (
            <span key={`inner-${i}`} className={`profile-radar__value ${pos.inner} profile-radar__value--inner`}>
              {skill.peak}
            </span>
          )
        })}

        <section className={activeAxis ? 'profile-history profile-history--visible' : 'profile-history'} aria-hidden={!activeAxis}>
          <span className="profile-history__title">История{activeAxis ? `: ${activeAxis}` : ''}</span>
          <div className="profile-history__chart">
            <div className="profile-history__grid" aria-hidden="true">
              {Array.from({ length: 5 }).map((_, i) => (
                <span key={i} className="profile-history__grid-line" />
              ))}
            </div>
            <div className="profile-history__y">
              <span>20</span><span>15</span><span>10</span><span>5</span><span>0</span>
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
              <span>1</span><span>2</span><span>3</span><span>4</span><span>5</span><span>6</span>
            </div>
            <span className="profile-history__x-label">Недели</span>
          </div>
        </section>
      </section>

      <section className="profile-path profile-card">
        <h3 className="profile-achievements__title">Достижения:</h3>
        <div className="profile-achievements__row">
          {['Обычный', 'Редкий', 'Эпический'].map((rarity) => (
            <button key={rarity} className="ach ach--preview hover-lift" type="button">
              <span className="ach__icon ach__icon--preview" aria-hidden="true">
                <span className="ach__glyph ach__glyph--preview" />
              </span>
              <span className="ach__name">Название</span>
              <span className="ach__rarity">Редкость</span>
            </button>
          ))}
        </div>

        <div className="profile-path__tabs" ref={tabsRef}>
          {tabs.map((t) => (
            <button
              key={t} type="button"
              ref={(el) => { tabButtonRefs.current[t] = el }}
              className={t === activeTab ? 'profile-path__tab profile-path__tab--active' : 'profile-path__tab'}
              onClick={() => setActiveTab(t)}
            >{t}</button>
          ))}
        </div>
        <div className="profile-path__underline" aria-hidden="true">
          <div className="profile-path__indicator" style={{ width: `${indicatorStyle.width}px`, left: `${indicatorStyle.left}px` }} />
        </div>

        <div className="profile-path__grid">
          {['Обычный', 'Редкий', 'Эпический', 'Легендарный'].map((rarity) => (
            <button key={rarity} className="path-card hover-lift" type="button">
              <span className={`path-card__icon path-card__icon--${rarity.toLowerCase()}`} aria-hidden="true">
                <span className="path-card__glyph" />
              </span>
              <span className="path-card__name">Название</span>
              <span className={`path-card__chip path-card__chip--${rarity.toLowerCase()}`}>{rarity}</span>
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