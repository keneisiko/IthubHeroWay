import { Fragment, useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useCountUp } from '../useCountUp'
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
import LoadError from '../components/LoadError'
import { useToasts } from '../useToasts'
import { RARITY_LABELS, unwrapList } from '../lib/apiData'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

const AXIS_KEYS = ['Мощность', 'Связь', 'Фокус', 'Ритм', 'Отдача'] as const

const radarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      beginAtZero: true,
      max: 20,
      // в макете пятиугольник состоит ровно из 5 колец
      ticks: { display: false, stepSize: 4 },
      grid: { color: 'rgba(154, 51, 244, 0.55)', lineWidth: 3, circular: false },
      angleLines: { color: 'rgba(154, 51, 244, 0.55)', lineWidth: 3 },
      pointLabels: { display: false },
    },
  },
  layout: { padding: 0 },
  elements: { line: { tension: 0.12 } },
  animation: { duration: 900, easing: 'easeOutQuart' as const },
  plugins: { legend: { display: false }, tooltip: { enabled: false } },
} as const

const AXES = [
  { key: 'Мощность', position: 'profile-radar__axis--top' },
  { key: 'Связь', position: 'profile-radar__axis--left' },
  { key: 'Фокус', position: 'profile-radar__axis--right' },
  { key: 'Ритм', position: 'profile-radar__axis--bottom-left' },
  { key: 'Отдача', position: 'profile-radar__axis--bottom-right' },
] as const

const VALUE_POSITIONS = [
  { outer: 'profile-radar__value--outer-top', inner: 'profile-radar__value--inner-top' },
  { outer: 'profile-radar__value--outer-left', inner: 'profile-radar__value--inner-left' },
  { outer: 'profile-radar__value--outer-right', inner: 'profile-radar__value--inner-right' },
  { outer: 'profile-radar__value--outer-bottom-left', inner: 'profile-radar__value--inner-bottom-left' },
  { outer: 'profile-radar__value--outer-bottom-right', inner: 'profile-radar__value--inner-bottom-right' },
]

const BADGE_TAB_CATEGORIES: Record<string, string | null> = {
  'Путь': null,
  'Ритм': 'progress',
  'Мастерство': 'academic',
  'Сообщество': 'social',
  'Вклад': 'progress',
  'Статус': 'special',
  'Особые': 'special',
}

interface ProfileData {
  username: string
  callsign: string
  avatar?: string | null
  track: string
  squad: string
  level: number
  rating_current: number | null
  coins_balance?: number
  rating_zone?: string
  duel_wins?: number
  // коды пройденных вех карты пути; бэкенд пока не отдаёт это поле
  path_reached?: string[]
}

// Вехи карты пути — постоянные точки программы (из макета).
// Верхний ряд идёт слева направо, нижний — продолжение того же пути.
const PATH_TOP = [
  { code: 'entry', label: 'Вход' },
  { code: 'first_win', label: 'Первая\nпобеда' },
  { code: 'first_fail', label: 'Первый\nпровал' },
  { code: 'first_mission', label: 'Первая\nмиссия' },
] as const

const PATH_BOTTOM = [
  { code: 'product', label: 'Продукт' },
  { code: 'internship', label: 'Стажировка' },
  { code: 'graduation', label: 'Выпуск' },
] as const

interface UserBadge {
  id: number
  is_pinned?: boolean
  badge: {
    code: string
    title: string
    rarity: string
    category: string
  }
  acquired_at: string
}

interface CharacteristicItem {
  pillar: string
  label: string
  current: number
  peak: number
  history: number[]
}

function useModal(initial = false) {
  const [open, setOpen] = useState(initial)
  const ref = useRef<HTMLDivElement>(null)
  const show = () => setOpen(true)
  const hide = () => setOpen(false)

  useEffect(() => {
    if (!open) return
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') hide() }
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) hide()
    }
    document.addEventListener('keydown', handleEsc)
    document.addEventListener('mousedown', handleClick)
    return () => {
      document.removeEventListener('keydown', handleEsc)
      document.removeEventListener('mousedown', handleClick)
    }
  }, [open])

  return { open, ref, show, hide }
}

