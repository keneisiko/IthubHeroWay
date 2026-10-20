const PIXELS: { top: string; left: string; delay: number; kind?: 'coin' | 'frame' }[] = [
  { top: '9%', left: '91%', delay: 0 },
  { top: '18%', left: '84%', delay: 2.4, kind: 'frame' },
  { top: '31%', left: '96%', delay: 5.1 },
  { top: '6%', left: '72%', delay: 6.8, kind: 'coin' },
  { top: '74%', left: '3%', delay: 1.3 },
  { top: '86%', left: '9%', delay: 3.9, kind: 'frame' },
  { top: '93%', left: '18%', delay: 7.2 },
  { top: '64%', left: '6%', delay: 4.6, kind: 'coin' },
]

/** Фон оболочки: сетка пикселей по краям и редкие вспышки клеток. */
export default function Atmosphere() {
  return (
    <div className="atmo" aria-hidden="true">
      <div className="atmo__grid" />
      {PIXELS.map((px, i) => (
        <span
          key={i}
          className={`atmo__px${px.kind ? ` atmo__px--${px.kind}` : ''}`}
          style={{ top: px.top, left: px.left, animationDelay: `${px.delay}s` }}
        />
      ))}
    </div>
  )
}
