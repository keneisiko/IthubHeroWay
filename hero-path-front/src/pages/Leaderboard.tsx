const leaderboardItems = [
  { rank: 1, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--first' },
  { rank: 2, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--second' },
  { rank: 3, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--third' },
  { rank: 4, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--default' },
  { rank: 5, title: 'Название отряда', delta: '+47', badgeClass: 'rank-badge rank-badge--default' },
]

export default function Leaderboard() {
  return (
    <div className="dashboard leaderboard-page">
      <div className="leaderboard-controls">
        <div className="leaderboard-tabs">
          <button type="button" className="leaderboard-tab">
            Агенты
          </button>
          <button type="button" className="leaderboard-tab leaderboard-tab--active">
            Отряды
          </button>
        </div>
        <div className="leaderboard-filters-frame">
          <button type="button" className="leaderboard-filter-button">
            Фильтры
          </button>
        </div>
      </div>

      <section className="leaderboard-card">
        <div className="leaderboard-card__header">
          <h2>Топ 10 отрядов</h2>
        </div>

        <div className="leaderboard-search">
          <span>Поиск</span>
          <svg viewBox="0 0 26 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="10.11" cy="10.11" r="8.11" stroke="#848484" strokeWidth="4" />
            <line x1="17.6" y1="17.11" x2="25.67" y2="25.17" stroke="#848484" strokeWidth="4" strokeLinecap="round" />
          </svg>
        </div>

        <div className="leaderboard-panel">
          <div className="leaderboard-list">
            {leaderboardItems.map((item) => (
              <div className="leaderboard-item" key={item.rank}>
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
                <span className="tag tag--title">Мой отряд</span>
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
