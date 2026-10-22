import { useId } from 'react'

interface DevFrameArtProps {
  /** Проявление при открытии профиля: тушь прорисовывается, звёзды вспыхивают. */
  intro?: boolean
  /** Крупный размер (профиль): свои стили масштаба. */
  large?: boolean
}

// Поле рисунка 140×140, аватар занимает середину 20…120 — рамка
// выходит за аватар на 20% с каждой стороны.
const RING = 'M54 16 H86 A38 38 0 0 1 124 54 V86 A38 38 0 0 1 86 124 H54 A38 38 0 0 1 16 86 V54 A38 38 0 0 1 54 16 Z'
// орбита комет — чуть шире кольца туши
const ORBIT = 'M54 9 H86 A45 45 0 0 1 131 54 V86 A45 45 0 0 1 86 131 H54 A45 45 0 0 1 9 86 V54 A45 45 0 0 1 54 9 Z'
// пиксельная цепь — дуга по правому нижнему углу
const CHAIN = 'M131 70 V86 A45 45 0 0 1 86 131 H62'

// языки пламени-туши слева снизу: вырываются из кольца наружу
const FLAMES = [
  'M18 100 C4 86 -2 66 4 42 C6 64 12 82 24 96 Z',
  'M12 112 C-2 100 -8 84 -6 66 C0 84 6 98 18 108 Z',
  'M28 120 C14 116 4 106 -2 94 C8 104 18 110 32 114 Z',
]

const STARS: [number, number, number][] = [
  [120, 12, 9],
  [133, 32, 4.5],
  [26, 130, 9],
  [8, 30, 4],
]

// кометы: голова-пиксель и хвост из трёх гаснущих пикселей
const COMETS = [
  { dur: 7, begin: 0 },
  { dur: 7, begin: -3.5 },
  { dur: 11, begin: -2 },
]

function star(cx: number, cy: number, r: number): string {
  const k = r * 0.2
  return `M${cx} ${cy - r} Q${cx + k} ${cy - k} ${cx + r} ${cy} Q${cx + k} ${cy + k} ${cx} ${cy + r} Q${cx - k} ${cy + k} ${cx - r} ${cy} Q${cx - k} ${cy - k} ${cx} ${cy - r} Z`
}

const reduceMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * Рамка разработчика — «космическая тушь» в языке IThub: рваное
 * кольцо туши с фиолетовым свечением изнутри, языки туши слева,
 * пиксельная цепь, кометы-пиксели на орбите и мерцающие звёзды.
 */
export default function DevFrameArt({ intro = false, large = false }: DevFrameArtProps) {
  const id = useId().replace(/:/g, '')
  const rough = `dfr-${id}`
  const glow = `dfg-${id}`
  const still = reduceMotion()

  // Три слоя друг над другом. Фильтры SVG пересчитываются при любой
  // перерисовке своего svg, поэтому всё движущееся вынесено в отдельный
  // слой без фильтров: кольцо туши считается один раз, свечение «дышит»
  // прозрачностью всего слоя — это делает композитор без перерисовки.
  return (
    <span
      className={`dev-art${intro ? ' dev-art--intro' : ''}${large ? ' dev-art--large' : ''}`}
      aria-hidden="true"
    >
      <svg className="dev-art__layer dev-art__layer--glow" viewBox="0 0 140 140">
        <defs>
          <filter id={glow} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" />
          </filter>
        </defs>
        <path className="dev-art__energy" d={RING} filter={`url(#${glow})`} />
      </svg>

      <svg className="dev-art__layer" viewBox="0 0 140 140">
        <defs>
          {/* рваный край кисти */}
          <filter id={rough} x="-25%" y="-25%" width="150%" height="150%">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="7" result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="5" />
          </filter>
        </defs>
        <g filter={`url(#${rough})`}>
          <path className="dev-art__ink" d={RING} pathLength={100} />
        </g>
      </svg>

      <svg className="dev-art__layer" viewBox="0 0 140 140">
        <g className="dev-art__flames">
          {FLAMES.map((d, i) => <path key={i} d={d} style={{ '--i': i } as React.CSSProperties} />)}
        </g>
        <path className="dev-art__ink dev-art__ink--dry" d={RING} pathLength={100} />
        <path className="dev-art__chain" d={CHAIN} pathLength={100} />

        {/* кометы — только в крупной рамке: в шапке и списках их не видно, а SMIL стоит кадров */}
        {large && !still && COMETS.map((c, i) => (
          <g key={i} className={`dev-art__comet dev-art__comet--${i}`}>
            {[0, 0.12, 0.24, 0.36].map((lag, j) => (
              <rect key={j} x={-2.6 + j * 0.5} y={-2.6 + j * 0.5} width={5.2 - j} height={5.2 - j} className={j === 0 ? 'is-head' : undefined} style={{ opacity: 1 - j * 0.24 }}>
                <animateMotion dur={`${c.dur}s`} begin={`${c.begin - lag}s`} repeatCount="indefinite" rotate="auto" path={ORBIT} />
              </rect>
            ))}
          </g>
        ))}

        {STARS.map(([x, y, r], i) => (
          <path
            key={i}
            className="dev-art__star"
            d={star(x, y, r)}
            style={{ '--i': i, transformOrigin: `${x}px ${y}px` } as React.CSSProperties}
          />
        ))}
      </svg>
    </span>
  )
}
