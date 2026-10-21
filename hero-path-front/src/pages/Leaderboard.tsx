import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import LoadError from '../components/LoadError'
import { useCountUp } from '../useCountUp'
import { unwrapList, formatRating } from '../lib/apiData'
import Avatar from '../components/Avatar'

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
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [onClose])

  return (
    <div ref={ref} className="leaderboard-filters">
      {/* фильтра по треку пока нет на сервере — пустую группу со
          служебной припиской «API не отдаёт» студенту не показываем */}
      <div className="leaderboard-filters__group">
        <h4 className="leaderboard-filters__title">Курс:</h4>
        {COURSE_OPTIONS.map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={course === option}
            className={`leaderboard-filters__option${course === option ? ' leaderboard-filters__option--on' : ''}`}
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
  const [myRank, setMyRank] = useState({ rank: 0, delta: '0', username: '' })
  const myRowRef = useRef<HTMLDivElement | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [transitioning, setTransitioning] = useState(false)
  // Набор фильтрует то, что уже на экране, — мгновенно и без запросов.
  // На сервер (поиск за пределами топа) — только когда человек сам нажал
  // Enter или лупу: раньше запрос уходил после секунды паузы, страница
  // перезагружалась и поле теряло фокус посреди набора.
  const [appliedSearch, setAppliedSearch] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [meOnScreen, setMeOnScreen] = useState(false)
  const loadedOnce = useRef(false)

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (activeTab === 'agents') setAppliedSearch(searchQuery.trim())
  }

  const changeSearch = (value: string) => {
    setSearchQuery(value)
    // поле очистили — вернуть общий топ, ждать Enter тут незачем
    if (!value.trim() && appliedSearch) setAppliedSearch('')
  }

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

  // своя строка на экране — плашка «Моё место» не нужна и не закрывает
  // соседей; уехала за край — плашка возвращается
  useEffect(() => {
    const row = myRowRef.current
    if (!row || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver(([entry]) => setMeOnScreen(entry.isIntersecting), { threshold: 0.6 })
    io.observe(row)
    return () => {
      io.disconnect()
      setMeOnScreen(false)
    }
  }, [agents, activeTab, appliedSearch, loading])

  // «Моё место»: если ты в списке — прокрутить к своей строке и мигнуть
  // ей, иначе открыть свой профиль
  const goToMyPlace = () => {
    const row = myRowRef.current
    if (!row) { navigate('/profile'); return }
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    row.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' })
    row.classList.remove('leaderboard-item--flash')
    void row.offsetWidth
    row.classList.add('leaderboard-item--flash')
  }

  const loadLeaderboard = useCallback(() => {
    // экран загрузки — только в первый раз; дальше список обновляется
    // на месте и не пропадает из-под пальца
    if (loadedOnce.current) setRefreshing(true)
    else setLoading(true)
    setLoadError(false)
    const agentsParams: Record<string, string | number> = { page: 1, page_size: 20 }
    if (selectedCourse) agentsParams.course = selectedCourse
    if (appliedSearch) agentsParams.search = appliedSearch

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
        delta: formatRating(item.rating_current),
        badgeClass: getBadgeClass((page - 1) * pageSize + i + 1),
        track: item.track,
        status: item.level ? `${item.level} ур.` : undefined,
        avatar: item.avatar ?? null,
      })))

      setSquads(squadsData.map((item, i) => ({
        username: item.code,
        rank: i + 1,
        title: item.name,
        delta: formatRating(item.avg_rating),
        badgeClass: getBadgeClass(i + 1),
      })))

      setMyRank({
        rank: meRes.data?.rank ?? 0,
        delta: formatRating(meRes.data?.rating_current),
        username: meRes.data?.username ?? '',
      })
    }).catch(() => {
      if (loadedOnce.current) return
      setAgents([])
      setSquads([])
      setLoadError(true)
    }).finally(() => {
      loadedOnce.current = true
      setLoading(false)
      setRefreshing(false)
    })
  }, [selectedCourse, appliedSearch])

  useEffect(() => {
    loadLeaderboard()
  }, [loadLeaderboard])

  // Общее число агентов берём отдельным запросом без фильтров: count из
  // отфильтрованного списка — это размер выборки, и подпись «моё место из N»
  // показывала, например, «42 из 3» при поиске.
  useEffect(() => {
    api.get('/api/v1/leaderboard/agents/', { params: { page: 1, page_size: 1 } })
      .then((res) => setTotalAgents(res.data?.count ?? 0))
      .catch(() => setTotalAgents(0))
  }, [])

  const items = activeTab === 'agents' ? agents : squads
  const needle = searchQuery.trim().toLowerCase()
  const filteredItems = needle
    ? items.filter(item => item.title.toLowerCase().includes(needle))
    : items
  const canSearchWider = activeTab === 'agents' && needle !== '' && needle !== appliedSearch.toLowerCase()

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

        <form className="leaderboard-search" role="search" onSubmit={submitSearch}>
          <input
            type="search" value={searchQuery}
            onChange={e => changeSearch(e.target.value)}
            placeholder={activeTab === 'agents' ? 'Поиск по позывному...' : 'Поиск по названию...'}
            aria-label={activeTab === 'agents' ? 'Поиск агента по позывному' : 'Поиск отряда по названию'}
            enterKeyHint="search"
            autoComplete="off"
            style={{
              border: 'none', outline: 'none', background: 'transparent',
              fontFamily: 'Montserrat, sans-serif', fontSize: '20px',
              fontWeight: 600, color: '#121212', width: '100%',
            }}
          />
          <button type="submit" className="search-submit" aria-label="Найти">
            <svg viewBox="0 0 26 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <circle cx="10.11" cy="10.11" r="8.11" stroke="#848484" strokeWidth="4" />
              <line x1="17.6" y1="17.11" x2="25.67" y2="25.17" stroke="#848484" strokeWidth="4" strokeLinecap="round" />
            </svg>
          </button>
        </form>

        <div className={`leaderboard-panel${transitioning ? ' leaderboard-panel--transitioning' : ''}${refreshing ? ' leaderboard-panel--refreshing' : ''}`} aria-busy={refreshing}>
          <div className="leaderboard-list">
            {filteredItems.map((item, i) => {
              const isMe = activeTab === 'agents' && item.username === myRank.username
              return (
              <div
                className={`leaderboard-item hover-lift${isMe ? ' leaderboard-item--me' : ''}${activeTab === 'agents' ? ' leaderboard-item--link' : ''}`}
                key={item.username}
                onClick={activeTab === 'agents' ? () => navigate(`/profile/${item.username}`) : undefined}
                ref={isMe ? myRowRef : undefined}
                style={{ animationDelay: `${Math.min(i * 30, 600)}ms` }}
              >
                <div className={item.badgeClass}>{item.rank}</div>
                <div className={`leaderboard-item__card leaderboard-item__card--rank-${Math.min(item.rank, 4)}`}>
                  <div className="leaderboard-item__tags">
                    {activeTab === 'agents' && (
                      <Avatar src={item.avatar} name={item.title} className="leaderboard-item__avatar" />
                    )}
                    <div className="leaderboard-item__meta">
                      <span className="tag tag--title">{item.title}</span>
                      {isMe && <span className="tag tag--me">Это ты</span>}
                      {item.track && <span className="tag tag--track">{item.track}</span>}
                      {item.status && <span className="tag tag--status">{item.status}</span>}
                    </div>
                  </div>
                  {/* переход — по всей строке; кнопка остаётся для клавиатуры,
                      её нажатие всплывает к строке */}
                  <button
                    type="button"
                    className="leaderboard-item__rating"
                    aria-label={activeTab === 'agents' ? `Профиль: ${item.title}, рейтинг ${item.delta}` : undefined}
                    tabIndex={activeTab === 'agents' ? 0 : -1}
                  >
                    {item.delta}
                  </button>
                </div>
              </div>
              )
            })}
            {filteredItems.length === 0 && (
              <div className="leaderboard-empty" style={{
                textAlign: 'center', padding: '40px 20px', color: '#848484',
                fontFamily: 'Montserrat, sans-serif', fontSize: '18px', fontWeight: 600
              }}>
                <p>{canSearchWider ? 'В этом топе таких нет' : 'Ничего не найдено'}</p>
                {canSearchWider && (
                  <button
                    type="button"
                    className="leaderboard-empty__action btn-press"
                    onClick={() => setAppliedSearch(searchQuery.trim())}
                  >
                    Искать среди всех агентов
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="leaderboard-divider" />

          <button
            type="button"
            className={`leaderboard-myplace btn-press${meOnScreen ? ' leaderboard-myplace--away' : ''}`}
            onClick={goToMyPlace}
          >
            Моё место: <strong>{animMyRank}</strong>
            {totalAgents ? <> из {totalAgents}</> : null}
          </button>
        </div>
      </section>
    </div>
  )
}