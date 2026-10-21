import { Fragment, useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Radar } from 'react-chartjs-2'
import type { Chart as ChartType } from 'chart.js'
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
import AgentPicker from '../components/AgentPicker'
import { RARITY_LABELS, apiErrorMessage, formatDayMonth, unwrapList } from '../lib/apiData'
import { plural } from '../lib/plural'
import { useTabIndicator } from '../useTabIndicator'
import BadgeEmblem from '../components/BadgeEmblem'
import BadgeSheet from '../components/BadgeSheet'
import type { Badge, EarnedBadge } from '../lib/badges'
import SkillHistory from '../components/SkillHistory'
import RadarHud from '../components/RadarHud'
import SkillSummary from '../components/SkillSummary'
import PixelText from '../components/PixelText'
import Avatar from '../components/Avatar'
import { bannerVariant, glowVariant, type ActiveBoost, type AppliedItems } from '../lib/cosmetics'
import { BoostPlaque } from '../components/BoostPlaque'
import DevFrame from '../components/DevFrame'
import RollNumber from '../components/RollNumber'
import '../styles/profile-radar.css'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

// Порядок как в макете: от верхней вершины по часовой стрелке
const AXIS_KEYS = ['Мощность', 'Фокус', 'Отдача', 'Ритм', 'Связь'] as const

const radarBaseOptions = {
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

const AXES = AXIS_KEYS.map((key) => ({ key }))

// Габариты пилюли со значением: она стоит в вершине пятиугольника,
// поэтому подпись оси нужно отодвинуть за её пределы
const VALUE_PILL = { halfWidth: 27, halfHeight: 17.5 }
const AXIS_LABEL_GAP = 12
// ширина подсказки оси — совпадает с .axis-tip в profile-radar.css
const TIP_WIDTH = 148

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
  rating_status?: string
  // Коды пройденных вех карты пути (apps/progress/services/path_map.py).
  path_reached?: string[]
  duel_wins?: number
  respects_received?: number
  applied_items?: AppliedItems
  // Только в своём профиле: одноразовый буст, который ещё не сработал.
  active_boost?: ActiveBoost | null
  avatar_frame?: string
  // Только в чужом профиле: свой профиль берёт это из отдельных запросов.
  quests_completed?: number
  badges?: UserBadge[]
  characteristics?: CharacteristicItem[]
}

// Вехи карты пути — постоянные точки программы (из макета).
// Путь — змейкой: верхний ряд слева направо, справа полукругом вниз,
// нижний ряд справа налево.
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

interface DuelRow {
  id: number
  status: string
  bet_coins: number
  resolve_after: string | null
  challenger: { username: string; callsign: string }
  opponent: { username: string; callsign: string }
  winner: { username: string; callsign: string } | null
}

interface DuelsResponse {
  results?: DuelRow[]
  bet_coins?: number
  duration_days?: number
  max_rating_diff?: number
  my_rating?: number
}

interface MentorshipRow {
  id: number
  mentor: { username: string; callsign: string }
  mentee: { username: string; callsign: string }
  ended_at: string | null
}

// Позывной, а если его нет — логин с @, как в чипах макета.
function agentName(agent: { username: string; callsign: string }): string {
  return agent.callsign || `@${agent.username}`
}

interface UserBadge {
  id: number
  is_pinned?: boolean
  badge: {
    code: string
    title: string
    rarity: string
    category: string
    description?: string
    reward_coins?: number
  }
  acquired_at: string
}

interface Point {
  x: number
  y: number
}

// Подпись оси: точка привязки у вершины и направление, куда её отодвинуть
interface AxisAnchor extends Point {
  ux: number
  uy: number
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
  // сторона подсказки оси: наружу от графика, а если там край экрана — над подписью
  const [tipSide, setTipSide] = useState<'left' | 'right' | 'above'>('right')
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [characteristics, setCharacteristics] = useState<CharacteristicItem[]>([])
  const [badges, setBadges] = useState<UserBadge[]>([])
  const [allBadges, setAllBadges] = useState<UserBadge['badge'][]>([])
  const [questsCompleted, setQuestsCompleted] = useState(0)
  const [loading, setLoading] = useState(true)
  // лента категорий прокручивается; выбранная вкладка подъезжает к центру
  const tabsScrollRef = useRef<HTMLDivElement>(null)
  // ref и положение подчёркивания — отдельными значениями: в одном объекте
  // линтер React считал рефом всё, включая обычное состояние.
  const {
    containerRef: tabsContainerRef,
    registerTab,
    indicator: tabIndicatorBox,
  } = useTabIndicator(activeTab, loading, tabsScrollRef)
  const [loadError, setLoadError] = useState(false)
  const [notFound, setNotFound] = useState(false)
  const [myRating, setMyRating] = useState<number | null>(null)
  const [socialBusy, setSocialBusy] = useState(false)
  const [editForm, setEditForm] = useState({ callsign: '' })
  const { ref: editModalRef, ...editModal } = useModal()
  const { ref: avatarModalRef, ...avatarModal } = useModal()
  const { ref: mentorModalRef, ...mentorModal } = useModal()
  const { ref: duelModalRef, ...duelModal } = useModal()
  const { ref: endModalRef, ...endModal } = useModal()
  // Чьё шефство завершаем: действие необратимое, поэтому сначала спрашиваем.
  const [endTarget, setEndTarget] = useState<MentorshipRow | null>(null)
  const [duels, setDuels] = useState<DuelRow[]>([])
  const [duelInfo, setDuelInfo] = useState<{ bet: number; days: number; maxDiff: number; myRating: number }>(
    { bet: 0, days: 0, maxDiff: 0, myRating: 0 },
  )
  const [mentees, setMentees] = useState<MentorshipRow[]>([])
  // Кого вызываем на дуэль — выбирается в том же поиске, что и подшефный.
  const [duelUsername, setDuelUsername] = useState('')
  const [mentors, setMentors] = useState<MentorshipRow[]>([])
  const [menteeUsername, setMenteeUsername] = useState('')
  const [avatarFile, setAvatarFile] = useState<File | null>(null)
  const [avatarUploading, setAvatarUploading] = useState(false)
  const { toasts, addToast } = useToasts()

