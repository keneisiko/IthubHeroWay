import { useCallback, useEffect, useState } from 'react'
import api from '../api'

export interface AgentSuggestion {
  username: string
  callsign: string
  full_name: string
  squad: string
  rating_current: number
}

interface Props {
  /** Выбранный студент — подсвечивается в списке. */
  picked: string
  onPick: (agent: AgentSuggestion) => void
  /** Причина, по которой студента выбрать нельзя. Пусто — можно. */
  disabledReason?: (agent: AgentSuggestion) => string
  placeholder?: string
  autoFocus?: boolean
}

/**
 * Поиск студента с подсказками.
 *
 * Наставничество и дуэли раньше требовали ввести username вручную и точно:
 * опечатка давала «не удалось оформить» без намёка, кого вообще можно выбрать.
 * Компонент общий, чтобы поведение поиска не разъезжалось между окнами.
 */
export default function AgentPicker({
  picked,
  onPick,
  disabledReason,
  placeholder = 'начните вводить позывной',
  autoFocus = false,
}: Props) {
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState<AgentSuggestion[]>([])
  const [searching, setSearching] = useState(true)

  const search = useCallback(
    (value: string) =>
      api
        .get('/api/v1/agents/search/', { params: value.trim() ? { q: value.trim() } : {} })
        .then((res) => setOptions(Array.isArray(res.data) ? res.data : []))
        .catch(() => setOptions([]))
        .finally(() => setSearching(false)),
    [],
  )

  // Запрос уходит не на каждую букву: 300 мс тишины после ввода.
  useEffect(() => {
    const timer = setTimeout(() => search(query), 300)
    return () => clearTimeout(timer)
  }, [query, search])

  return (
    <>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        className="popup__input"
        autoFocus={autoFocus}
      />
      <div className="agent-picker">
        {searching && <p className="agent-picker__hint">Ищем…</p>}
        {!searching && options.length === 0 && (
          <p className="agent-picker__hint">Никого не нашли</p>
        )}
        {options.map((agent) => {
          const reason = disabledReason?.(agent) ?? ''
          return (
            <button
              key={agent.username}
              type="button"
              className={`agent-picker__row${
                agent.username === picked ? ' agent-picker__row--picked' : ''
              }${reason ? ' agent-picker__row--disabled' : ''}`}
              onClick={() => !reason && onPick(agent)}
              disabled={Boolean(reason)}
              title={reason || undefined}
            >
              <span className="agent-picker__name">{agent.callsign || agent.username}</span>
              <span className="agent-picker__meta">
                {reason || [agent.full_name, agent.squad].filter(Boolean).join(' · ')}
              </span>
            </button>
          )
        })}
      </div>
    </>
  )
}
