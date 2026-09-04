import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import LoadError from '../components/LoadError'
import { useCountUp } from '../useCountUp'
import { unwrapList } from '../lib/apiData'

type LeaderTab = 'agents' | 'squads'

interface LeaderItem {
  username: string
  rank: number
  title: string
  delta: string
  badgeClass: string
  track?: string
  status?: string
  avatar?: string | null
}

const COURSE_OPTIONS = [1, 2, 3, 4]

const getBadgeClass = (rank: number) => {
  if (rank === 1) return 'rank-badge rank-badge--first'
  if (rank === 2) return 'rank-badge rank-badge--second'
  if (rank === 3) return 'rank-badge rank-badge--third'
  return 'rank-badge rank-badge--default'
}

function FilterPanel({
  course, onCourse, onClose,
}: {
  course: number | null
  onCourse: (v: number | null) => void
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  return (
    <div ref={ref} className="leaderboard-filters">
      <div className="leaderboard-filters__group">
        <h4 className="leaderboard-filters__title">Трек:</h4>
        <p className="leaderboard-filters__note">
          Список треков API пока не отдаёт
        </p>
      </div>
      <div className="leaderboard-filters__group">
        <h4 className="leaderboard-filters__title">Курс:</h4>
        {COURSE_OPTIONS.map((option) => (
          <button
            key={option}
            type="button"
            className="leaderboard-filters__option"
            onClick={() => onCourse(course === option ? null : option)}
          >
            <span
              className={`leaderboard-filters__radio${course === option ? ' leaderboard-filters__radio--on' : ''}`}
              aria-hidden="true"
            />
            {option}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function Leaderboard() {
  const [activeTab, setActiveTab] = useState<LeaderTab>('agents')
  const [searchQuery, setSearchQuery] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [selectedCourse, setSelectedCourse] = useState<number | null>(null)
  const [totalAgents, setTotalAgents] = useState(0)
  const [agents, setAgents] = useState<LeaderItem[]>([])
  const [squads, setSquads] = useState<LeaderItem[]>([])
  const [myRank, setMyRank] = useState({ rank: 0, delta: '0' })
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [transitioning, setTransitioning] = useState(false)
  const [debouncedSearch, setDebouncedSearch] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery.trim()), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Анимация чисел
  const animMyRank = useCountUp(myRank.rank, 1200)

  const switchTab = (tab: LeaderTab) => {
    if (tab === activeTab) return
    setTransitioning(true)
    setTimeout(() => {
      setActiveTab(tab)
      setTransitioning(false)
    }, 280)
  }

  const loadLeaderboard = useCallback(() => {
    setLoading(true)
    setLoadError(false)
    const agentsParams: Record<string, string | number> = { page: 1, page_size: 20 }
    if (selectedCourse) agentsParams.course = selectedCourse
    if (debouncedSearch) agentsParams.search = debouncedSearch

    Promise.all([
      api.get('/api/v1/leaderboard/agents/', { params: agentsParams }),
      api.get('/api/v1/squads/leaderboard/', { params: { limit: 10 } }),
      api.get('/api/v1/rating/me/'),
    ]).then(([agentsRes, squadsRes, meRes]) => {
      const page = 1
      const pageSize = 20
      const agentsData = unwrapList<{
        username: string
        callsign: string
        rating_current: number
        level: number
        track?: string
        avatar?: string | null
      }>(agentsRes.data)
      setTotalAgents(agentsRes.data?.count ?? agentsData.length)

      const squadsData = unwrapList<{
        code: string
        name: string
        avg_rating: number
        agents_count: number
        course: number
      }>(squadsRes.data)

      setAgents(agentsData.map((item, i) => ({
        username: item.username,
        rank: (page - 1) * pageSize + i + 1,
        title: item.callsign || item.username,
        delta: String(item.rating_current ?? 0),
        badgeClass: getBadgeClass((page - 1) * pageSize + i + 1),
        track: item.track,
        status: item.level ? `${item.level} ур.` : undefined,
        avatar: item.avatar ?? null,
      })))

      setSquads(squadsData.map((item, i) => ({
        username: item.code,
        rank: i + 1,
        title: item.name,
        delta: String(item.avg_rating ?? 0),
        badgeClass: getBadgeClass(i + 1),
      })))

      setMyRank({
        rank: meRes.data?.rank ?? 0,
        delta: String(meRes.data?.rating_current ?? 0),
      })
    }).catch(() => {
      setAgents([])
      setSquads([])
      setLoadError(true)
    }).finally(() => setLoading(false))
  }, [selectedCourse, debouncedSearch])

  useEffect(() => {
    loadLeaderboard()
  }, [loadLeaderboard])

  const items = activeTab === 'agents' ? agents : squads
  const filteredItems = activeTab === 'agents'
    ? items
    : items.filter(item => item.title.toLowerCase().includes(searchQuery.toLowerCase()))

  const navigate = useNavigate()

  if (loading) {
    return (
      <div className="dashboard leaderboard-page page-enter">
        <div className="leaderboard-loading">
          <div className="loading-spinner">
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
          </div>
          <p className="loading-text">Загрузка лидерборда...</p>
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="dashboard leaderboard-page page-enter">
        <LoadError className="leaderboard-loading" onRetry={loadLeaderboard} />
      </div>
    )
  }

  return (
    <div className="dashboard leaderboard-page page-enter">
      <div className="leaderboard-controls">
        <div className="leaderboard-tabs">
          <button
            type="button"
            className={`leaderboard-tab${activeTab === 'agents' ? ' leaderboard-tab--active' : ''} btn-press`}
            onClick={() => { switchTab('agents') }}
          >Агенты</button>
          <button
            type="button"
            className={`leaderboard-tab${activeTab === 'squads' ? ' leaderboard-tab--active' : ''} btn-press`}
            onClick={() => { switchTab('squads') }}
          >Отряды</button>
        </div>
        <div className="leaderboard-filters-frame" style={{ position: 'relative' }}>
          <button
            type="button"
            className="leaderboard-filter-button btn-press"
            onClick={() => setShowFilters(v => !v)}
          >Фильтры</button>
          {showFilters && (
            <FilterPanel
              course={selectedCourse}
              onCourse={setSelectedCourse}
              onClose={() => setShowFilters(false)}
            />
          )}
        </div>
      </div>

      <section className="leaderboard-card">
        <div className="leaderboard-card__header">
          <h2>{activeTab === 'agents' ? 'Топ 20 агентов' : 'Топ 10 отрядов'}</h2>
        </div>

        <div className="leaderboard-search">
          <input
            type="text" value={searchQuery}
            onChange={e => { setSearchQuery(e.target.value) }}
            placeholder={activeTab === 'agents' ? 'Поиск по позывному...' : 'Поиск по названию...'}
            style={{
              border: 'none', outline: 'none', background: 'transparent',
              fontFamily: 'Montserrat, sans-serif', fontSize: '20px',
              fontWeight: 600, color: '#121212', width: '100%',
            }}
          />
          <svg viewBox="0 0 26 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="10.11" cy="10.11" r="8.11" stroke="#848484" strokeWidth="4" />
            <line x1="17.6" y1="17.11" x2="25.67" y2="25.17" stroke="#848484" strokeWidth="4" strokeLinecap="round" />
          </svg>
        </div>

        <div className={`leaderboard-panel${transitioning ? ' leaderboard-panel--transitioning' : ''}`}>
          <div className="leaderboard-list">
            {filteredItems.map((item, i) => (
              <div 
                className="leaderboard-item hover-lift" 
                key={item.username} 
                style={{ animationDelay: `${Math.min(i * 30, 600)}ms` }}
              >
                <div className={item.badgeClass}>{item.rank}</div>
                <div className={`leaderboard-item__card leaderboard-item__card--rank-${Math.min(item.rank, 4)}`}>
                  <div className="leaderboard-item__tags">
                    {activeTab === 'agents' && (
                      <span className="leaderboard-item__avatar" aria-hidden="true">
                        {item.avatar
                          ? <img src={item.avatar} alt="" />
                          : item.title.slice(0, 2).toUpperCase()}
                      </span>
                    )}
                    <span className="tag tag--title">{item.title}</span>
                    {item.track && <span className="tag tag--track">{item.track}</span>}
                    {item.status && <span className="tag tag--status">{item.status}</span>}
                  </div>
                  <button
                    type="button"
                    className="leaderboard-item__rating btn-press"
                    onClick={() => activeTab === 'agents' && navigate(`/profile/${item.username}`)}
                  >
                    {item.delta}
                  </button>
                </div>
              </div>
            ))}
            {filteredItems.length === 0 && (
              <div className="leaderboard-empty" style={{
                textAlign: 'center', padding: '40px 20px', color: '#848484',
                fontFamily: 'Montserrat, sans-serif', fontSize: '18px', fontWeight: 600
              }}>
                <p>Ничего не найдено</p>
              </div>
            )}
          </div>

          <div className="leaderboard-divider" />

          <button
            type="button"
            className="leaderboard-myplace btn-press"
            onClick={() => navigate('/profile')}
          >
            Моё место: <strong>{animMyRank}</strong>
            {totalAgents ? <> из {totalAgents}</> : null}
          </button>
        </div>
      </section>
    </div>
  )
}