import '../styles/radar-hud.css'

interface SkillRow {
  key: string
  value: number
  peak?: number
}

interface SkillSummaryProps {
  skills: SkillRow[]
  max: number
  /** Только сильная сторона и куда расти, без шкал по осям. */
  compact?: boolean
  onPick?: (key: string) => void
}

const CELLS = 10

/**
 * Сводка рядом с пятиугольником: что сильнее всего, куда расти и
 * шкала из пикселей по каждой оси — то же самое, что на графике, но
 * читается сразу, без наведения.
 */
export default function SkillSummary({ skills, max, compact = false, onPick }: SkillSummaryProps) {
  if (skills.length === 0) return null
  const best = skills.reduce((a, b) => (b.value > a.value ? b : a))
  const weak = skills.reduce((a, b) => (b.value < a.value ? b : a))
  const flat = best.value === weak.value

  return (
    <div className={`skill-sum${compact ? ' skill-sum--compact' : ''}`}>
      <div className="skill-sum__head">
        {flat ? (
          <p className="skill-sum__fact">
            <span className="skill-sum__tag">Ровно</span>
            Все оси на одном уровне
          </p>
        ) : (
          <>
            <p className="skill-sum__fact">
              <span className="skill-sum__tag skill-sum__tag--best">Сильная сторона</span>
              <b>{best.key}</b>
            </p>
            <p className="skill-sum__fact">
              <span className="skill-sum__tag skill-sum__tag--grow">Куда расти</span>
              <b>{weak.key}</b>
            </p>
          </>
        )}
      </div>

      {!compact && (
        <ul className="skill-sum__rows">
          {skills.map((s, row) => {
            const filled = Math.round((Math.min(s.value, max) / max) * CELLS)
            const peak = s.peak !== undefined ? Math.round((Math.min(s.peak, max) / max) * CELLS) : 0
            const content = (
              <>
                <span className="skill-sum__name">{s.key}</span>
                <span className="skill-sum__bar" aria-hidden="true">
                  {Array.from({ length: CELLS }, (_, i) => (
                    <i
                      key={i}
                      className={i < filled ? 'is-on' : i < peak ? 'is-peak' : ''}
                      style={{ '--d': `${row * 60 + i * 28}ms` } as React.CSSProperties}
                    />
                  ))}
                </span>
                <span className="skill-sum__value">{s.value}</span>
              </>
            )
            return (
              <li key={s.key} className={s.key === best.key && !flat ? 'is-best' : undefined}>
                {onPick ? (
                  <button type="button" className="skill-sum__row" onClick={() => onPick(s.key)}>{content}</button>
                ) : (
                  <span className="skill-sum__row">{content}</span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
