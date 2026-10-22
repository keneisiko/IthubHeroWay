import { useId } from 'react'

// два облака с разным шумом дрейфуют навстречу друг другу
const LAYERS = [
  { seed: 4, freq: 0.016, cut: -0.95 },
  { seed: 17, freq: 0.024, cut: -1.15 },
]

/**
 * Аура вокруг рамки разработчика — клубы космической туманности.
 * Шум рисуется один раз, дальше слои только медленно поворачиваются
 * (styles/avatar-frames.css, .dev-aura): фильтр не пересчитывается,
 * поворот делает композитор.
 */
export default function DevAura() {
  const id = useId().replace(/:/g, '')

  return (
    <span className="dev-aura" aria-hidden="true">
      {LAYERS.map((l, i) => (
        <svg key={l.seed} className={`dev-aura__layer dev-aura__layer--${i}`} viewBox="0 0 200 200">
          <defs>
            <filter id={`${id}-f${i}`} x="0" y="0" width="100%" height="100%">
              <feTurbulence type="fractalNoise" baseFrequency={l.freq} numOctaves="4" seed={l.seed} />
              {/* шум в белый дым: прозрачность из яркости, тонкие места тают */}
              <feColorMatrix type="matrix" values={`0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  2.6 0 0 0 ${l.cut}`} />
            </filter>
            <radialGradient id={`${id}-g${i}`}>
              <stop offset="0.3" stopColor="#fff" />
              <stop offset="0.62" stopColor="#fff" stopOpacity="0.55" />
              <stop offset="1" stopColor="#fff" stopOpacity="0" />
            </radialGradient>
            <mask id={`${id}-m${i}`}>
              <circle cx="100" cy="100" r="100" fill={`url(#${id}-g${i})`} />
            </mask>
          </defs>
          <rect width="200" height="200" filter={`url(#${id}-f${i})`} mask={`url(#${id}-m${i})`} />
        </svg>
      ))}
    </span>
  )
}