  const applyDuels = useCallback((data: DuelsResponse | undefined) => {
    setDuels(data?.results ?? [])
    setDuelInfo({
      bet: data?.bet_coins ?? 0,
      days: data?.duration_days ?? 0,
      maxDiff: data?.max_rating_diff ?? 0,
      myRating: data?.my_rating ?? 0,
    })
  }, [])

  // quiet — обновить данные после действия на странице (закрепить нашивку,
  // принять дуэль): без лоадера на весь экран и без прыжка прокрутки.
  const loadProfile = useCallback(({ quiet = false }: { quiet?: boolean } = {}) => {
    const profileUrl = isOwnProfile
      ? '/api/v1/profile/me/'
      : `/api/v1/profile/${encodeURIComponent(routeUsername!)}/`

    const requests: Promise<unknown>[] = [
      api.get(profileUrl).then((res) => {
        const data = res.data as ProfileData
        setProfile(data)
        setEditForm({ callsign: data.callsign || '' })
        if (!isOwnProfile) {
          // Раньше всё это обнулялось: чужой профиль показывал только ник
          // и карточку. Теперь статистика, нашивки и характеристики приходят
          // вместе с профилем; каталог нужен для «N из M нашивок».
          setBadges(data.badges ?? [])
          setQuestsCompleted(data.quests_completed ?? 0)
          setCharacteristics(data.characteristics ?? [])
          return api.get('/api/v1/badges/').then((catalog) => {
            setAllBadges(unwrapList<UserBadge['badge']>(catalog.data))
          })
        }
        return Promise.all([
          api.get('/api/v1/badges/my/'),
          api.get('/api/v1/quests/my-progress/', { params: { completed: true } }),
          api.get('/api/v1/profile/me/characteristics/'),
          api.get('/api/v1/badges/'),
          api.get('/api/v1/social/duels/my/'),
          api.get('/api/v1/social/mentorships/my/'),
        ]).then(([badgesRes, questsRes, charsRes, allBadgesRes, duelsRes, mentorRes]) => {
          const badgeRows = unwrapList<UserBadge>(badgesRes.data)
          badgeRows.sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned))
          setBadges(badgeRows)
          setQuestsCompleted(unwrapList(questsRes.data).length)
          setCharacteristics(unwrapList<CharacteristicItem>(charsRes.data))
          setAllBadges(unwrapList<UserBadge['badge']>(allBadgesRes.data))
          applyDuels(duelsRes.data)
          setMentees(mentorRes.data?.mentees ?? [])
          setMentors(mentorRes.data?.mentors ?? [])
        })
      }),
    ]

    if (!isOwnProfile) {
      // мои дуэли нужны и на чужом профиле: из них видно, можно ли вызвать
      // этого человека — лимит разницы рейтинга задаёт бэкенд
      requests.push(
        api.get('/api/v1/social/duels/my/').then((res) => {
          applyDuels(res.data)
          setMyRating(res.data?.my_rating ?? null)
        }),
      )
    }

