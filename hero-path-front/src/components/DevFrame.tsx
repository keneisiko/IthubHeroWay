import DevFrameArt from './DevFrameArt'

// пиксели, которые затягивает в дыру: по кругу, на разном расстоянии
const DEBRIS = Array.from({ length: 14 }, (_, i) => ({
  angle: i * (360 / 14) + (i % 2) * 11,
  dist: 92 + (i % 3) * 26,
  delay: (i % 5) * 0.06,
}))

// светящиеся пылинки ауры: своя орбита, темп и размер у каждой
const MOTES = Array.from({ length: 11 }, (_, i) => ({
  angle: i * 33 + (i % 3) * 17,
  radius: 56 + (i % 4) * 8,
  speed: 9 + (i % 5) * 2.3,
  delay: -(i * 1.3),
  size: 2 + (i % 3),
  reverse: i % 3 === 0,
}))

/**
 * Рамка разработчика в карточке профиля. При открытии — чёрная дыра:
 * вокруг темнеет, в центре открывается сингулярность, пиксели падают в
 * неё, аватар выходит из горизонта, тушь собирается в рамку, выезжает
 * плашка «Разработчик». Дальше вокруг живёт аура: мягкое свечение
 * перетекает и дышит (styles/avatar-frames.css, .dev-aura), плавают
 * пылинки света, изредка расходится волна и по аватару пробегает блик.
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
      <span className="dev-fx">
        {MOTES.map((m, i) => (
          <i
            key={i}
            className={`dev-fx__mote${m.reverse ? ' dev-fx__mote--rev' : ''}`}
            style={{
              '--a': `${m.angle}deg`,
              '--r': `${m.radius}px`,
              '--s': `${m.speed}s`,
              '--d': `${m.delay}s`,
              '--z': `${m.size}px`,
            } as React.CSSProperties}
          />
        ))}
        <span className="dev-fx__shock" />
        <span className="dev-fx__glint" />
      </span>
      <span className="dev-frame__tag">
        <span className="dev-frame__code">&lt;/&gt;</span>
        Разработчик
      </span>
    </span>
  )
}