export default function Profile() {
  const { username: routeUsername } = useParams<{ username?: string }>()
  const isOwnProfile = !routeUsername
  const tabs = useMemo(() => ['Путь', 'Ритм', 'Мастерство', 'Сообщество', 'Вклад', 'Статус', 'Особые'], [])
  const [activeTab, setActiveTab] = useState('Путь')
  const [activeAxis, setActiveAxis] = useState<string | null>(null)
  const [hoveredAxis, setHoveredAxis] = useState<string | null>(null)
  const tabsRef = useRef<HTMLDivElement | null>(null)
  const tabButtonRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 65 })
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [characteristics, setCharacteristics] = useState<CharacteristicItem[]>([])
  const [badges, setBadges] = useState<UserBadge[]>([])
  const [allBadges, setAllBadges] = useState<UserBadge['badge'][]>([])
  const [questsCompleted, setQuestsCompleted] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [notFound, setNotFound] = useState(false)
  const [myRating, setMyRating] = useState<number | null>(null)
  const [socialBusy, setSocialBusy] = useState(false)
  const [editForm, setEditForm] = useState({ callsign: '' })
  const editModal = useModal()
  const avatarModal = useModal()
  const mentorModal = useModal()
  const [menteeUsername, setMenteeUsername] = useState('')
  const [avatarFile, setAvatarFile] = useState<File | null>(null)
  const [avatarUploading, setAvatarUploading] = useState(false)
  const { toasts, addToast } = useToasts()

  const loadProfile = useCallback(() => {
    setLoading(true)
    setLoadError(false)
    setNotFound(false)
    const profileUrl = isOwnProfile
      ? '/api/v1/profile/me/'
      : `/api/v1/profile/${encodeURIComponent(routeUsername!)}/`

    const requests: Promise<unknown>[] = [
      api.get(profileUrl).then((res) => {
        const data = res.data as ProfileData
        setProfile(data)
        setEditForm({ callsign: data.callsign || '' })
        if (!isOwnProfile) {
          setBadges([])
          setAllBadges([])
          setQuestsCompleted(0)
          setCharacteristics([])
          return
        }
        return Promise.all([
          api.get('/api/v1/badges/my/'),
          api.get('/api/v1/quests/my-progress/', { params: { completed: true } }),
          api.get('/api/v1/profile/me/characteristics/'),
          api.get('/api/v1/badges/'),
        ]).then(([badgesRes, questsRes, charsRes, allBadgesRes]) => {
          const badgeRows = unwrapList<UserBadge>(badgesRes.data)
          badgeRows.sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned))
          setBadges(badgeRows)
          setQuestsCompleted(unwrapList(questsRes.data).length)
          setCharacteristics(unwrapList<CharacteristicItem>(charsRes.data))
          setAllBadges(unwrapList<UserBadge['badge']>(allBadgesRes.data))
        })
      }),
    ]

    if (!isOwnProfile) {
      requests.push(
        api.get('/api/v1/rating/me/').then((res) => {
          setMyRating(res.data?.rating_current ?? null)
        }),
      )
    } else {
      setMyRating(null)
    }

    return Promise.all(requests)
      .catch((err) => {
        setProfile(null)
        if (err?.response?.status === 404) {
          setNotFound(true)
        } else {
          setLoadError(true)
        }
      })
      .finally(() => setLoading(false))
  }, [isOwnProfile, routeUsername])

  useEffect(() => {
    loadProfile()
  }, [loadProfile])

  const getSkill = useCallback((key: string) => {
    const item = characteristics.find(c => c.label === key)
    return {
      current: item?.current ?? 0,
      peak: item?.peak ?? 0,
      history: item?.history ?? [0, 0, 0, 0, 0, 0],
    }
  }, [characteristics])

  const radarData = {
    labels: [...AXIS_KEYS],
    datasets: [
      {
        label: 'Текущий',
        data: AXIS_KEYS.map(k => getSkill(k).current),
        backgroundColor: 'rgba(154, 51, 244, 0.18)',
        borderColor: '#9A33F4',
        borderWidth: 5,
        pointBackgroundColor: '#f5f5f5',
        pointBorderColor: '#9A33F4',
        pointBorderWidth: 5,
        pointRadius: 9,
        pointHoverRadius: 12,
      },
      {
        label: 'Пик',
        data: AXIS_KEYS.map(k => getSkill(k).peak),
        backgroundColor: 'rgba(154, 51, 244, 0.08)',
        borderColor: 'rgba(154, 51, 244, 0.65)',
        borderWidth: 3,
        borderDash: [8, 7],
        pointRadius: 0,
        pointHoverRadius: 0,
      },
    ],
  }

  // Карта пути: пройденные вехи приходят с бэка; пока поля нет — пройден только вход.
  const pathPoints = [...PATH_TOP, ...PATH_BOTTOM]
  const reachedCodes = profile?.path_reached ?? ['entry']
  const lastReachedIndex = pathPoints.reduce(
    (last, point, i) => (reachedCodes.includes(point.code) ? i : last),
    -1,
  )
  const pathReached = (i: number) => i <= lastReachedIndex
  const pathNodeState = (i: number) =>
    i === lastReachedIndex ? 'current' : i < lastReachedIndex ? 'done' : 'idle'

  const selectedAxis = activeAxis ?? 'Мощность'
  const activeHistory = getSkill(selectedAxis).history

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

  const initials = profile?.callsign?.slice(0, 2).toUpperCase() ?? '??'

  // Анимация чисел в статистике
  const animQuests = useCountUp(questsCompleted, 1100, 200)
  const animBadges = useCountUp(badges.length, 1100, 350)

  const historyPoints = useMemo(() => {
    const max = 20
    return activeHistory.map((v, i) => ({
      x: (i / (activeHistory.length - 1)) * 100,
      y: 100 - (v / max) * 100,
      value: v
    }))
  }, [activeHistory])

  const polylinePoints = historyPoints.map(p => `${p.x},${p.y}`).join(' ')

  const handleSaveProfile = () => {
    api.patch('/api/v1/profile/me/', { callsign: editForm.callsign.trim() })
      .then((res) => {
        setProfile((prev) => prev ? { ...prev, callsign: res.data.callsign } : null)
        editModal.hide()
        addToast('Профиль сохранён!', 'success')
      })
      .catch(() => addToast('Ошибка сохранения', 'error'))
  }

  const handleAvatarUpload = () => {
    if (!avatarFile) return
    const formData = new FormData()
    formData.append('avatar', avatarFile)
    setAvatarUploading(true)
    api.patch('/api/v1/profile/me/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
      .then(res => {
        setProfile(prev => prev ? { ...prev, avatar: res.data.avatar } : null)
        avatarModal.hide()
        setAvatarFile(null)
        addToast('Аватар обновлён!', 'success')
      })
      .catch(() => addToast('Ошибка загрузки аватара', 'error'))
      .finally(() => setAvatarUploading(false))
  }

  const rarityClass = (rarity: string) => {
    if (rarity === 'legendary') return 'ach__rarity--epic'
    if (rarity === 'epic') return 'ach__rarity--epic'
    if (rarity === 'rare') return 'ach__rarity--rare'
    return 'ach__rarity--common'
  }

  const showCharacteristics = isOwnProfile
  const pinnedBadges = useMemo(
    () => badges.filter((b) => b.is_pinned).slice(0, 3),
    [badges],
  )
  const filteredBadges = useMemo(() => {
    const category = BADGE_TAB_CATEGORIES[activeTab]
    if (!category) return badges
    return badges.filter((b) => b.badge.category === category)
  }, [badges, activeTab])

  // Нераскрытые нашивки: в макете они показаны серыми слотами «Условие не выполнено»
  const lockedBadges = useMemo(() => {
    const earned = new Set(badges.map((b) => b.badge.code))
    const category = BADGE_TAB_CATEGORIES[activeTab]
    return allBadges.filter(
      (b) => !earned.has(b.code) && (!category || b.category === category),
    )
  }, [allBadges, badges, activeTab])

  const handlePinBadge = (code: string) => {
    api.post(`/api/v1/badges/${encodeURIComponent(code)}/pin/`)
      .then(() => {
        addToast('Нашивка закреплена!', 'success')
        loadProfile()
      })
      .catch(() => addToast('Не удалось закрепить нашивку', 'error'))
  }

  const handleRespect = () => {
    if (!profile?.username) return
    setSocialBusy(true)
    api.post('/api/v1/social/respects/', { to_username: profile.username })
      .then(() => addToast('Респект отправлен!', 'success'))
      .catch((err) => {
        const detail = err.response?.data?.detail
        addToast(typeof detail === 'string' ? detail : 'Не удалось отправить респект', 'error')
      })
      .finally(() => setSocialBusy(false))
  }

  const handleDuel = () => {
    if (!profile?.username) return
    setSocialBusy(true)
    api.post('/api/v1/social/duels/', { opponent_username: profile.username })
      .then(() => addToast('Вызов на дуэль отправлен!', 'success'))
      .catch((err) => {
        const detail = err.response?.data?.detail
        addToast(typeof detail === 'string' ? detail : 'Не удалось вызвать на дуэль', 'error')
      })
      .finally(() => setSocialBusy(false))
  }

  const canDuel = !isOwnProfile
    && profile?.rating_current != null
    && myRating != null
    && Math.abs(myRating - (profile.rating_current ?? 0)) <= 150

  if (loading) {
    return (
      <div className="profile page-enter">
        <div className="profile-loading">
          <div className="loading-spinner">
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
          </div>
          <p className="loading-text">Загрузка профиля...</p>
        </div>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="profile page-enter">
        <div className="profile-loading">
          <p className="loading-text">Профиль не найден</p>
        </div>
      </div>
    )
  }

  if (loadError || !profile) {
    return (
      <div className="profile page-enter">
        <LoadError onRetry={loadProfile} />
      </div>
    )
  }

  return (
    <div className="profile page-enter">
      <div className="profile__top">
        <div className="profile__left">
          <section className="profile-card profile-card--primary card-entrance">
            <div className="profile-card__header">
              <div 
                className="profile-card__avatar" 
                role="img" 
                aria-label="Аватар"
                onClick={isOwnProfile ? avatarModal.show : undefined}
                style={{ cursor: isOwnProfile ? 'pointer' : 'default' }}
                title={isOwnProfile ? 'Сменить аватар' : undefined}
              >
                {profile.avatar ? (
                  <img
                    src={profile.avatar}
                    alt=""
                    style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 'inherit' }}
                  />
                ) : (
                  initials
                )}
              </div>
              <div className="profile-card__names">
                <div className="profile-card__nickname">{profile?.callsign ?? '—'}</div>
                <div className="profile-card__fio">@{profile?.username ?? '—'}</div>
              </div>
            </div>
            <div className="profile-card__rows">
              <div className="profile-row">
                <span className="profile-row__label">Трек:</span>
                <span className="profile-row__chip profile-row__chip--dark">{profile?.track || '—'}</span>
              </div>
              <div className="profile-row">
                <span className="profile-row__label">Отряд:</span>
                <span className="profile-row__chip profile-row__chip--light">{profile?.squad || '—'}</span>
              </div>
              <div className="profile-row">
                <span className="profile-row__label">Статус и уровень:</span>
                <span className="profile-row__chip profile-row__chip--dark">
                  {profile?.rating_zone ? `${profile.rating_zone} ` : ''}ур. {profile?.level ?? 1}
                </span>
              </div>

            </div>
          </section>

          <section className="profile-card profile-card--map card-entrance" style={{ animationDelay: '0.1s' }}>
            <h3 className="profile-map__title">Карта пути:</h3>
            <div className="profile-map__body">
              <div className="profile-map__row">
                {PATH_TOP.map((point, i) => (
                  <Fragment key={point.code}>
                    {i > 0 && (
                      <span className={`profile-map__line profile-map__line--${pathReached(i) ? 'done' : 'idle'}`} />
                    )}
                    <span className={`profile-map__node profile-map__node--${pathNodeState(i)}`} />
                  </Fragment>
                ))}
              </div>
              <div className="profile-map__labels profile-map__labels--top">
                {PATH_TOP.map((point) => <span key={point.code}>{point.label}</span>)}
              </div>
              <div className="profile-map__row profile-map__row--bottom">
                <span
                  className={`profile-map__line profile-map__line--first profile-map__line--${pathReached(PATH_TOP.length) ? 'done' : 'idle'}`}
                />
                {PATH_BOTTOM.map((point, i) => (
                  <Fragment key={point.code}>
                    {i > 0 && (
                      <span
                        className={`profile-map__line profile-map__line--${pathReached(PATH_TOP.length + i) ? 'done' : 'idle'}`}
                      />
                    )}
                    <span className={`profile-map__node profile-map__node--${pathNodeState(PATH_TOP.length + i)}`} />
                  </Fragment>
                ))}
              </div>
              <div className="profile-map__labels profile-map__labels--bottom">
                {PATH_BOTTOM.map((point) => <span key={point.code}>{point.label}</span>)}
              </div>
            </div>
          </section>
        </div>

        {isOwnProfile && (
        <section className="profile-card profile-card--aside card-entrance" style={{ animationDelay: '0.2s' }}>
          <button className="profile-aside__btn btn-press" onClick={editModal.show}>Настроить профиль</button>
          <div className="profile-aside__divider" />
          <h3 className="profile-aside__title">Статистика:</h3>
          <div className="profile-aside__stats">
            <span className="profile-aside__pill">Выполнено квестов: <strong>{animQuests}</strong></span>
            <span className="profile-aside__pill">
              Получено нашивок: <strong>{animBadges}</strong>{allBadges.length ? <> из <strong>{allBadges.length}</strong></> : null}
            </span>
            {profile?.duel_wins != null && (
              <span className="profile-aside__pill">Побед в дуэлях: <strong>{profile.duel_wins}</strong></span>
            )}
          </div>
          <h3 className="profile-aside__title profile-aside__title--sp">Шефство:</h3>
          <div className="profile-aside__mentor-row">
            <button className="profile-aside__mentor-btn btn-press" onClick={mentorModal.show}>Стать наставником</button>
          </div>
        </section>
        )}

        {!isOwnProfile && (
        <section className="profile-card profile-card--aside card-entrance" style={{ animationDelay: '0.2s' }}>
          <h3 className="profile-aside__title">Социальные действия:</h3>
          <button
            className="profile-aside__btn btn-press"
            type="button"
            onClick={handleRespect}
            disabled={socialBusy}
          >
            Отправить респект
          </button>
          <button
            className="profile-aside__mentor-btn btn-press"
            type="button"
            onClick={handleDuel}
            disabled={socialBusy || !canDuel}
            title={canDuel ? undefined : 'Дуэль доступна при разнице рейтинга ≤ 150'}
          >
            Вызвать на дуэль
          </button>
        </section>
        )}
      </div>

      <section className="profile-radar card-entrance" style={{ animationDelay: '0.3s' }}>
        <div className="profile-radar__chart">
          <Radar data={radarData} options={radarOptions} />
        </div>

        {AXES.map(({ key, position }) => {
          const skill = getSkill(key)
          const isActive = activeAxis === key
          const isHovered = hoveredAxis === key
          return (
            <div
              key={key}
              className={`profile-radar__axis ${position}${isActive ? ' profile-radar__axis--active' : ''}`}
              onMouseEnter={() => setHoveredAxis(key)}
              onMouseLeave={() => setHoveredAxis(null)}
              onClick={() => setActiveAxis(cur => cur === key ? null : key)}
            >
              <span className="profile-radar__axis-icon" aria-hidden="true" />
              <span>{key}</span>
              {(isHovered || isActive) && showCharacteristics && (
                <span className="profile-radar__tooltip">
                  {key}: {skill.current} / 20 (пик: {skill.peak})
                </span>
              )}
            </div>
          )
        })}

        {showCharacteristics && VALUE_POSITIONS.map((pos, i) => {
          const skill = getSkill(AXES[i].key)
          return <span key={`outer-${i}`} className={`profile-radar__value ${pos.outer}`}>{skill.current}</span>
        })}

        {showCharacteristics && VALUE_POSITIONS.map((pos, i) => {
          const skill = getSkill(AXES[i].key)
          return <span key={`inner-${i}`} className={`profile-radar__value ${pos.inner} profile-radar__value--inner`}>{skill.peak}</span>
        })}

        {showCharacteristics && (
        <section className={`profile-history${activeAxis ? ' profile-history--visible' : ''}`} aria-hidden={!activeAxis}>
          <span className="profile-history__title">История: {selectedAxis}</span>
          <div className="profile-history__chart">
            <div className="profile-history__grid" aria-hidden="true">
              {Array.from({ length: 5 }).map((_, i) => <span key={i} className="profile-history__grid-line" />)}
            </div>
            <div className="profile-history__y"><span>20</span><span>15</span><span>10</span><span>5</span><span>0</span></div>
            <div className="profile-history__plot">
              {historyPoints.map((p, i) => (
                <span
                  key={i}
                  className="profile-history__dot"
                  style={{ left: `${p.x}%`, bottom: `${100 - p.y}%` }}
                  title={`Неделя ${i + 1}: ${p.value}`}
                />
              ))}
              <svg className="profile-history__line" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                <polyline points={polylinePoints} />
              </svg>
            </div>
            <div className="profile-history__x">
              {activeHistory.map((_, i) => <span key={i}>{i + 1}</span>)}
            </div>
            <span className="profile-history__x-label">Недели</span>
          </div>
        </section>
        )}
      </section>

      {isOwnProfile && (
      <section className="profile-path profile-card card-entrance" style={{ animationDelay: '0.4s' }}>
        <h3 className="profile-achievements__title">Достижения:</h3>
        <div className="profile-achievements__row">
          {pinnedBadges.length === 0 ? (
            <p className="loading-text">Пока нет закреплённых нашивок</p>
          ) : pinnedBadges.map((item) => (
            <button key={item.id} className="ach btn-press" type="button">
              <span className="ach__icon" aria-hidden="true"><span className="ach__glyph" /></span>
              <span className="ach__name">{item.badge.title}</span>
              <span className={`ach__rarity ${rarityClass(item.badge.rarity)}`}>
                {RARITY_LABELS[item.badge.rarity] ?? item.badge.rarity}
              </span>
            </button>
          ))}
        </div>

        <div className="profile-path__tabs" ref={tabsRef}>
          {tabs.map((t) => (
            <button
              key={t}
              type="button"
              ref={(el) => { tabButtonRefs.current[t] = el }}
              className={`profile-path__tab${t === activeTab ? ' profile-path__tab--active' : ''} btn-press`}
              onClick={() => setActiveTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="profile-path__underline" aria-hidden="true">
          <div className="profile-path__indicator" style={{ width: indicatorStyle.width, left: indicatorStyle.left }} />
        </div>

        <div className="profile-path__grid">
          {filteredBadges.map((card) => (
            <button key={card.id} className="path-card btn-press" type="button">
              <span className={`path-card__icon path-card__icon--${card.badge.rarity}`} aria-hidden="true">
                <span className="path-card__glyph" />
              </span>
              <span className="path-card__name">{card.badge.title}</span>
              <span className={`path-card__chip path-card__chip--${card.badge.rarity}`}>
                {RARITY_LABELS[card.badge.rarity] ?? card.badge.rarity}
              </span>
              {!card.is_pinned && (
                <span
                  className="path-card__chip path-card__chip--common"
                  style={{ marginTop: 4, cursor: 'pointer' }}
                  onClick={(e) => {
                    e.stopPropagation()
                    handlePinBadge(card.badge.code)
                  }}
                >
                  Закрепить
                </span>
              )}
            </button>
          ))}
          {lockedBadges.map((badge) => (
            <span key={badge.code} className="path-card path-card--locked" title={badge.title}>
              <span className="path-card__icon path-card__icon--locked" aria-hidden="true">
                <span className="path-card__glyph path-card__glyph--locked" />
              </span>
              <span className="path-card__locked">Условие не выполнено</span>
            </span>
          ))}
          {filteredBadges.length === 0 && lockedBadges.length === 0 && (
            <p className="loading-text" style={{ gridColumn: '1 / -1' }}>Нет нашивок</p>
          )}
        </div>
      </section>
      )}

      {/* Модалка настройки профиля */}
      {editModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={editModal.ref}>
            <h3 className="popup__title">Настроить профиль</h3>
            <label className="popup__label">Позывной</label>
            <input
              type="text"
              value={editForm.callsign}
              onChange={(e) => setEditForm(prev => ({ ...prev, callsign: e.target.value }))}
              className="popup__input"
            />
            <div className="shop-modal__buttons">
              <button type="button" className="shop-modal__btn shop-modal__btn--secondary btn-press" onClick={editModal.hide}>
                Отмена
              </button>
              <button type="button" className="shop-modal__btn shop-modal__btn--primary btn-press" onClick={handleSaveProfile}>
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка стать наставником */}
      {mentorModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={mentorModal.ref}>
            <h3 className="popup__title">Стать наставником</h3>
            <label className="popup__label">Username подшефного</label>
            <input
              type="text"
              value={menteeUsername}
              onChange={(e) => setMenteeUsername(e.target.value)}
              placeholder="username агента"
              className="popup__input"
            />
            <div className="shop-modal__buttons">
              <button type="button" className="shop-modal__btn shop-modal__btn--secondary btn-press" onClick={mentorModal.hide}>
                Отмена
              </button>
              <button type="button" className="shop-modal__btn shop-modal__btn--primary btn-press" onClick={() => {
                const username = menteeUsername.trim()
                if (!username) {
                  addToast('Укажите username подшефного', 'error')
                  return
                }
                api.post('/api/v1/social/mentorships/', { mentee_username: username })
                  .then(() => { addToast('Наставничество оформлено!', 'success'); mentorModal.hide(); setMenteeUsername('') })
                  .catch(() => { addToast('Не удалось оформить наставничество', 'error') })
              }}>
                Подтвердить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка смены аватара */}
      {avatarModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={avatarModal.ref}>
            <h3 className="popup__title">Сменить аватар</h3>
            <p className="popup__label">Загрузите изображение профиля</p>
            <div className="avatar-upload-zone" onClick={() => document.getElementById('avatar-file-input')?.click()}>
              <span className="avatar-upload-text">
                {avatarFile ? avatarFile.name : 'Перетащите фото сюда или нажмите для выбора'}
              </span>
              <input
                id="avatar-file-input"
                type="file"
                accept="image/*"
                className="avatar-upload-input"
                onChange={(e) => setAvatarFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <div className="shop-modal__buttons">
              <button type="button" className="shop-modal__btn shop-modal__btn--secondary btn-press" onClick={() => { avatarModal.hide(); setAvatarFile(null) }}>
                Отмена
              </button>
              <button
                type="button"
                className="shop-modal__btn shop-modal__btn--primary btn-press"
                onClick={handleAvatarUpload}
                disabled={!avatarFile || avatarUploading}
              >
                {avatarUploading ? 'Загрузка...' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Тосты */}
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