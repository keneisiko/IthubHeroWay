import { useEffect, useId, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api'
import Avatar from './Avatar'
import { formatDateRu, formatDayMonth } from '../lib/apiData'
import { plural } from '../lib/plural'

interface Holder {
  username: string
  callsign: string
  avatar: string | null
  avatar_frame: string
  squad: string
  acquired_at: string
}

interface HoldersData {
  count: number
  results: Holder[]
}

// дата без года, если получена в этом году
const when = (iso: string) => (
  new Date(iso).getFullYear() === new Date().getFullYear() ? formatDayMonth(iso) : formatDateRu(iso)
)

// Карточку одной нашивки открывают по многу раз — список держим, пока жива вкладка.
const cache = new Map<string, HoldersData>()

interface Props {
  code: string
  /** Переход в профиль владельца закрывает шторку. */
  onNavigate: () => void
}

/**
 * «У кого есть» в карточке нашивки: кнопка с числом владельцев и
 * выпадающий список — кто и когда получил, первыми самые ранние.
 */
export default function BadgeHolders({ code, onNavigate }: Props) {
  const [data, setData] = useState<HoldersData | null>(() => cache.get(code) ?? null)
  const [shownCode, setShownCode] = useState(code)
  const [open, setOpen] = useState(false)
  const [failed, setFailed] = useState(false)
  const listId = useId()

  if (code !== shownCode) {
    setShownCode(code)
    setData(cache.get(code) ?? null)
    setOpen(false)
    setFailed(false)
  }

  useEffect(() => {
    if (cache.has(code)) return
    let alive = true
    api.get<HoldersData>(`/api/v1/badges/${encodeURIComponent(code)}/holders/`)
      .then((res) => {
        cache.set(code, res.data)
        if (alive) setData(res.data)
      })
      .catch(() => { if (alive) setFailed(true) })
    return () => { alive = false }
  }, [code])

  const count = data?.count ?? 0
  const label = data
    ? count === 0
      ? 'Пока ни у кого нет'
      : `У ${count} ${plural(count, ['агента', 'агентов', 'агентов'])}`
    : failed ? 'Список не загрузился' : 'Считаем владельцев…'

  return (
    <div className={`bd-holders${open ? ' bd-holders--open' : ''}`}>
      <button
        type="button"
        className="bd-holders__toggle btn-press"
        onClick={() => setOpen((v) => !v)}
        disabled={!data || count === 0}
        aria-expanded={open}
        aria-controls={listId}
      >
        <span className="bd-holders__faces" aria-hidden="true">
          {data?.results.slice(0, 3).map((h) => (
            <Avatar key={h.username} src={h.avatar} name={h.callsign || h.username} className="bd-holders__face" />
          ))}
        </span>
        <span className="bd-holders__label">{label}</span>
        <svg className="bd-holders__chevron" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      <div className="bd-holders__drawer" id={listId} hidden={!data || count === 0}>
        <div className="bd-holders__inner">
        <ol className="bd-holders__list">
          {data?.results.map((h, i) => (
            <li key={h.username} className="bd-holders__row" style={{ '--i': i } as React.CSSProperties}>
              <Link to={`/profile/${h.username}`} className="bd-holders__link" onClick={onNavigate} tabIndex={open ? 0 : -1}>
                <Avatar src={h.avatar} name={h.callsign || h.username} frame={h.avatar_frame} className="bd-holders__avatar" />
                <span className="bd-holders__who">
                  <span className="bd-holders__name">{h.callsign || h.username}</span>
                  <span className="bd-holders__squad">{h.squad || `@${h.username}`}</span>
                </span>
                <span className="bd-holders__when">
                  {i === 0 && <span className="bd-holders__first">первым</span>}
                  {when(h.acquired_at)}
                </span>
              </Link>
            </li>
          ))}
        </ol>
        {data && data.count > data.results.length && (
          <p className="bd-holders__more">и ещё {data.count - data.results.length}</p>
        )}
        </div>
      </div>
    </div>
  )
}
