import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import userAvatar from '../assets/branding/user-avatar.png'
import api from '../api'
import { useToasts } from '../useToasts'
import { unwrapList } from '../lib/apiData'

type SortKey = 'name' | 'track' | 'status'

interface Member {
  id: number
  username: string
  name: string
  track: string
  status: string
  avatar?: string | null
  rating?: number | null
}

interface SquadData {
  code: string
  name: string
  course: number
  rating: number
  members_count: number
  delta: string
  rank: string
  bonus_progress: number
  bonus_completed: number
  bonus_total: number
  // Порог и награда приходят с бэка: раньше они были записаны текстом
  // в разметке и расходились бы с расчётом при любой правке регламента.
  bonus_threshold: number
  bonus_coins: number
  coins_month: number
  share_url: string
}

interface AvailableSquad {
  code: string
  name: string
  course: number | null
  capacity: number | null
  agents_count: number
  avg_rating: number
  can_join: boolean
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

function memberAvatarUrl(avatar?: string | null): string {
  if (!avatar) return userAvatar
  if (avatar.startsWith('http')) return avatar
  return avatar.startsWith('/') ? avatar : `/${avatar}`
}

export default function Squads() {
  const navigate = useNavigate()
  const [memberQuery, setMemberQuery] = useState('')
  const [showSort, setShowSort] = useState(false)
  const { toasts, addToast } = useToasts()
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [members, setMembers] = useState<Member[]>([])
  const [squad, setSquad] = useState<SquadData | null>(null)
  const [availableSquads, setAvailableSquads] = useState<AvailableSquad[]>([])
  const [loading, setLoading] = useState(true)
  const [noSquad, setNoSquad] = useState(false)
  const [joinCode, setJoinCode] = useState('')
  const [createName, setCreateName] = useState('')
  const [createCourse, setCreateCourse] = useState('2')
  const [submitting, setSubmitting] = useState(false)
  const [debouncedMemberQuery, setDebouncedMemberQuery] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedMemberQuery(memberQuery.trim()), 300)
    return () => clearTimeout(timer)
  }, [memberQuery])

  const mapMembers = (rows: {
    username: string
    callsign: string
    track?: string
    status?: string
    avatar?: string | null
    rating_current?: number | null
  }[]) => rows.map((m, index) => ({
    id: index + 1,
    username: m.username,
    name: m.callsign || m.username,
    track: m.track || '—',
    status: m.status || '—',
    avatar: m.avatar,
    rating: m.rating_current ?? null,
  }))

  const loadMembers = useCallback((code: string, search: string, ordering: SortKey) => {
    const params: Record<string, string> = {
      ordering: ordering === 'name' ? 'alpha' : 'rating',
    }
    if (search) params.search = search
    return api.get(`/api/v1/squads/${code}/members/`, { params })
      .then((membersRes) => {
        const rows = unwrapList<{
          username: string
          callsign: string
          track?: string
          status?: string
          avatar?: string | null
          rating_current?: number | null
        }>(membersRes.data)
        setMembers(mapMembers(rows))
      })
  }, [])

  const loadSquad = useCallback(() => {
    setLoading(true)
    setNoSquad(false)
    api.get('/api/v1/squads/me/')
      .then(async (res) => {
        const my = res.data?.my_squad
        const bonus = res.data?.team_bonus ?? {}
        const actions = res.data?.actions ?? {}
        if (!my) {
          setNoSquad(true)
          setSquad(null)
          setMembers([])
          const listRes = await api.get('/api/v1/squads/')
          setAvailableSquads(unwrapList<AvailableSquad>(listRes.data))
          return null
        }
        setNoSquad(false)
        setSquad({
          code: my.code,
          name: my.name,
          course: my.course,
          rating: my.squad_rating_avg ?? 0,
          members_count: my.agents_count ?? 0,
          delta: my.delta_week >= 0 ? `+${my.delta_week}` : String(my.delta_week),
          rank: `${my.place} место из ${my.total_squads}`,
          bonus_progress: bonus.percent ?? 0,
          bonus_completed: bonus.completed ?? 0,
          bonus_total: bonus.total ?? 0,
          bonus_threshold: bonus.bonus_threshold_percent ?? 80,
          bonus_coins: bonus.bonus_reward_coins ?? 5,
          coins_month: actions.month_coins ?? 0,
          share_url: actions.share_url ?? `/squads/${my.code}`,
        })
        return my.code as string
      })
      .catch(() => {
        addToast('Не удалось загрузить отряд', 'error')
      })
      .finally(() => setLoading(false))
  }, [addToast])

  useEffect(() => {
    loadSquad()
  }, [loadSquad])

  useEffect(() => {
    if (!squad?.code || loading) return
    loadMembers(squad.code, debouncedMemberQuery, sortKey).catch(() => {
      addToast('Не удалось обновить список участников', 'error')
    })
  }, [squad?.code, debouncedMemberQuery, sortKey, loading, loadMembers, addToast])

  const handleJoin = useCallback((code: string) => {
    const trimmed = code.trim()
    if (!trimmed) {
      addToast('Введите код отряда', 'error')
      return
    }
    setSubmitting(true)
    api.post('/api/v1/squads/join/', { code: trimmed })
      .then(() => {
        addToast('Вы вступили в отряд!', 'success')
        setJoinCode('')
        loadSquad()
      })
      .catch((err) => {
        const msg = err.response?.data?.detail || 'Не удалось вступить в отряд'
        addToast(typeof msg === 'string' ? msg : 'Не удалось вступить в отряд', 'error')
      })
      .finally(() => setSubmitting(false))
  }, [addToast, loadSquad])

  const handleCreate = useCallback(() => {
    const name = createName.trim()
    if (!name) {
      addToast('Введите название отряда', 'error')
      return
    }
    setSubmitting(true)
    api.post('/api/v1/squads/', {
      name,
      course: Number(createCourse) || undefined,
      capacity: 20,
    })
      .then(() => {
        addToast('Отряд создан!', 'success')
        setCreateName('')
        loadSquad()
      })
      .catch((err) => {
        const msg = err.response?.data?.detail || 'Не удалось создать отряд'
        addToast(typeof msg === 'string' ? msg : 'Не удалось создать отряд', 'error')
      })
      .finally(() => setSubmitting(false))
  }, [addToast, createCourse, createName, loadSquad])

  const visibleMembers = members

  const handleShare = useCallback(() => {
    const shareUrl = `${window.location.origin}${squad?.share_url ?? '/squads'}`
    const shareData = {
      title: `Отряд ${squad?.name ?? ''}`,
      text: squad?.name ? `Отряд «${squad.name}» в IThub Путь Героя` : 'IThub Путь Героя',
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

  if (loading) {
    return (
      <div className="dashboard squad-page page-enter">
        <div className="profile-loading" style={{ minHeight: '40vh' }}>
          <div className="loading-spinner">
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
          </div>
          <p className="loading-text">Загрузка отряда...</p>
        </div>
      </div>
    )
  }

  if (noSquad || !squad) {
    return (
      <div className="dashboard squad-page page-enter">
        <section className="card card--light" style={{ maxWidth: 720, margin: '0 auto 24px', padding: 24 }}>
          <h2 className="squad-my__title" style={{ marginBottom: 8 }}>Вы пока не состоите в отряде</h2>
          <p className="loading-text" style={{ marginBottom: 20 }}>Вступите по коду или создайте свой отряд</p>

          <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
            <input
              type="text"
              value={joinCode}
              onChange={e => setJoinCode(e.target.value)}
              placeholder="Код отряда (например alpha-2025)"
              className="squad-members__search-input"
              style={{ flex: 1, minWidth: 200 }}
            />
            <button
              type="button"
              className="squad-actions__btn squad-actions__btn--share btn-press"
              disabled={submitting}
              onClick={() => handleJoin(joinCode)}
            >
              Вступить
            </button>
          </div>

          <h3 className="squad-members__title" style={{ marginBottom: 12 }}>Создать отряд</h3>
          <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
            <input
              type="text"
              value={createName}
              onChange={e => setCreateName(e.target.value)}
              placeholder="Название отряда"
              className="squad-members__search-input"
              style={{ flex: 1, minWidth: 160 }}
            />
            <input
              type="number"
              min={1}
              max={6}
              value={createCourse}
              onChange={e => setCreateCourse(e.target.value)}
              placeholder="Курс"
              className="squad-members__search-input"
              style={{ width: 100 }}
            />
            <button
              type="button"
              className="squad-actions__btn btn-press"
              disabled={submitting}
              onClick={handleCreate}
            >
              Создать
            </button>
          </div>

          {availableSquads.length > 0 && (
            <>
              <h3 className="squad-members__title" style={{ marginBottom: 12 }}>Доступные отряды</h3>
              <ul className="squad-members__list" style={{ listStyle: 'none', padding: 0 }}>
                {availableSquads.map(s => (
                  <li key={s.code} className="squad-member-row hover-lift" style={{ marginBottom: 8 }}>
                    <div className="squad-member-row__main">
                      <div className="squad-member-row__tags">
                        <span className="squad-member-tag squad-member-tag--dark">{s.name}</span>
                        <span className="squad-member-tag squad-member-tag--purple">
                          {s.agents_count}{s.capacity ? ` / ${s.capacity}` : ''} агентов
                        </span>
                        {s.course != null && (
                          <span className="squad-member-tag squad-member-tag--purple">Курс {s.course}</span>
                        )}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="squad-member-row__rating btn-press"
                      disabled={!s.can_join || submitting}
                      onClick={() => handleJoin(s.code)}
                    >
                      {s.can_join ? 'Вступить' : 'Нет мест'}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

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

  return (
    <div className="dashboard squad-page page-enter">
      <div className="squad-page__top">
        <section className="squad-my" aria-labelledby="squad-my-title">
          <h2 id="squad-my-title" className="squad-my__title">{squad.name}</h2>
          <div className="squad-my__course"><span>Курс: {squad.course}</span></div>
          <dl className="squad-my__stats">
            <div className="squad-my__row">
              <dt className="squad-my__label">Рейтинг:</dt>
              <dd><span className="squad-pill squad-pill--dark squad-pill--firs">{squad.rating}</span></dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Агентов:</dt>
              <dd><span className="squad-pill squad-pill--light">{squad.members_count}</span></dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Дельта роста за неделю:</dt>
              <dd>
                <span className="squad-pill squad-pill--dark squad-pill--delta">
                  {squad.delta}
                  <svg className="squad-pill__arrow" width="14" height="7" viewBox="0 0 14 7" fill="none" aria-hidden="true">
                    <path d="M2 6L7 1L12 6" stroke="#6CD63E" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              </dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Место в общем рейтинге отрядов:</dt>
              <dd><span className="squad-pill squad-pill--dark squad-pill--wide">{squad.rank}</span></dd>
            </div>
          </dl>
        </section>

        <div className="squad-page__right">
          <section className="squad-bonus" aria-label="Прогресс командного бонуса">
            <p className="squad-bonus__lead">{squad.bonus_progress}% отряда выполнили еженедельный квест</p>
            <div className="squad-bonus__chip squad-bonus__chip--purple">
              При {squad.bonus_threshold}% — +{squad.bonus_coins} монет в пятницу
            </div>
            <div className="squad-bonus__chip squad-bonus__chip--dark">
              <span className="squad-bonus__chip-num">{squad.bonus_completed}</span>
              <span> из {squad.bonus_total} агентов</span>
            </div>
            <div className="squad-bonus__progress-block">
              <p className="squad-bonus__hint">
              До бонуса осталось{' '}
              {Math.max(0, Math.ceil(squad.bonus_total * squad.bonus_threshold / 100) - squad.bonus_completed)} человек
            </p>
              <div className="squad-bonus__progress">
                <span className="squad-bonus__dot squad-bonus__dot--start" aria-hidden="true" />
                <div className="squad-bonus__track">
                  <div className="squad-bonus__track-slot">
                    <div className="squad-bonus__fill" style={{ width: `${Math.min(100, squad.bonus_progress)}%` }} />
                  </div>
                </div>
                <span className="squad-bonus__dot squad-bonus__dot--end" aria-hidden="true" />
              </div>
            </div>
          </section>

          <section className="squad-actions" aria-label="Действия отряда">
            <div className="squad-actions__coins">
              <span className="squad-actions__coins-text">В этом месяце отряд получил</span>
              <span className="squad-actions__coins-badge">{squad.coins_month}</span>
              <span className="squad-actions__coins-text">монет</span>
            </div>
            <button type="button" className="squad-actions__btn squad-actions__btn--share btn-press" onClick={handleShare}>Поделиться</button>
            <button
              type="button"
              className="squad-actions__btn squad-actions__btn--invite btn-press"
              onClick={() => addToast('Приглашения пока не подключены на бэкенде', 'error')}
            >
              Пригласить
            </button>
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
                  <img className="squad-member-row__avatar" src={memberAvatarUrl(m.avatar)} alt="" width={50} height={50} />
                  <div className="squad-member-row__tags">
                    <span className="squad-member-tag squad-member-tag--dark">{m.name}</span>
                    <span className="squad-member-tag squad-member-tag--purple">{m.track}</span>
                    <span className="squad-member-tag squad-member-tag--purple">{m.status}</span>
                  </div>
                </div>
                <button
                  type="button"
                  className="squad-member-row__rating btn-press"
                  onClick={() => navigate(`/profile/${m.username}`)}
                >
                  {m.rating != null ? m.rating : 'Рейтинг'}
                </button>
              </li>
            ))}
            {visibleMembers.length === 0 && (
              <li className="squad-members__empty">Никого не найдено</li>
            )}
            {visibleMembers.length === 1 && !debouncedMemberQuery && (
              <li className="squad-members__empty">В отряде пока только вы</li>
            )}
          </ul>
        </div>
      </section>

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

