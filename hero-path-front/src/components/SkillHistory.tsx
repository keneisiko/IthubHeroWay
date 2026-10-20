import { useEffect, useMemo, useRef, useState } from 'react'

/**
 * История характеристики за последние недели — карточка у радара профиля.
 *
 * Раньше ось Y всегда шла от 0 до 20, и при значениях около нуля график
 * был плоской линией по дну. Теперь масштаб подбирается под данные,
 * крупно показано текущее значение и изменение за период, линия
 * прорисовывается при каждом выборе оси, по точкам можно пройтись.
 */

interface Props {
  axis: string
  values: number[]
  current: number
  peak: number
  max: number
  visible: boolean
  onClose: () => void
}

const W = 240
const H = 112
const PAD = { top: 22, right: 10, bottom: 8, left: 10 }

const STEPS = [1, 2, 5, 10, 15, 20, 30, 50, 100]

function niceMax(value: number, limit: number): number {
  const target = Math.max(value * 1.2, 1)
  const step = STEPS.find((s) => s >= target) ?? target
  return Math.min(step, Math.max(limit, value))
}

function format(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

/** Сглаженная кривая через точки (Catmull-Rom → кубические Безье). */
function smoothPath(points: { x: number; y: number }[]): string {
  if (points.length === 0) return ''
  if (points.length === 1) return `M${points[0].x},${points[0].y}`
  let d = `M${points[0].x},${points[0].y}`
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[i + 2] ?? p2
    const t = 0.18
    const c1x = p1.x + (p2.x - p0.x) * t
    const c1y = p1.y + (p2.y - p0.y) * t
    const c2x = p2.x - (p3.x - p1.x) * t
    const c2y = p2.y - (p3.y - p1.y) * t
    d += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${p2.x},${p2.y}`
  }
  return d
}

export default function SkillHistory({ axis, values, current, peak, max, visible, onClose }: Props) {
  const series = useMemo(() => (values.length > 0 ? values : [0]), [values])
  const [focus, setFocus] = useState(series.length - 1)

  // новая ось — точка снова на «сейчас»
  const [shownAxis, setShownAxis] = useState(axis)
  if (axis !== shownAxis) {
    setShownAxis(axis)
    setFocus(series.length - 1)
  }

  // На телефоне карточка раскрывается под радаром — подводим её в кадр,
  // иначе нажатие на ось выглядело так, будто ничего не произошло.
  const rootRef = useRef<HTMLElement>(null)
  useEffect(() => {
    if (!visible || !window.matchMedia('(max-width: 980px)').matches) return
    const timer = window.setTimeout(() => {
      rootRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, 220)
    return () => window.clearTimeout(timer)
  }, [visible, axis])

  useEffect(() => {
    if (!visible) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [visible, onClose])

  const top = niceMax(Math.max(...series), max)
  const points = useMemo(() => {
    const innerW = W - PAD.left - PAD.right
    const innerH = H - PAD.top - PAD.bottom
    return series.map((v, i) => ({
      x: PAD.left + (series.length === 1 ? innerW / 2 : (i / (series.length - 1)) * innerW),
      y: PAD.top + innerH - (Math.min(v, top) / top) * innerH,
      value: v,
    }))
  }, [series, top])

  const line = smoothPath(points)
  const area = points.length > 1
    ? `${line} L${points[points.length - 1].x},${H - PAD.bottom} L${points[0].x},${H - PAD.bottom} Z`
    : ''

  const first = series[0]
  const last = series[series.length - 1]
  const delta = Math.round((last - first) * 10) / 10
  const deltaText = delta === 0
    ? 'без изменений'
    : `${delta > 0 ? '+' : '−'}${format(Math.abs(delta))} за ${series.length} нед.`
  const focused = points[Math.min(focus, points.length - 1)]

  return (
    <section
      ref={rootRef}
      className={`skill-history${visible ? ' skill-history--visible' : ''}`}
      aria-hidden={!visible}
      aria-label={`История: ${axis}`}
    >
      <header className="skill-history__head">
        <span className="skill-history__axis">{axis}</span>
        <button type="button" className="skill-history__close" onClick={onClose} aria-label="Закрыть историю" tabIndex={visible ? 0 : -1}>
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
        </button>
      </header>

      <div className="skill-history__now">
        <strong>{format(current)}</strong>
        <span className="skill-history__of">из {max}</span>
        <span className={`skill-history__delta${delta > 0 ? ' is-up' : delta < 0 ? ' is-down' : ''}`}>{deltaText}</span>
      </div>
      <p className="skill-history__peak">Лучшее значение: {format(peak)}</p>

      <svg key={`${axis}-${series.join(',')}`} className="skill-history__chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`По неделям: ${series.map(format).join(', ')}`}>
        <defs>
          <linearGradient id="skill-history-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f5f5f5" stopOpacity="0.42" />
            <stop offset="100%" stopColor="#f5f5f5" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.5, 1].map((f) => (
          <line
            key={f}
            className="skill-history__grid"
            x1={PAD.left}
            x2={W - PAD.right}
            y1={PAD.top + (H - PAD.top - PAD.bottom) * (1 - f)}
            y2={PAD.top + (H - PAD.top - PAD.bottom) * (1 - f)}
          />
        ))}
        <line className="skill-history__base" x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom} />
        {area && <path className="skill-history__area" d={area} fill="url(#skill-history-fill)" />}
        <path className="skill-history__line" d={line} pathLength={1} />
        {focused && (
          <line className="skill-history__guide" x1={focused.x} x2={focused.x} y1={focused.y} y2={H - PAD.bottom} />
        )}
        {points.map((p, i) => (
          <g
            key={i}
            className={`skill-history__pt${i === focus ? ' is-focus' : ''}${i === points.length - 1 ? ' is-last' : ''}`}
            style={{ '--i': i } as React.CSSProperties}
            onPointerEnter={() => setFocus(i)}
            onClick={() => setFocus(i)}
          >
            <circle className="skill-history__hit" cx={p.x} cy={p.y} r="14" />
            <circle className="skill-history__dot" cx={p.x} cy={p.y} r={i === points.length - 1 ? 5 : 3.5} />
          </g>
        ))}
        {focused && (
          <g className="skill-history__tip" transform={`translate(${Math.min(Math.max(focused.x, 26), W - 26)} ${Math.max(focused.y - 14, 10)})`}>
            <rect x="-24" y="-11" width="48" height="20" rx="10" />
            <text y="3.5" textAnchor="middle">{format(focused.value)}</text>
          </g>
        )}
      </svg>

      <div className="skill-history__weeks" aria-hidden="true">
        {series.map((_, i) => (
          <span key={i} className={i === focus ? 'is-focus' : ''}>
            {i === series.length - 1 ? 'сейчас' : `−${series.length - 1 - i}`}
          </span>
        ))}
      </div>
    </section>
  )
}
