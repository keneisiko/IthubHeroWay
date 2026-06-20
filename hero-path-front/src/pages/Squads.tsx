import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import userAvatar from '../assets/branding/user-avatar.png'
import api from '../api'
import { useToasts } from '../useToasts'

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

function Modal({
  open, onClose, title, children, width = '460px'
}: {
  open: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
  width?: string
}) {
  const [visible, setVisible] = useState(false)
  const [closing, setClosing] = useState(false)

  useEffect(() => {
    if (open) {
      setClosing(false)
      const t = setTimeout(() => setVisible(true), 10)
      return () => clearTimeout(t)
    } else {
      setClosing(true)
      const t = setTimeout(() => setVisible(false), 220)
      return () => clearTimeout(t)
    }
  }, [open])

  if (!visible && !open) return null

  return (
    <div className={`overlay${closing ? ' overlay--closing' : ''}`} onClick={onClose} style={{ background: 'transparent' }}>
      <div className={`popup${closing ? ' popup--closing' : ''}`} onClick={e => e.stopPropagation()} style={{ width, maxWidth: '90vw' }}>
        {title && <h3 className="popup__title">{title}</h3>}
        {children}
      </div>
    </div>
  )
}

function SortDropdown({
  sortKey, onSelect, onClose
}: {
  sortKey: SortKey
  onSelect: (key: SortKey) => void
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

  const options: { key: SortKey; label: string }[] = [
    { key: 'name', label: 'По имени' },
    { key: 'track', label: 'По треку' },
    { key: 'status', label: 'По статусу' },
  ]

  return (
    <div ref={ref} className="popup sort-dropdown" style={{
      position: 'absolute', top: '44px', right: 0,
      background: '#f5f5f5', borderRadius: '12px', border: '4px solid #9a33f4',
      boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '8px 0',
      minWidth: '160px', zIndex: 60,
      animation: 'popIn 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)'
    }}>
      {options.map(opt => (
        <button
          key={opt.key} type="button"
          onClick={() => { onSelect(opt.key); onClose() }}
          style={{
            display: 'block', width: '100%', padding: '8px 20px', border: 'none',
            background: sortKey === opt.key ? '#9a33f4' : 'transparent',
            color: sortKey === opt.key ? '#f5f5f5' : '#121212',
            fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '16px',
            textAlign: 'left', cursor: 'pointer', transition: 'background 0.2s',
          }}
        >{opt.label}</button>
      ))}
    </div>
  )
}


export default function Squads() {
  const [showInvite, setShowInvite] = useState(false)
  const [inviteSearch, setInviteSearch] = useState('')
  const [memberQuery, setMemberQuery] = useState('')
  const [showSort, setShowSort] = useState(false)
  const { toasts, addToast } = useToasts()
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [members, setMembers] = useState<Member[]>([])
  const [squad, setSquad] = useState<SquadData | null>(null)
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])

  useEffect(() => {
    api.get('/api/v1/squad/my/').then(res => setSquad(res.data)).catch(() => addToast('Не удалось загрузить отряд', 'error'))
    api.get('/api/v1/squad/members/').then(res => {
      if (res.data?.length) setMembers(res.data)
    }).catch(() => addToast('Не удалось загрузить участников', 'error'))
  }, [addToast])

  useEffect(() => {
    if (!inviteSearch) return
    const timer = setTimeout(() => {
      api.get(`/api/v1/users/search/?q=${encodeURIComponent(inviteSearch)}`).then(res => {
        setSearchResults(res.data ?? [])
      }).catch(() => addToast('Ошибка поиска пользователей', 'error'))
    }, 300)
    return () => clearTimeout(timer)
  }, [inviteSearch, addToast])

  const sortedMembers = useMemo(() => {
    return [...members].sort((a, b) => a[sortKey].localeCompare(b[sortKey]))
  }, [members, sortKey])

  const visibleMembers = useMemo(() => {
    const q = memberQuery.trim().toLowerCase()
    if (!q) return sortedMembers
    return sortedMembers.filter(m =>
      m.name.toLowerCase().includes(q) ||
      m.track.toLowerCase().includes(q) ||
      m.status.toLowerCase().includes(q)
    )
  }, [sortedMembers, memberQuery])

  const handleShare = useCallback(() => {
    const shareUrl = `${window.location.origin}/squads`
    const shareData = {
      title: `Отряд ${squad?.name ?? 'Альфа-12'}`,
      text: `Присоединяйся к моему отряду «${squad?.name ?? 'Альфа-12'}» в IThub Путь Героя!`,
      url: shareUrl,
    }
    if (navigator.share) {
      navigator.share(shareData).catch(() => {})
      return
    }
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(shareUrl)
        .then(() => addToast('Ссылка на отряд скопирована'))
        .catch(() => addToast('Не удалось скопировать ссылку', 'error'))
    } else {
      addToast('Не удалось скопировать ссылку', 'error')
    }
  }, [squad, addToast])

  const filteredResults = useMemo(() => {
    if (!inviteSearch) return searchResults
    return searchResults.filter(r => r.name.toLowerCase().includes(inviteSearch.toLowerCase()))
  }, [searchResults, inviteSearch])

  const handleInvite = useCallback((userId: number) => {
    api.post(`/api/v1/squad/invite/${userId}/`).then(() => {
      addToast('Приглашение отправлено!', 'success')
    }).catch(() => {
      addToast('Ошибка при отправке приглашения', 'error')
    })
  }, [addToast])

  return (
    <div className="dashboard squad-page page-enter">
      <div className="squad-page__top">
        <section className="squad-my" aria-labelledby="squad-my-title">
          <div className="squad-my__title-row">
            <h2 id="squad-my-title" className="squad-my__title">{squad?.name ?? 'Альфа-12'}</h2>
            <div className="squad-my__course"><span>Курс: {squad?.course ?? 2}</span></div>
          </div>
          <dl className="squad-my__stats">
            <div className="squad-my__row">
              <dt className="squad-my__label">Рейтинг:</dt>
              <dd><span className="squad-pill squad-pill--dark squad-pill--firs">{squad?.rating ?? 199}</span></dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Агентов:</dt>
              <dd><span className="squad-pill squad-pill--light">{squad?.members_count ?? members.length}</span></dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Дельта роста:</dt>
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
              <dt className="squad-my__label">Место в рейтинге:</dt>
              <dd><span className="squad-pill squad-pill--dark squad-pill--wide">{squad?.rank ?? '3 место из 18'}</span></dd>
            </div>
          </dl>
        </section>

        <div className="squad-page__right">
          <section className="squad-bonus" aria-label="Прогресс командного бонуса">
            <p className="squad-bonus__lead">{squad?.bonus_progress ?? 80}% отряда выполнили еженедельный квест</p>
            <div className="squad-bonus__chip squad-bonus__chip--purple">При 80% — +5 монет в пятницу</div>
            <div className="squad-bonus__chip squad-bonus__chip--dark">
              <span className="squad-bonus__chip-num">{squad?.bonus_completed ?? Math.min(members.length, 12)}</span>
              <span> из {squad?.bonus_total ?? members.length} агентов</span>
            </div>
            <div className="squad-bonus__progress-block">
              <p className="squad-bonus__hint">До бонуса осталось {(squad?.bonus_total ?? members.length) - (squad?.bonus_completed ?? Math.min(members.length, 12))} человек</p>
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
              <span className="squad-actions__coins-text">В этом месяце:</span>
              <span className="squad-actions__coins-badge">{squad?.coins_month ?? 340}</span>
              <span className="squad-actions__coins-text">монет</span>
            </div>
            <button type="button" className="squad-actions__btn squad-actions__btn--share btn-press" onClick={handleShare}>Поделиться</button>
            <button type="button" className="squad-actions__btn squad-actions__btn--invite btn-press" onClick={() => setShowInvite(true)}>Пригласить</button>
          </section>
        </div>
      </div>

      <section className="squad-members" aria-labelledby="squad-members-title">
        <div className="squad-members__head">
          <h2 id="squad-members-title" className="squad-members__title">Участники отряда</h2>
          <div style={{ position: 'relative' }}>
            <button type="button" className="squad-members__sort btn-press" onClick={() => setShowSort(v => !v)}>Сортировка</button>
            {showSort && (
              <SortDropdown
                sortKey={sortKey}
                onSelect={setSortKey}
                onClose={() => setShowSort(false)}
              />
            )}
          </div>
        </div>

        <div className="squad-members__search">
          <input
            type="text"
            value={memberQuery}
            onChange={e => setMemberQuery(e.target.value)}
            placeholder="Поиск участника по имени, треку или статусу..."
            className="squad-members__search-input"
            aria-label="Поиск участника отряда"
          />
          <svg viewBox="0 0 26 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="10.11" cy="10.11" r="8.11" stroke="#848484" strokeWidth="4" />
            <line x1="17.6" y1="17.11" x2="25.67" y2="25.17" stroke="#848484" strokeWidth="4" strokeLinecap="round" />
          </svg>
        </div>

        <div className="squad-members__panel">
          <ul className="squad-members__list">
            {visibleMembers.map((m, i) => (
              <li key={m.id} className="squad-member-row hover-lift" style={{ animationDelay: `${i * 40}ms` }}>
                <div className="squad-member-row__main">
                  <img className="squad-member-row__avatar" src={userAvatar} alt="" width={50} height={50} />
                  <div className="squad-member-row__tags">
                    <span className="squad-member-tag squad-member-tag--dark">{m.name}</span>
                    <span className="squad-member-tag squad-member-tag--purple">{m.track}</span>
                    <span className="squad-member-tag squad-member-tag--purple">{m.status}</span>
                  </div>
                </div>
                <button type="button" className="squad-member-row__rating btn-press">Рейтинг</button>
              </li>
            ))}
            {visibleMembers.length === 0 && (
              <li className="squad-members__empty">Никого не найдено</li>
            )}
          </ul>
        </div>
      </section>

      <Modal open={showInvite} onClose={() => setShowInvite(false)} title="Пригласить в отряд">
        <div className="squad-modal__search">
          <input
            type="text" value={inviteSearch} onChange={e => setInviteSearch(e.target.value)}
            placeholder="Поиск агента..."
            className="popup__input"
          />
          <svg viewBox="0 0 26 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="10.11" cy="10.11" r="8.11" stroke="#848484" strokeWidth="4" />
            <line x1="17.6" y1="17.11" x2="25.67" y2="25.17" stroke="#848484" strokeWidth="4" strokeLinecap="round" />
          </svg>
        </div>
        <div className="squad-modal__results">
          {filteredResults.map(result => (
            <div key={result.id} className="squad-modal__result">
              <img src={userAvatar} alt="" className="squad-modal__result-avatar" />
              <span className="squad-modal__result-name">{result.name}</span>
              <button type="button" className="squad-modal__invite-btn btn-press" onClick={() => handleInvite(result.id)}>
                Пригласить
              </button>
            </div>
          ))}
          {filteredResults.length === 0 && (
            <div className="squad-modal__empty">Ничего не найдено</div>
          )}
        </div>
      </Modal>

      <div className="toast-container toast-container--fixed-right">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast--${toast.type}`}>
            {toast.type === 'success' ? '✓ ' : '✕ '}
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  )
}