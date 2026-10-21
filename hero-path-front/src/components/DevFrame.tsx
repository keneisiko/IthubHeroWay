import DevFrameArt from './DevFrameArt'

// пиксели, которые затягивает в дыру: по кругу, на разном расстоянии
const DEBRIS = Array.from({ length: 14 }, (_, i) => ({
  angle: i * (360 / 14) + (i % 2) * 11,
  dist: 92 + (i % 3) * 26,
  delay: (i % 5) * 0.06,
}))

/**
 * Рамка разработчика в карточке профиля. При открытии — чёрная дыра:
 * вокруг темнеет, в центре открывается сингулярность, пиксели
 * закручиваются по спирали и падают в неё, расходится волна
 * искажения, аватар выходит из горизонта, тушь и диск собираются в
 * рамку, выезжает плашка «Разработчик». Стили — styles/avatar-frames.css.
 */
export default function DevFrame() {
  return (
    <span className="dev-frame" aria-hidden="true">
      <span className="dev-intro">
        <span className="dev-intro__veil" />
        <span className="dev-intro__core" />
        <span className="dev-intro__wave" />
        {DEBRIS.map((d, i) => (
          <i
            key={i}
            className="dev-intro__px"
            style={{ '--a': `${d.angle}deg`, '--r': `${d.dist}px`, '--d': `${d.delay}s` } as React.CSSProperties}
          />
        ))}
      </span>
      <DevFrameArt intro large />
      <span className="dev-frame__tag">
        <span className="dev-frame__code">&lt;/&gt;</span>
        Разработчик
      </span>
    </span>
  )
}
