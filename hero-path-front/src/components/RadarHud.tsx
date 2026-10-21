import '../styles/radar-hud.css'

/**
 * Обвязка вокруг пятиугольника характеристик: уголки прицела по краям,
 * медленная орбита из квадратных точек и деления на ней. Сам график не
 * трогает — лежит под ним и не ловит нажатия.
 */
export default function RadarHud() {
  return (
    <div className="radar-hud" aria-hidden="true">
      <svg className="radar-hud__orbit" viewBox="0 0 100 100">
        <circle className="radar-hud__ring radar-hud__ring--outer" cx="50" cy="50" r="47" pathLength={360} />
        <circle className="radar-hud__ring radar-hud__ring--inner" cx="50" cy="50" r="41" pathLength={360} />
        {Array.from({ length: 5 }, (_, i) => {
          // деления — напротив вершин пятиугольника (первая ось сверху)
          const a = (-90 + i * 72) * (Math.PI / 180)
          return (
            <rect
              key={i}
              className="radar-hud__tick"
              x={50 + Math.cos(a) * 47 - 1.6}
              y={50 + Math.sin(a) * 47 - 1.6}
              width="3.2"
              height="3.2"
            />
          )
        })}
      </svg>
      <i className="radar-hud__corner radar-hud__corner--tl" />
      <i className="radar-hud__corner radar-hud__corner--tr" />
      <i className="radar-hud__corner radar-hud__corner--bl" />
      <i className="radar-hud__corner radar-hud__corner--br" />
    </div>
  )
}
