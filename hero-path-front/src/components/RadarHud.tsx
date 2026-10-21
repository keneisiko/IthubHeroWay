import '../styles/radar-hud.css'

export interface RadarGeo {
  cx: number
  cy: number
  r: number
}

interface RadarHudProps {
  /** Центр и радиус пятиугольника в пикселях поля графика — берутся у Chart.js. */
  geo?: RadarGeo | null
  /** Значения осей по порядку графика и максимум шкалы — по ним рисуется аура. */
  values?: number[]
  max?: number
}

// светлые частицы внутри пятиугольника: место, размер, темп
const MOTES = Array.from({ length: 12 }, (_, i) => ({
  x: 18 + ((i * 37) % 64),
  y: 30 + ((i * 53) % 52),
  size: 3 + (i % 3),
  dur: 7 + (i % 5) * 1.3,
  delay: -(i * 1.7),
}))

function polygon(points: number[], axes: number): string {
  return points.map((k, i) => {
    const a = ((-90 + (360 / axes) * i) * Math.PI) / 180
    return `${(50 + 50 * k * Math.cos(a)).toFixed(2)}% ${(50 + 50 * k * Math.sin(a)).toFixed(2)}%`
  }).join(', ')
}

/**
 * Мягкая подложка под пятиугольником: за графиком светится размытая
 * аура ровно по форме значений и медленно дышит, внутри поля плавают
 * светлые частицы. Сам график не трогает — лежит под ним.
 */
export default function RadarHud({ geo, values = [], max = 20 }: RadarHudProps) {
  if (!geo || geo.r <= 0) return null
  const axes = values.length || 5
  const shape = values.length
    ? polygon(values.map((v) => Math.max(0.12, Math.min(v, max) / max)), axes)
    : polygon(Array(axes).fill(1), axes)
  const field = polygon(Array(axes).fill(1), axes)
  const box = {
    left: geo.cx - geo.r,
    top: geo.cy - geo.r,
    width: geo.r * 2,
    height: geo.r * 2,
  }

  return (
    <div className="radar-hud" aria-hidden="true">
      <div className="radar-hud__aura" style={box}>
        <span className="radar-hud__aura-shape" style={{ clipPath: `polygon(${shape})` }} />
      </div>
      <div className="radar-hud__field" style={{ ...box, clipPath: `polygon(${field})` }}>
        {MOTES.map((m, i) => (
          <i
            key={i}
            className="radar-hud__mote"
            style={{
              left: `${m.x}%`,
              top: `${m.y}%`,
              width: m.size,
              height: m.size,
              animationDuration: `${m.dur}s`,
              animationDelay: `${m.delay}s`,
            }}
          />
        ))}
      </div>
    </div>
  )
}
