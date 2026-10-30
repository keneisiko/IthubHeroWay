// раскладки для разных карточек: сколько фонариков в гирлянде, когда
// спускается паук и когда в углу загораются глаза — чтобы карточки не
// жили в унисон
const LAYOUTS = [
  { lanterns: [0.14, 0.38, 0.62, 0.86], spider: 0, eyes: 2 },
  { lanterns: [0.2, 0.5, 0.8], spider: -3.5, eyes: -4 },
  { lanterns: [0.12, 0.34, 0.56, 0.78], spider: -6, eyes: -7.5 },
  { lanterns: [0.08, 0.22, 0.36, 0.5, 0.64, 0.78, 0.92], spider: -2, eyes: -10 },
]

// провисание нитки: та же дуга, что у пути в SVG (M0 2 Q50 30 100 2), в px высоты гирлянды
const sag = (t: number) => (2 + 56 * t * (1 - t)) * (34 / 30)

/**
 * Живность хэллоуинской карточки профиля: вдоль верхнего края провисает
 * гирлянда из тыкв-фонариков, в углу вниз головой спит летучая мышь, с
 * паутины спускается паук, по дну ползёт пиксельный туман, снизу
 * вздрагивает свет свечи, в тёмном углу изредка загораются чьи-то глаза,
 * сквозь карточку проплывает призрак. Всё — за содержимым.
 */
export default function CardHaunt({ variant = 0 }: { variant?: number }) {
  const l = LAYOUTS[variant % LAYOUTS.length]
  return (
    <span className="haunt" aria-hidden="true">
      <span className="haunt__glow" />
      <span className="haunt__fog" />
      <span className="haunt__garland">
        <svg className="haunt__rope" viewBox="0 0 100 30" preserveAspectRatio="none">
          <path d="M0 2 Q50 30 100 2" />
        </svg>
        {l.lanterns.map((t, i) => (
          <i
            key={t}
            className="haunt__lantern"
            style={{ left: `${t * 100}%`, top: `${sag(t) - 1}px`, '--d': `${-(i * 0.9 + variant * 0.7)}s` } as React.CSSProperties}
          />
        ))}
      </span>
      <span className="haunt__bat" style={{ left: variant % 2 ? '3%' : '5%', '--d': `${-(variant * 2.2)}s` } as React.CSSProperties} />
      <span className="haunt__spider" style={{ '--d': `${l.spider}s` } as React.CSSProperties} />
      <span className="haunt__eyes" style={{ '--d': `${l.eyes}s` } as React.CSSProperties} />
      <span className="haunt__ghost" style={{ '--d': `${l.spider * 2 - variant * 4}s` } as React.CSSProperties} />
    </span>
  )
}
