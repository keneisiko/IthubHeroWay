import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { useCountUp } from '../useCountUp'

type LeaderTab = 'agents' | 'squads'

interface LeaderItem {
  id: number
  rank: number
  title: string
  delta: string
  badgeClass: string
  track?: string
}

const FILTER_OPTIONS = ['Все курсы', 'Курс 1', 'Курс 2', 'Курс 3', 'Курс 4']

const AGENT_NAMES = [
  'CyberWolf', 'PixelMaster', 'DataNinja', 'CloudRider', 'ByteHunter',
  'NeonFox', 'CodePhantom', 'DevSpark', 'StarCoder', 'QuantumBit',
  'IronHeart', 'SkyWalker', 'NightOwl', 'FireStorm', 'IceBreaker',
  'ThunderBolt', 'FastTrack', 'DeepMind', 'AlphaWave', 'ZeroCool'
]

const SQUAD_NAMES = [
  'Альфа', 'Бета', 'Гамма', 'Дельта', 'Эпсилон',
  'Зета', 'Эта', 'Тета', 'Йота', 'Каппа',
  'Лямбда', 'Мю', 'Ню', 'Кси', 'Омикрон',
  'Пи', 'Ро', 'Сигма', 'Тау', 'Ипсилон'
]

const TRACKS = ['Код', 'Дизайн', 'Менеджмент']

const getBadgeClass = (rank: number) => {
  if (rank === 1) return 'rank-badge rank-badge--first'
  if (rank === 2) return 'rank-badge rank-badge--second'
  if (rank === 3) return 'rank-badge rank-badge--third'
  return 'rank-badge rank-badge--default'
}

function FilterDropdown({
  options, selected, onSelect, onClose
}: {
  options: string[]
  selected: string
  onSelect: (v: string) => void
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
    <div ref={ref} className="popup filter-dropdown" style={{
      position: 'absolute', top: '56px', right: 0,
      background: '#f5f5f5', borderRadius: '12px', border: '4px solid #9a33f4',
      boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '12px 0',
      minWidth: '180px', zIndex: 60,
      animation: 'popIn 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)'
    }}>
      {options.map(opt => (
        <button
          key={opt} type="button"
          onClick={() => { onSelect(opt); onClose() }}
          style={{
            display: 'block', width: '100%', padding: '8px 20px', border: 'none',
            background: selected === opt ? '#9a33f4' : 'transparent',
            color: selected === opt ? '#f5f5f5' : '#121212',
            fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '16px',
            textAlign: 'left', cursor: 'pointer', transition: 'background 0.2s',
          }}
        >{opt}</button>
      ))}
    </div>
  )
}