    return Promise.all(requests)
      .catch((err) => {
        if (quiet) {
          addToast('Не удалось обновить данные профиля', 'error')
          return
        }
        setProfile(null)
        if (err?.response?.status === 404) {
          setNotFound(true)
        } else {
          setLoadError(true)
        }
      })
      .finally(() => setLoading(false))
  }, [isOwnProfile, routeUsername, applyDuels, addToast])

  // Сброс «загружается» — при смене открытого профиля, во время отрисовки,
  // а не синхронным setState в эффекте (лишний каскадный рендер). Эффект
  // только загружает данные.
  const profileKey = routeUsername ?? ''
  const [shownKey, setShownKey] = useState(profileKey)
  if (shownKey !== profileKey) {
    setShownKey(profileKey)
    setMyRating(null)
    setLoading(true)
    setLoadError(false)
    setNotFound(false)
  }

  useEffect(() => {
    loadProfile()
  }, [loadProfile])

  const retryProfile = () => {
    setLoading(true)
    setLoadError(false)
    setNotFound(false)
    loadProfile()
  }

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

  // Карта пути: пройденные вехи считает бэкенд по реальным событиям.
  // Пустой список — профиль ещё не загрузился.
  const pathPoints = [...PATH_TOP, ...PATH_BOTTOM]
  const reachedCodes = profile?.path_reached ?? []
  const lastReachedIndex = pathPoints.reduce(
    (last, point, i) => (reachedCodes.includes(point.code) ? i : last),
    -1,
  )
  const pathReached = (i: number) => i <= lastReachedIndex
  const pathNodeState = (i: number) =>
    i === lastReachedIndex ? 'current' : i < lastReachedIndex ? 'done' : 'idle'

  // Подписи значений стоят ровно на вершинах графика, поэтому координаты
  // берём у самого чарта после отрисовки и после каждого ресайза.
  const chartRef = useRef<ChartType<'radar'> | null>(null)
  const [vertices, setVertices] = useState<{ current: Point[]; peak: Point[]; center: Point | null }>({ current: [], peak: [], center: null })
  const [axisAnchors, setAxisAnchors] = useState<AxisAnchor[]>([])

  const syncVertices = useCallback(() => {
    const chart = chartRef.current
    if (!chart) return
    const scale = chart.scales.r as unknown as {
      xCenter: number
      yCenter: number
      drawingArea: number
      getPointPosition: (i: number, d: number) => { x: number; y: number }
    }
    if (!scale) return

    // Пик подписан прямо на своей вершине, текущее значение — в углу
    // пятиугольника, как в макете.
    setVertices({
      current: AXES.map((_, i) => scale.getPointPosition(i, scale.drawingArea)),
      peak: chart.getDatasetMeta(1).data.map((point) => ({ x: point.x, y: point.y })),
      center: { x: scale.xCenter, y: scale.yCenter },
    })

    // Подпись оси уводим за пилюлю: считаем, насколько та выступает
    // вдоль луча, и добавляем зазор.
    setAxisAnchors(AXES.map((_, i) => {
      const outer = scale.getPointPosition(i, scale.drawingArea)
      const dx = outer.x - scale.xCenter
      const dy = outer.y - scale.yCenter
      const length = Math.hypot(dx, dy) || 1
      const ux = dx / length
      const uy = dy / length
      const pillReach = Math.abs(ux) * VALUE_PILL.halfWidth + Math.abs(uy) * VALUE_PILL.halfHeight
      const point = scale.getPointPosition(i, scale.drawingArea + pillReach + AXIS_LABEL_GAP)
      return { x: point.x, y: point.y, ux, uy }
    }))
  }, [])

  const radarOptions = useMemo(() => ({
    ...radarBaseOptions,
    animation: { ...radarBaseOptions.animation, onComplete: syncVertices },
    onResize: syncVertices,
  }), [syncVertices])

  const selectedAxis = activeAxis ?? 'Мощность'
  const activeHistory = getSkill(selectedAxis).history
  const closeHistory = useCallback(() => setActiveAxis(null), [])



  // Анимация чисел в статистике


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

  const showCharacteristics = characteristics.length > 0
  const pinnedBadges = useMemo(() => {
    const pinned = badges.filter((b) => b.is_pinned).slice(0, 3)
    // В чужом профиле пустой ряд «нет закреплённых» ничего не говорит о
    // человеке — показываем последние полученные (сервер отдаёт их первыми).
    return pinned.length || isOwnProfile ? pinned : badges.slice(0, 3)
  }, [badges, isOwnProfile])
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

  const handlePinBadge = (code: string, isPinned = false) => {
    // Повторное нажатие снимает закрепление: раньше открепить было нельзя
    // ни из интерфейса, ни через API.
    const request = isPinned
      ? api.delete(`/api/v1/badges/${encodeURIComponent(code)}/pin/`)
      : api.post(`/api/v1/badges/${encodeURIComponent(code)}/pin/`)
    return request
      .then(() => {
        addToast(isPinned ? 'Нашивка откреплена' : 'Нашивка закреплена!', 'success')
        loadProfile({ quiet: true })
      })
      .catch(() => addToast('Не удалось изменить нашивку', 'error'))
  }

  // Карточка нашивки — та же шторка, что на странице нашивок: описание
  // берём из каталога, дату и закрепление — из своих нашивок.
  const [sheetCode, setSheetCode] = useState<string | null>(null)
  const [pinning, setPinning] = useState(false)
  const closeSheet = useCallback(() => setSheetCode(null), [setSheetCode])
  // Без useMemo: поиск по паре десятков нашивок дешевле, чем мемоизация,
  // которую компилятор React к тому же не смог сохранить.
  const sheetSource = sheetCode
    ? allBadges.find((b) => b.code === sheetCode) ?? badges.find((b) => b.badge.code === sheetCode)?.badge
    : undefined
  const sheetBadge: Badge | null = sheetSource
    ? {
        code: sheetSource.code,
        title: sheetSource.title,
        category: sheetSource.category,
        rarity: sheetSource.rarity,
        description: sheetSource.description ?? '',
        reward_coins: sheetSource.reward_coins ?? 0,
      }
    : null
  const sheetOwn = sheetBadge ? badges.find((b) => b.badge.code === sheetBadge.code) : undefined
  const sheetEarned: EarnedBadge | undefined = sheetOwn && sheetBadge
    ? { id: sheetOwn.id, badge: sheetBadge, acquired_at: sheetOwn.acquired_at, is_pinned: sheetOwn.is_pinned }
    : undefined
  const togglePinFromSheet = (badge: Badge) => {
    setPinning(true)
    handlePinBadge(badge.code, Boolean(sheetEarned?.is_pinned)).finally(() => setPinning(false))
  }

  const duelAction = (id: number, action: 'accept' | 'reject' | 'cancel', message: string) => {
    api.post(`/api/v1/social/duels/${id}/${action}/`)
      .then(() => { addToast(message, 'success'); loadProfile({ quiet: true }) })
      .catch((err) => addToast(apiErrorMessage(err, 'Не удалось выполнить действие'), 'error'))
  }

  const challengeAgent = () => {
    if (!duelUsername) {
      addToast('Выберите соперника из списка', 'error')
      return
    }
    api.post('/api/v1/social/duels/', { opponent_username: duelUsername })
      .then(() => {
        addToast('Вызов отправлен!', 'success')
        duelModal.hide()
        setDuelUsername('')
        loadProfile({ quiet: true })
      })
      .catch((err) => addToast(apiErrorMessage(err, 'Не удалось вызвать на дуэль'), 'error'))
  }

  // Завершённое шефство — уже история, в карточке только действующее.
  const activeMentees = mentees.filter((row) => !row.ended_at)
  const activeMentors = mentors.filter((row) => !row.ended_at)

  const askEndMentorship = (row: MentorshipRow) => {
    setEndTarget(row)
    endModal.show()
  }

  const endMentorship = () => {
    if (!endTarget) return
    api.post(`/api/v1/social/mentorships/${endTarget.id}/end/`)
      .then(() => {
        addToast('Шефство завершено', 'success')
        endModal.hide()
        loadProfile({ quiet: true })
      })
      .catch((err) => addToast(apiErrorMessage(err, 'Не удалось завершить шефство'), 'error'))
  }

  const handleRespect = () => {
    if (!profile?.username) return
    setSocialBusy(true)
    api.post('/api/v1/social/respects/', { to_username: profile.username })
      .then(() => addToast('Респект отправлен!', 'success'))
      .catch((err) => addToast(apiErrorMessage(err, 'Не удалось отправить респект'), 'error'))
      .finally(() => setSocialBusy(false))
  }

  const handleDuel = () => {
    if (!profile?.username) return
    setSocialBusy(true)
    api.post('/api/v1/social/duels/', { opponent_username: profile.username })
      .then(() => {
        addToast('Вызов на дуэль отправлен!', 'success')
        loadProfile({ quiet: true })
      })
      .catch((err) => addToast(apiErrorMessage(err, 'Не удалось вызвать на дуэль'), 'error'))
      .finally(() => setSocialBusy(false))
  }

  // Почему нельзя вызвать этого человека — пишем текстом под кнопкой:
  // подсказка в title на телефоне не видна, а неактивная кнопка без
  // объяснения выглядит как поломка.
  const hasActiveDuel = duels.some((d) => d.status === 'pending' || d.status === 'accepted')
  const ratingGap = profile?.rating_current != null && myRating != null
    ? Math.abs(myRating - profile.rating_current)
    : null
  const duelBlockReason = isOwnProfile || ratingGap == null
    ? ''
    : hasActiveDuel
      ? 'У тебя уже идёт дуэль — новая станет доступна после неё'
      : duelInfo.maxDiff > 0 && ratingGap > duelInfo.maxDiff
        ? `Разница рейтинга ${ratingGap}, а для дуэли нужна не больше ${duelInfo.maxDiff}`
        : ''
  const canDuel = !isOwnProfile && ratingGap != null && !duelBlockReason

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
        <LoadError onRetry={retryProfile} />
      </div>
    )
  }

  // Косметика читается из applied_items профиля — своего или чужого,
  // поэтому видна всем. Тихая перезагрузка (закрепление нашивки) заменяет
  // профиль целиком, а applied_items приходит в каждом ответе.
  const banner = bannerVariant(profile.applied_items)
  const glow = glowVariant(profile.applied_items)

  return (
    <div className="profile page-enter">
      <div className="profile__top">
        <div className="profile__left">
          <section className={`profile-card profile-card--primary card-entrance${banner ? ` profile-card--banner banner--${banner}` : ''}`}>
            <div className="profile-card__header">
              <div
                className={`profile-card__avatar${isOwnProfile ? ' profile-card__avatar--editable' : ''}${profile.avatar_frame ? ` profile-card__avatar--${profile.avatar_frame}` : ''}`}
                role={isOwnProfile ? 'button' : 'img'}
                tabIndex={isOwnProfile ? 0 : undefined}
                aria-label={isOwnProfile ? 'Сменить аватар' : 'Аватар'}
                onClick={isOwnProfile ? avatarModal.show : undefined}
                onKeyDown={isOwnProfile ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); avatarModal.show() }
                } : undefined}
              >
                {/* диск чёрной дыры — под аватаром, аватар как горизонт событий */}
                {profile.avatar_frame === 'developer' && (
                  <>
                    <span key={`nebula-${profile.username}`} className="dev-nebula" aria-hidden="true" />
                    <span key={`hole-${profile.username}`} className="dev-hole dev-hole--intro" aria-hidden="true" />
                  </>
                )}
                <Avatar
                  src={profile.avatar}
                  name={profile.callsign || profile.username || '?'}
                  className="profile-card__avatar-face"
                />
                {isOwnProfile && <span className="profile-card__avatar-edit" aria-hidden="true">Сменить</span>}
                {profile.avatar_frame === 'developer' && <DevFrame key={profile.username} />}
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
                  {profile?.rating_status ? `${profile.rating_status} ` : ''}ур. {profile?.level ?? 1}
                </span>
              </div>

            </div>
            {isOwnProfile && <BoostPlaque boost={profile.active_boost} />}
          </section>

          <section className="profile-card profile-card--map card-entrance" style={{ animationDelay: '0.1s' }}>
            <h3 className="profile-map__title"><PixelText text="Карта пути:" /></h3>
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
              <span
                className={`profile-map__turn profile-map__turn--${pathReached(PATH_TOP.length) ? 'done' : 'idle'}`}
              />
              <div className="profile-map__row profile-map__row--bottom">
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

        <section className="profile-card profile-card--aside card-entrance" style={{ animationDelay: '0.2s' }}>
          {isOwnProfile && (
            <>
              <button className="profile-aside__btn btn-press" onClick={editModal.show}>Настроить профиль</button>
              <div className="profile-aside__divider" />
            </>
          )}
          <div className="profile-aside__section">
            <h3 className="profile-aside__title"><PixelText text="Статистика:" /></h3>
            <div className="profile-aside__stats">
              <span className="profile-aside__pill">Выполнено квестов: <strong><RollNumber value={questsCompleted} /></strong></span>
              <span className="profile-aside__pill">
                Получено нашивок: <strong><RollNumber value={badges.length} /></strong>{allBadges.length ? <> из <strong>{allBadges.length}</strong></> : null}
              </span>
              {profile?.duel_wins != null && (
                <span className="profile-aside__pill">Побед в дуэлях: <strong>{profile.duel_wins}</strong></span>
              )}
              {profile?.respects_received != null && (
                <span className="profile-aside__pill">
                  Респектов за месяц: <strong>{profile.respects_received}</strong>
                </span>
              )}
            </div>
          </div>

          {!isOwnProfile && (
          <>
            <div className="profile-aside__divider" />
          <div className="profile-aside__section">
            <h3 className="profile-aside__title"><PixelText text="Социальные действия:" /></h3>
            <div className="profile-social">
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
              >
                Вызвать на дуэль
              </button>
              {duelBlockReason && <p className="profile-social__hint">{duelBlockReason}</p>}
            </div>
          </div>
          </>
          )}

          {/* Шефство и дуэли — управление своими связями, в чужом профиле ни к чему. */}
          {isOwnProfile && (
          <>
          <div className="profile-aside__section">
            <h3 className="profile-aside__title"><PixelText text="Шефство:" /></h3>
            <div className="profile-social">
              {activeMentees.map((row) => (
                <div key={row.id} className="profile-social__row">
                  <span className="profile-aside__mentee">{agentName(row.mentee)}</span>
                  <button
                    type="button"
                    className="profile-social__action profile-social__action--light btn-press"
                    onClick={() => askEndMentorship(row)}
                  >
                    Завершить
                  </button>
                </div>
              ))}
              {activeMentors.length > 0 && (
                <div className="profile-social__row">
                  <span className="profile-social__label">
                    {activeMentors.length > 1 ? 'Наставники:' : 'Наставник:'}
                  </span>
                  {activeMentors.map((row) => (
                    <span key={row.id} className="profile-aside__mentee">{agentName(row.mentor)}</span>
                  ))}
                </div>
              )}
              <button className="profile-aside__mentor-btn btn-press" onClick={mentorModal.show}>Стать наставником</button>
            </div>
          </div>

          <div className="profile-aside__section">
            <h3 className="profile-aside__title"><PixelText text="Дуэли:" /></h3>
            <div className="profile-social">
              {duels.length === 0 && <p className="profile-social__empty">Дуэлей пока нет</p>}
              {duels.slice(0, 5).map((duel) => {
                const iAmOpponent = duel.opponent.username === profile?.username
                const rival = iAmOpponent ? duel.challenger : duel.opponent
                const won = duel.winner?.username === profile?.username
                return (
                  <div key={duel.id} className="profile-social__row">
                    <span className="profile-aside__mentee">{agentName(rival)}</span>
                    {duel.status === 'pending' && iAmOpponent && (
                      <span className="profile-social__actions">
                        <button
                          type="button"
                          className="profile-social__action btn-press"
                          onClick={() => duelAction(duel.id, 'accept', 'Вызов принят')}
                        >
                          Принять
                        </button>
                        <button
                          type="button"
                          className="profile-social__action profile-social__action--light btn-press"
                          onClick={() => duelAction(duel.id, 'reject', 'Вызов отклонён')}
                        >
                          Отклонить
                        </button>
                      </span>
                    )}
                    {duel.status === 'pending' && !iAmOpponent && (
                      <>
                        <span className="profile-social__status">ждёт ответа</span>
                        <button
                          type="button"
                          className="profile-social__action profile-social__action--light btn-press"
                          onClick={() => duelAction(duel.id, 'cancel', 'Вызов отозван')}
                        >
                          Отозвать
                        </button>
                      </>
                    )}
                    {duel.status === 'accepted' && (
                      <span className="profile-social__status">
                        {duel.resolve_after ? `итог ${formatDayMonth(duel.resolve_after)}` : 'идёт'}
                      </span>
                    )}
                    {duel.status === 'finished' && (
                      <span
                        className={`profile-social__status${
                          duel.winner ? (won ? ' profile-social__status--win' : '') : ''
                        }`}
                      >
                        {duel.winner ? (won ? 'Победа' : 'Поражение') : 'Ничья'}
                      </span>
                    )}
                    {duel.status === 'rejected' && <span className="profile-social__status">отменена</span>}
                  </div>
                )
              })}
              {duelInfo.bet > 0 && (
                <p className="profile-social__hint">
                  Ставка {duelInfo.bet} {plural(duelInfo.bet, ['монета', 'монеты', 'монет'])}, итог через {duelInfo.days} дн.
                </p>
              )}
              <button
                type="button"
                className="profile-aside__mentor-btn btn-press"
                onClick={duelModal.show}
              >
                Вызвать на дуэль
              </button>
            </div>
          </div>
          </>
          )}
        </section>

      </div>

      {/* Радар и в чужом профиле: характеристики приходят вместе с ним.
          Пустой пятиугольник не рисуем — на пол-экрана он только путает. */}
      {showCharacteristics && (
      <section className="profile-radar card-entrance" style={{ animationDelay: '0.3s' }}>
        <div className="profile-radar__chart">
          <RadarHud
            geo={vertices.center && vertices.current[0] ? {
              cx: vertices.center.x,
              cy: vertices.center.y,
              r: Math.hypot(vertices.current[0].x - vertices.center.x, vertices.current[0].y - vertices.center.y),
            } : null}
            values={AXES.map(({ key }) => getSkill(key).current)}
            max={20}
          />
          <Radar ref={chartRef} data={radarData} options={radarOptions} />

          {/* луч к выбранной оси: видно, о какой характеристике история */}
          {showCharacteristics && activeAxis && vertices.center && (() => {
            const i = AXES.findIndex((a) => a.key === activeAxis)
            const end = vertices.current[i]
            if (!end) return null
            return (
              <svg className="profile-radar__beam" aria-hidden="true">
                <line key={activeAxis} x1={vertices.center.x} y1={vertices.center.y} x2={end.x} y2={end.y} pathLength={1} />
              </svg>
            )
          })()}

          {/* Пик подписываем, только когда он читается: у выбранной оси или
              если вершина отошла от центра. Иначе подписи с маленькими
              значениями слипались в одну кучу посередине. */}
          {showCharacteristics && vertices.peak.map((point, i) => {
            const key = AXES[i].key
            const skill = getSkill(key)
            const center = vertices.center
            const far = center ? Math.hypot(point.x - center.x, point.y - center.y) > 64 : true
            // у самой вершины пик лёг бы на подпись текущего значения
            const corner = vertices.current[i]
            const clear = corner ? Math.hypot(point.x - corner.x, point.y - corner.y) > 46 : true
            const show = (activeAxis === key && clear) || (far && clear && skill.peak !== skill.current)
            return (
              <span
                key={`peak-${i}`}
                className={`profile-radar__value profile-radar__value--inner${show ? '' : ' profile-radar__value--hidden'}${activeAxis === key ? ' profile-radar__value--focus' : ''}`}
                style={{ left: point.x, top: point.y }}
                aria-hidden={!show}
              >
                {skill.peak}
              </span>
            )
          })}

          {showCharacteristics && vertices.current.map((point, i) => (
            <span
              key={`current-${i}`}
              className={`profile-radar__value${activeAxis === AXES[i].key ? ' profile-radar__value--focus' : ''}${activeAxis && activeAxis !== AXES[i].key ? ' profile-radar__value--dim' : ''}`}
              style={{ left: point.x, top: point.y }}
            >
              {getSkill(AXES[i].key).current}
            </span>
          ))}

          {axisAnchors.map((anchor, i) => {
            const key = AXES[i].key
            const skill = getSkill(key)
            const isActive = activeAxis === key
            const isHovered = hoveredAxis === key
            return (
              <button
                type="button"
                key={key}
                aria-pressed={isActive}
                className={`profile-radar__axis${isActive ? ' profile-radar__axis--active' : ''}`}
                style={{
                  left: anchor.x,
                  top: anchor.y,
                  // сдвигаем подпись на половину её размера наружу от вершины
                  transform: `translate(calc(-50% + ${anchor.ux * 50}%), calc(-50% + ${anchor.uy * 50}%))`,
                }}
                onMouseEnter={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect()
                  const outward = anchor.ux < -0.05 ? 'left' : 'right'
                  const room = outward === 'left' ? rect.left : window.innerWidth - rect.right
                  setTipSide(room >= TIP_WIDTH + 24 ? outward : 'above')
                  setHoveredAxis(key)
                }}
                onMouseLeave={() => setHoveredAxis(null)}
                onClick={() => setActiveAxis(cur => cur === key ? null : key)}
              >
                <span className="profile-radar__axis-icon" aria-hidden="true" />
                <span>{key}</span>
                {/* у выбранной оси всё это уже есть в карточке истории */}
                {!isActive && showCharacteristics && (
                  // наружу от пятиугольника и вбок от подписи: снизу и сверху
                  // подсказка легла бы на линии графика
                  <span className={`axis-tip axis-tip--${isHovered ? tipSide : anchor.ux < -0.05 ? 'left' : 'right'}${isHovered ? ' axis-tip--show' : ''}`} aria-hidden="true">
                    <span className="axis-tip__num"><b>{skill.current}</b> / 20</span>
                    <span className="axis-tip__bar">
                      <i style={{ transform: `scaleX(${Math.min(skill.current, 20) / 20})` }} />
                      <em style={{ left: `${(Math.min(skill.peak, 20) / 20) * 100}%` }} />
                    </span>
                    <span className="axis-tip__peak">лучшее {skill.peak}</span>
                  </span>
                )}
              </button>
            )
          })}
        </div>

        <SkillSummary
          skills={AXES.map(({ key }) => ({ key, value: getSkill(key).current, peak: getSkill(key).peak }))}
          max={20}
          onPick={(key) => setActiveAxis((cur) => (cur === key ? null : key))}
        />

        {showCharacteristics && (
          <SkillHistory
            axis={selectedAxis}
            values={activeHistory}
            current={getSkill(selectedAxis).current}
            peak={getSkill(selectedAxis).peak}
            max={20}
            visible={Boolean(activeAxis)}
            onClose={closeHistory}
          />
        )}
      </section>
      )}

      <section className="profile-path profile-card card-entrance" style={{ animationDelay: '0.4s' }}>
        <h3 className="profile-achievements__title"><PixelText text="Достижения:" /></h3>
        <div className="profile-achievements__row">
          {pinnedBadges.length === 0 ? (
            <p className="loading-text">{isOwnProfile ? 'Пока нет закреплённых нашивок' : 'Нашивок пока нет'}</p>
          ) : pinnedBadges.map((item) => (
            <button
              key={item.id}
              className={`ach btn-press${glow ? ` ach--glow ach--glow-${glow}` : ''}`}
              type="button"
              onClick={() => setSheetCode(item.badge.code)}
              aria-haspopup="dialog"
            >
              <span className="ach__icon" aria-hidden="true">
                <BadgeEmblem code={item.badge.code} rarity={item.badge.rarity} size={72} />
              </span>
              <span className="ach__name">{item.badge.title}</span>
              <span className={`ach__rarity ${rarityClass(item.badge.rarity)}`}>
                {RARITY_LABELS[item.badge.rarity] ?? item.badge.rarity}
              </span>
            </button>
          ))}
        </div>

        {/* Категорий семь: на узком экране лента прокручивается вбок.
            Подчёркивание лежит внутри той же прокрутки, иначе индикатор
            уезжал бы от своей вкладки. */}
        <div className="profile-path__tabs-scroll" ref={tabsScrollRef}>
          <div className="profile-path__tabs-inner">
            <div className="profile-path__tabs" ref={tabsContainerRef}>
              {tabs.map((t) => (
                <button
                  key={t}
                  type="button"
                  ref={registerTab(t)}
                  className={`profile-path__tab${t === activeTab ? ' profile-path__tab--active' : ''} btn-press`}
                  onClick={() => setActiveTab(t)}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="profile-path__underline" aria-hidden="true">
              <div className="profile-path__indicator" style={{ width: tabIndicatorBox.width, left: tabIndicatorBox.left }} />
            </div>
          </div>
        </div>

        <div className="profile-path__grid">
          {filteredBadges.map((card) => (
            <button
              key={card.id}
              className={`path-card btn-press${glow ? ` ach--glow ach--glow-${glow}` : ''}`}
              type="button"
              onClick={() => setSheetCode(card.badge.code)}
              aria-haspopup="dialog"
            >
              <span className={`path-card__icon path-card__icon--${card.badge.rarity}`} aria-hidden="true">
                <BadgeEmblem code={card.badge.code} rarity={card.badge.rarity} size={58} />
              </span>
              <span className="path-card__name">{card.badge.title}</span>
              <span className={`path-card__chip path-card__chip--${card.badge.rarity}`}>
                {RARITY_LABELS[card.badge.rarity] ?? card.badge.rarity}
              </span>
              {/* Закрепление — только своих нашивок: в чужом профиле кнопка
                  закрепляла бы нашивку смотрящего, а не владельца. */}
              {isOwnProfile && (
                <span
                  className="path-card__chip path-card__chip--common"
                  style={{ marginTop: 4, cursor: 'pointer' }}
                  onClick={(e) => {
                    e.stopPropagation()
                    handlePinBadge(card.badge.code, Boolean(card.is_pinned))
                  }}
                >
                  {card.is_pinned ? 'Открепить' : 'Закрепить'}
                </span>
              )}
            </button>
          ))}
          {lockedBadges.map((badge) => (
            <button
              key={badge.code}
              type="button"
              className="path-card path-card--locked btn-press"
              onClick={() => setSheetCode(badge.code)}
              aria-haspopup="dialog"
            >
              <span className="path-card__icon path-card__icon--locked" aria-hidden="true">
                <BadgeEmblem code={badge.code} rarity={badge.rarity} locked size={58} />
              </span>
              {/* название вместо одинакового «Условие не выполнено» у всех
                  закрытых: видно, что именно предстоит получить */}
              <span className="path-card__locked">{badge.title}</span>
            </button>
          ))}
          {filteredBadges.length === 0 && lockedBadges.length === 0 && (
            <p className="loading-text" style={{ gridColumn: '1 / -1' }}>Нет нашивок</p>
          )}
        </div>
      </section>

      <BadgeSheet
        badge={sheetBadge}
        earned={sheetEarned}
        pinning={pinning}
        onClose={closeSheet}
        onTogglePin={isOwnProfile ? togglePinFromSheet : undefined}
      />

      {/* Модалка настройки профиля */}
      {editModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={editModalRef}>
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

      {/* Модалка вызова на дуэль: соперника ищем, а не ищем его профиль вручную */}
      {duelModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={duelModalRef}>
            <h3 className="popup__title">Вызвать на дуэль</h3>
            <label className="popup__label">
              Ставка {duelInfo.bet} {plural(duelInfo.bet, ['монета', 'монеты', 'монет'])}. Побеждает тот, кто за {duelInfo.days} дн. прибавит
              больше рейтинга
            </label>
            <AgentPicker
              picked={duelUsername}
              onPick={(agent) => setDuelUsername(agent.username)}
              disabledReason={(agent) =>
                duelInfo.maxDiff && Math.abs(agent.rating_current - duelInfo.myRating) > duelInfo.maxDiff
                  ? `рейтинг ${agent.rating_current}: разница больше ${duelInfo.maxDiff}`
                  : ''
              }
              placeholder="кого вызываем"
              autoFocus
            />
            <div className="shop-modal__buttons">
              <button
                type="button"
                className="shop-modal__btn shop-modal__btn--secondary btn-press"
                onClick={duelModal.hide}
              >
                Отмена
              </button>
              <button
                type="button"
                className="shop-modal__btn shop-modal__btn--primary btn-press"
                onClick={challengeAgent}
              >
                Вызвать
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка стать наставником */}
      {mentorModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={mentorModalRef}>
            <h3 className="popup__title">Стать наставником</h3>
            <label className="popup__label">Найдите студента по позывному или имени</label>
            <AgentPicker picked={menteeUsername} onPick={(agent) => setMenteeUsername(agent.username)} autoFocus />
            <div className="shop-modal__buttons">
              <button type="button" className="shop-modal__btn shop-modal__btn--secondary btn-press" onClick={mentorModal.hide}>
                Отмена
              </button>
              <button type="button" className="shop-modal__btn shop-modal__btn--primary btn-press" onClick={() => {
                const username = menteeUsername.trim()
                if (!username) {
                  addToast('Выберите студента из списка', 'error')
                  return
                }
                api.post('/api/v1/social/mentorships/', { mentee_username: username })
                  .then(() => {
                    addToast('Наставничество оформлено!', 'success')
                    mentorModal.hide()
                    setMenteeUsername('')
                    loadProfile({ quiet: true })
                  })
                  .catch((err) => addToast(apiErrorMessage(err, 'Не удалось оформить наставничество'), 'error'))
              }}>
                Подтвердить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Подтверждение: завершить шефство */}
      {endModal.open && endTarget && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={endModalRef}>
            <h3 className="popup__title">Завершить шефство?</h3>
            <p className="popup__label">
              {agentName(endTarget.mentee)} больше не будет числиться твоим подшефным, а еженедельные монеты
              за него перестанут начисляться.
            </p>
            <div className="shop-modal__buttons">
              <button type="button" className="shop-modal__btn shop-modal__btn--secondary btn-press" onClick={endModal.hide}>
                Отмена
              </button>
              <button type="button" className="shop-modal__btn shop-modal__btn--primary btn-press" onClick={endMentorship}>
                Завершить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка смены аватара */}
      {avatarModal.open && (
        <div className="modal-fixed">
          <div className="modal-fixed__content" ref={avatarModalRef}>
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
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  )
}
