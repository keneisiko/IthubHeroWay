import '../styles/radar-hud.css'

export interface RadarGeo {
  cx: number
  cy: number
  r: number
}

interface RadarHudProps {
  /** Центр и радиус пятиугольника в пикселях поля графика — берутся у Chart.js. */
  geo?: RadarGeo | null
  axes?: number
}

// один оборот луча; вершина вспыхивает, когда луч проходит над ней
const SWEEP_S = 6

/**
 * Радар-сканер под пятиугольником: по нему идёт луч, обрезанный ровно
 * по форме графика, внутри — пиксельная сетка; вершины осей вспыхивают
 * пикселем IThub, когда луч их проходит. По краям поля — уголки прицела.
 * Сам график не трогает: лежит под ним и не ловит нажатия.
 */
export default function RadarHud({ geo, axes = 5 }: RadarHudProps) {
  // вершины многоугольника в процентах от его квадрата: первая ось сверху
  const polygon = Array.from({ length: axes }, (_, i) => {
    const a = ((-90 + (360 / axes) * i) * Math.PI) / 180
    return `${(50 + 50 * Math.cos(a)).toFixed(2)}% ${(50 + 50 * Math.sin(a)).toFixed(2)}%`
  }).join(', ')

  return (
    <div className="radar-hud" aria-hidden="true">
      {geo && geo.r > 0 && (
        <>
          <div
            className="radar-hud__scope"
            style={{
              left: geo.cx - geo.r,
              top: geo.cy - geo.r,
              width: geo.r * 2,
              height: geo.r * 2,
              clipPath: `polygon(${polygon})`,
              '--sweep': `${SWEEP_S}s`,
            } as React.CSSProperties}
          >
            <span className="radar-hud__beam" />
          </div>
          {Array.from({ length: axes }, (_, i) => {
            const a = ((-90 + (360 / axes) * i) * Math.PI) / 180
            return (
              <span
                key={i}
                className="radar-hud__ping"
                style={{
                  left: geo.cx + geo.r * Math.cos(a),
                  top: geo.cy + geo.r * Math.sin(a),
                  animationDelay: `${(SWEEP_S / axes) * i}s`,
                  '--sweep': `${SWEEP_S}s`,
                } as React.CSSProperties}
              />
            )
          })}
        </>
      )}
      <i className="radar-hud__corner radar-hud__corner--tl" />
      <i className="radar-hud__corner radar-hud__corner--tr" />
      <i className="radar-hud__corner radar-hud__corner--bl" />
      <i className="radar-hud__corner radar-hud__corner--br" />
    </div>
  )
}