export default function Leaderboard() {
  const [activeTab, setActiveTab] = useState<LeaderTab>('agents')
  const [searchQuery, setSearchQuery] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [selectedFilter, setSelectedFilter] = useState('Все курсы')
  const [agents, setAgents] = useState<LeaderItem[]>([])
  const [squads, setSquads] = useState<LeaderItem[]>([])
  const [myRank, setMyRank] = useState({ rank: 56, delta: '+47' })
  const [loading, setLoading] = useState(true)
  const [transitioning, setTransitioning] = useState(false)

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

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get('/api/v1/leaderboard/agents/').catch(() => ({ data: [] })),
      api.get('/api/v1/leaderboard/squads/').catch(() => ({ data: [] })),
      api.get('/api/v1/leaderboard/me/').catch(() => ({ data: { rank: 56, delta: '+47' } })),
    ]).then(([agentsRes, squadsRes, meRes]) => {
      const agentsData = agentsRes.data?.length ? agentsRes.data : generateFallbackAgents()
      const squadsData = squadsRes.data?.length ? squadsRes.data : generateFallbackSquads()

      setAgents(agentsData.map((item: any, i: number) => ({
        id: item.id ?? i + 1,
        rank: i + 1,
        title: item.callsign ?? item.title ?? AGENT_NAMES[i] ?? 'Агент',
        delta: item.delta ?? `+${Math.max(1, 50 - i * 2)}`,
        badgeClass: getBadgeClass(i + 1),
        track: item.track ?? TRACKS[i % 3],
      })))

      setSquads(squadsData.map((item: any, i: number) => ({
        id: item.id ?? i + 1,
        rank: i + 1,
        title: item.name ?? item.title ?? SQUAD_NAMES[i] ?? 'Отряд',
        delta: item.delta ?? `+${Math.max(1, 48 - i * 2)}`,
        badgeClass: getBadgeClass(i + 1),
      })))

      setMyRank({ rank: meRes.data?.rank ?? 56, delta: meRes.data?.delta ?? '+0' })
    }).finally(() => setLoading(false))
  }, [])

  const generateFallbackAgents = () =>
    Array.from({ length: 20 }, (_, i) => ({
      id: i + 1,
      callsign: AGENT_NAMES[i],
      delta: `+${Math.max(1, 50 - i * 2)}`,
      track: TRACKS[i % 3],
    }))

  const generateFallbackSquads = () =>
    Array.from({ length: 20 }, (_, i) => ({
      id: i + 1,
      name: SQUAD_NAMES[i],
      delta: `+${Math.max(1, 48 - i * 2)}`,
      course: (i % 4) + 1,
    }))

  const items = activeTab === 'agents' ? agents : squads
  const filteredItems = items.filter(item =>
    item.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const navigate = useNavigate()

  const handleFilterSelect = useCallback((filter: string) => {
    setSelectedFilter(filter)
  }, [])

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
          >{selectedFilter}</button>
          {showFilters && (
            <FilterDropdown
              options={FILTER_OPTIONS}
              selected={selectedFilter}
              onSelect={handleFilterSelect}
              onClose={() => setShowFilters(false)}
            />
          )}
        </div>
      </div>

      <section className="leaderboard-card">
        <div className="leaderboard-card__header">
          <h2>{activeTab === 'agents' ? 'Топ агентов' : 'Топ отрядов'}</h2>
          <span className="leaderboard-count">
            <span className="leaderboard-count__number">{filteredItems.length}</span>
            <span>{activeTab === 'agents' ? 'агентов' : 'отрядов'}</span>
          </span>
        </div>

        <div className="leaderboard-search">
          <input
            type="text" value={searchQuery}
            onChange={e => { setSearchQuery(e.target.value) }}
            placeholder="Поиск по названию..."
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
                key={item.id} 
                style={{ animationDelay: `${Math.min(i * 30, 600)}ms` }}
              >
                <div className={item.badgeClass}>{item.rank}</div>
                <div className="leaderboard-item__card">
                  <div className="leaderboard-item__tags">
                    <span className="tag tag--title">{item.title}</span>
                    {item.track && (
                      <span className="tag tag--track">{item.track}</span>
                    )}
                    <span className="tag tag--delta">Дельта:</span>
                    <span className="tag tag--gain">{item.delta}</span>
                  </div>
                  <button type="button" className="leaderboard-item__button btn-press" onClick={() => navigate(`/profile/${item.id}`)}>Рейтинг</button>
                </div>
              </div>
            ))}
            {filteredItems.length === 0 && (
              <div className="leaderboard-empty" style={{
                textAlign: 'center', padding: '40px 20px', color: '#848484',
                fontFamily: 'Montserrat, sans-serif', fontSize: '18px', fontWeight: 600
              }}>
                <span style={{ fontSize: '40px', display: 'block', marginBottom: '12px' }}>🔍</span>
                <p>Ничего не найдено</p>
              </div>
            )}
          </div>

          <div className="leaderboard-divider" />

          <div className="leaderboard-item leaderboard-item--my-squad">
            <div className="rank-badge rank-badge--bottom">{animMyRank}</div>
            <div className="leaderboard-item__card leaderboard-item__card--bottom">
              <div className="leaderboard-item__tags">
                <span className="tag tag--title">{activeTab === 'agents' ? 'Моя позиция' : 'Мой отряд'}</span>
                <span className="tag tag--delta">Дельта:</span>
                <span className="tag tag--gain">{myRank.delta}</span>
              </div>
              <button type="button" className="leaderboard-item__button btn-press" onClick={() => navigate('/profile')}>Рейтинг</button>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}