import { useState } from 'react'

type LeaderTab = 'agents' | 'squads'

const AGENT_ITEMS = [
  { rank: 1, title: 'Никнейм', delta: '+47', badgeClass: 'rank-badge rank-badge--first' },
  { rank: 2, title: 'Никнейм', delta: '+35', badgeClass: 'rank-badge rank-badge--second' },
  { rank: 3, title: 'Никнейм', delta: '+28', badgeClass: 'rank-badge rank-badge--third' },
  { rank: 4, title: 'Никнейм', delta: '+21', badgeClass: 'rank-badge rank-badge--default' },
  { rank: 5, title: 'Никнейм', delta: '+15', badgeClass: 'rank-badge rank-badge--default' },
]

const SQUAD_ITEMS = [
  { rank: 1, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--first' },
  { rank: 2, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--second' },
  { rank: 3, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--third' },
  { rank: 4, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--default' },
  { rank: 5, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--default' },
]

const FILTER_OPTIONS = ['Все курсы', 'Курс 1', 'Курс 2', 'Курс 3', 'Курс 4']

export default function Leaderboard() {
  const [activeTab, setActiveTab] = useState<LeaderTab>('squads')
  const [searchQuery, setSearchQuery] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [selectedFilter, setSelectedFilter] = useState('Все курсы')

  const items = activeTab === 'agents' ? AGENT_ITEMS : SQUAD_ITEMS
  const filteredItems = items.filter((item) =>
    item.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="dashboard leaderboard-page page-enter">
      <div className="leaderboard-controls">
        <div className="leaderboard-tabs">
          <button
            type="button"
            className={`leaderboard-tab${activeTab === 'agents' ? ' leaderboard-tab--active' : ''}`}
            onClick={() => setActiveTab('agents')}
          >
            Агенты
          </button>
          <button
            type="button"
            className={`leaderboard-tab${activeTab === 'squads' ? ' leaderboard-tab--active' : ''}`}
            onClick={() => setActiveTab('squads')}
          >
            Отряды
          </button>
        </div>
        <div className="leaderboard-filters-frame" style={{ position: 'relative' }}>
          <button
            type="button"
            className="leaderboard-filter-button"
            onClick={() => setShowFilters((v) => !v)}
          >
            Фильтры
          </button>
          {showFilters && (
            <div
              className="popup"
              style={{
                position: 'absolute',
                top: '56px',
                right: 0,
                background: '#f5f5f5',
                borderRadius: '12px',
                border: '4px solid #9a33f4',
                boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)',
                padding: '12px 0',
                minWidth: '180px',
                zIndex: 60,
              }}
            >
              {FILTER_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => { setSelectedFilter(opt); setShowFilters(false) }}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: '8px 20px',
                    border: 'none',
                    background: selectedFilter === opt ? '#9a33f4' : 'transparent',
                    color: selectedFilter === opt ? '#f5f5f5' : '#121212',
                    fontFamily: 'Montserrat, sans-serif',
                    fontWeight: 600,
                    fontSize: '16px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    transition: 'background 0.2s',
                  }}
                >
                  {opt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <section className="leaderboard-card">
        <div className="leaderboard-card__header">
          <h2>{activeTab === 'agents' ? 'Топ 10 агентов' : 'Топ 10 отрядов'}</h2>
        </div>

        <div className="leaderboard-search" style={{ position: 'relative' }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск"
            style={{
              border: 'none',
              outline: 'none',
              background: 'transparent',
              fontFamily: 'Montserrat, sans-serif',
              fontSize: '20px',
              fontWeight: 600,
              color: '#121212',
              width: '100%',
            }}
          />
          <svg viewBox="0 0 26 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="10.11" cy="10.11" r="8.11" stroke="#848484" strokeWidth="4" />
            <line x1="17.6" y1="17.11" x2="25.67" y2="25.17" stroke="#848484" strokeWidth="4" strokeLinecap="round" />
          </svg>
        </div>

        <div className="leaderboard-panel">
          <div className="leaderboard-list">
            {filteredItems.map((item) => (
              <div className="leaderboard-item hover-lift" key={item.rank}>
                <div className={item.badgeClass}>{item.rank}</div>
                <div className="leaderboard-item__card">
                  <div className="leaderboard-item__tags">
                    <span className="tag tag--title">{item.title}</span>
                    <span className="tag tag--delta">Дельта роста:</span>
                    <span className="tag tag--gain">{item.delta}</span>
                  </div>
                  <button type="button" className="leaderboard-item__button">
                    Рейтинг
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="leaderboard-divider" />

          <div className="leaderboard-item leaderboard-item--my-squad">
            <div className="rank-badge rank-badge--bottom">56</div>
            <div className="leaderboard-item__card leaderboard-item__card--bottom">
              <div className="leaderboard-item__tags">
                <span className="tag tag--title">{activeTab === 'agents' ? 'Я' : 'Мой отряд'}</span>
                <span className="tag tag--delta">Дельта роста:</span>
                <span className="tag tag--gain">+47</span>
              </div>
              <button type="button" className="leaderboard-item__button">
                Рейтинг
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
