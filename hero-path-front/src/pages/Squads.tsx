import { useState, useRef, useEffect } from 'react'
import userAvatar from '../assets/branding/user-avatar.png'
import api from '../api'

type SortKey = 'name' | 'track' | 'status'

interface Member {
  id: number
  name: string
  track: string
  status: string
}

interface SquadData {
  name: string
  course: number
  rating: number
  members_count: number
  delta: string
  rank: string
  bonus_progress: number
  bonus_completed: number
  bonus_total: number
  coins_month: number
}

interface SearchResult {
  id: number
  name: string
}

export default function Squads() {
  const [showInvite, setShowInvite] = useState(false)
  const [inviteSearch, setInviteSearch] = useState('')
  const [showSort, setShowSort] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [members, setMembers] = useState<Member[]>([
    { id: 1, name: 'Никнейм', track: 'Код', status: 'Активен' },
    { id: 2, name: 'Никнейм', track: 'Дизайн', status: 'Неактивен' },
    { id: 3, name: 'Никнейм', track: 'Код', status: 'Активен' },
    { id: 4, name: 'Никнейм', track: 'Менеджмент', status: 'Активен' },
  ])
  const [squad, setSquad] = useState<SquadData | null>(null)
  const [searchResults, setSearchResults] = useState<SearchResult[]>([
    { id: 101, name: 'Агент_1' },
    { id: 102, name: 'Агент_2' },
    { id: 103, name: 'Агент_3' },
  ])
  const sortRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.get('/api/v1/squad/my/').then(res => {
      setSquad(res.data)
    }).catch(() => {})

    api.get('/api/v1/squad/members/').then(res => {
      if (res.data?.length) setMembers(res.data)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!inviteSearch) return
    const timer = setTimeout(() => {
      api.get(`/api/v1/users/search/?q=${inviteSearch}`).then(res => {
        if (res.data?.length) setSearchResults(res.data)
      }).catch(() => {})
    }, 300)
    return () => clearTimeout(timer)
  }, [inviteSearch])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (sortRef.current && !sortRef.current.contains(e.target as Node)) setShowSort(false)
    }
    if (showSort) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showSort])

  const sortedMembers = [...members].sort((a, b) => a[sortKey].localeCompare(b[sortKey]))
  const filteredResults = searchResults.filter(r => r.name.toLowerCase().includes(inviteSearch.toLowerCase()))

  return (
    <div className="dashboard squad-page page-enter">
      <div className="squad-page__top">
        <section className="squad-my" aria-labelledby="squad-my-title">
          <div className="squad-my__title-row">
            <h2 id="squad-my-title" className="squad-my__title">{squad?.name ?? 'Название отряда'}</h2>
            <div className="squad-my__course"><span>Курс: {squad?.course ?? 2}</span></div>
          </div>
          <dl className="squad-my__stats">
            <div className="squad-my__row">
              <dt className="squad-my__label">Рейтинг:</dt>
              <dd><span className="squad-pill squad-pill--dark squad-pill--firs">{squad?.rating ?? 199}</span></dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Агентов:</dt>
              <dd><span className="squad-pill squad-pill--light">{squad?.members_count ?? 19}</span></dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Дельта роста за неделю:</dt>
              <dd>
                <span className="squad-pill squad-pill--dark squad-pill--delta">
                  {squad?.delta ?? '+47'}
                  <svg className="squad-pill__arrow" width="14" height="7" viewBox="0 0 14 7" fill="none" aria-hidden="true">
                    <path d="M2 6L7 1L12 6" stroke="#6CD63E" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              </dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Место в общем рейтинге отрядов:</dt>
              <dd><span className="squad-pill squad-pill--dark squad-pill--wide">{squad?.rank ?? '3 место из 18'}</span></dd>
            </div>
          </dl>
        </section>

        <div className="squad-page__right">
          <section className="squad-bonus" aria-label="Прогресс командного бонуса">
            <p className="squad-bonus__lead">{squad?.bonus_progress ?? 80}% отряда выполнили еженедельный квест</p>
            <div className="squad-bonus__chip squad-bonus__chip--purple">При 80% - вы получите +5 монет в пятницу</div>
            <div className="squad-bonus__chip squad-bonus__chip--dark">
              <span className="squad-bonus__chip-num">{squad?.bonus_completed ?? 12}</span>
              <span> из {squad?.bonus_total ?? 15} агентов выполнили</span>
            </div>
            <div className="squad-bonus__progress-block">
              <p className="squad-bonus__hint">До бонуса осталось {(squad?.bonus_total ?? 15) - (squad?.bonus_completed ?? 12)} человека</p>
              <div className="squad-bonus__progress">
                <span className="squad-bonus__dot squad-bonus__dot--start" aria-hidden="true" />
                <div className="squad-bonus__track">
                  <div className="squad-bonus__track-slot">
                    <div className="squad-bonus__fill" style={{ width: `${squad?.bonus_progress ?? 80}%` }} />
                  </div>
                </div>
                <span className="squad-bonus__dot squad-bonus__dot--end" aria-hidden="true" />
              </div>
            </div>
          </section>

          <section className="squad-actions" aria-label="Действия отряда">
            <div className="squad-actions__coins">
              <span className="squad-actions__coins-text">В этом месяце отряд получил</span>
              <span className="squad-actions__coins-badge">{squad?.coins_month ?? 340}</span>
              <span className="squad-actions__coins-text">монет</span>
            </div>
            <button type="button" className="squad-actions__btn squad-actions__btn--share">поделиться</button>
            <button type="button" className="squad-actions__btn squad-actions__btn--invite" onClick={() => setShowInvite(true)}>пригласить</button>
          </section>
        </div>
      </div>

      <section className="squad-members" aria-labelledby="squad-members-title">
        <div className="squad-members__head">
          <h2 id="squad-members-title" className="squad-members__title">Участники отряда</h2>
          <div ref={sortRef} style={{ position: 'relative' }}>
            <button type="button" className="squad-members__sort" onClick={() => setShowSort(v => !v)}>Сортировка</button>
            {showSort && (
              <div className="popup" style={{ position: 'absolute', top: '44px', right: 0, background: '#f5f5f5', borderRadius: '12px', border: '4px solid #9a33f4', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '8px 0', minWidth: '160px', zIndex: 60 }}>
                {(['name', 'track', 'status'] as SortKey[]).map(key => (
                  <button key={key} type="button" onClick={() => { setSortKey(key); setShowSort(false) }} style={{ display: 'block', width: '100%', padding: '8px 20px', border: 'none', background: sortKey === key ? '#9a33f4' : 'transparent', color: sortKey === key ? '#f5f5f5' : '#121212', fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '16px', textAlign: 'left', cursor: 'pointer' }}>
                    {{ name: 'По имени', track: 'По треку', status: 'По статусу' }[key]}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="squad-members__search">
          <span>Поиск</span>
          <svg viewBox="0 0 26 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="10.11" cy="10.11" r="8.11" stroke="#848484" strokeWidth="4" />
            <line x1="17.6" y1="17.11" x2="25.67" y2="25.17" stroke="#848484" strokeWidth="4" strokeLinecap="round" />
          </svg>
        </div>

        <div className="squad-members__panel">
          <ul className="squad-members__list">
            {sortedMembers.map(m => (
              <li key={m.id} className="squad-member-row hover-lift">
                <div className="squad-member-row__main">
                  <img className="squad-member-row__avatar" src={userAvatar} alt="" width={50} height={50} />
                  <div className="squad-member-row__tags">
                    <span className="squad-member-tag squad-member-tag--dark">{m.name}</span>
                    <span className="squad-member-tag squad-member-tag--purple">{m.track}</span>
                    <span className="squad-member-tag squad-member-tag--purple">{m.status}</span>
                  </div>
                </div>
                <button type="button" className="squad-member-row__rating">Рейтинг</button>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {showInvite && (
        <div className="overlay" onClick={() => setShowInvite(false)}>
          <div className="popup" onClick={e => e.stopPropagation()} style={{ background: '#f5f5f5', borderRadius: '24px', border: '4px solid #9a33f4', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '20px', width: '460px', maxWidth: '90vw', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '28px', color: '#9a33f4', margin: 0 }}>Пригласить в отряд</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: '#f5f5f5', borderRadius: '12px', border: '4px solid #9a33f4', boxShadow: '25px 25px 20px -14px rgba(0,0,0,0.45)', padding: '9px 11px' }}>
              <input
                type="text" value={inviteSearch} onChange={e => setInviteSearch(e.target.value)}
                placeholder="Поиск агента"
                style={{ border: 'none', outline: 'none', background: 'transparent', fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '20px', color: '#121212', width: '100%' }}
              />
              <svg viewBox="0 0 26 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style={{ flexShrink: 0 }}>
                <circle cx="10.11" cy="10.11" r="8.11" stroke="#848484" strokeWidth="4" />
                <line x1="17.6" y1="17.11" x2="25.67" y2="25.17" stroke="#848484" strokeWidth="4" strokeLinecap="round" />
              </svg>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filteredResults.map(result => (
                <div key={result.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', background: '#f5f5f5', borderRadius: '8px', border: '4px solid #9a33f4', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '14px' }}>
                  <img src={userAvatar} alt="" style={{ width: '50px', height: '50px', borderRadius: '50%', border: '3px solid #9a33f4' }} />
                  <div style={{ flex: 1 }}>
                    <span style={{ background: '#121212', borderRadius: '48px', padding: '4px 16px', fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '16px', color: '#f5f5f5' }}>{result.name}</span>
                  </div>
                  <button type="button" style={{ background: '#9a33f4', height: '46px', borderRadius: '4px', padding: '8px 16px', border: 'none', fontFamily: 'Montserrat, sans-serif', fontWeight: 700, fontSize: '18px', color: '#f5f5f5', cursor: 'pointer' }}>Пригласить</button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}