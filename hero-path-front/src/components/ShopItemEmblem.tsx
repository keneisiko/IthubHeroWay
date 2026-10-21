import { useId } from 'react'

/**
 * Иконка товара магазина в стилистике нашивок (BadgeEmblem): пришитый
 * патч с прострочкой и пиксельным знаком по центру.
 *
 * Форма и знак говорят о типе товара ещё до подписи: рамка — квадрат с
 * контуром, свечение — шестигранник с искрой, баннер — вымпел, буст —
 * восьмигранник с молнией, услуга — щит с репликой, мерч — круглая
 * наклейка с кружкой. Цвет — по конкретному коду (золото, неон, пламя,
 * радуга…), неизвестный код получает палитру своего типа.
 */

export type ItemKind = 'frame' | 'glow' | 'banner' | 'boost' | 'service' | 'merch'

const SHAPES: Record<ItemKind, string> = {
  frame: 'M20 4H80Q96 4 96 20V80Q96 96 80 96H20Q4 96 4 80V20Q4 4 20 4Z',
  glow: 'M50 3L91 26.5V73.5L50 97L9 73.5V26.5Z',
  banner: 'M5 12H95L81 50L95 88H5Z',
  boost: 'M31 4H69L96 31V69L69 96H31L4 69V31Z',
  service: 'M50 3L93 15V51C93 74 75 89 50 97C25 89 7 74 7 51V15Z',
  merch: 'M50 4A46 46 0 1 1 49.99 4Z',
}

// Пиксельные знаки. `#` — залитая клетка, `o` — клетка акцента (светлая).
const GLYPHS: Record<ItemKind, string[]> = {
  frame: [
    '#######',
    '#.....#',
    '#..#..#',
    '#.###.#',
    '#.#.#.#',
    '#.....#',
    '#######',
  ],
  glow: [
    '...#...',
    '...#...',
    '..###..',
    '#######',
    '..###..',
    '...#...',
    '...#...',
  ],
  banner: [
    '#......',
    '######.',
    '#######',
    '#o#o#o.',
    '#######',
    '#......',
    '#......',
  ],
  boost: [
    '....##.',
    '...##..',
    '..##...',
    '.#####.',
    '...##..',
    '..##...',
    '.##....',
  ],
  service: [
    '.#####.',
    '#.....#',
    '#.#.#.#',
    '#.....#',
    '.#####.',
    '..##...',
    '...#...',
  ],
  merch: [
    '.#.#...',
    '.......',
    '#####..',
    '#...###',
    '#...#.#',
    '#...###',
    '#####..',
  ],
}

interface Palette {
  fill: string
  /** Два цвета и больше — диагональный градиент вместо плоской заливки. */
  gradient?: string[]
  ink: string
  accent: string
  stitch: string
}

const LIGHT_INK = '#f5f5f5'
const DARK_INK = '#121212'
const STITCH_LIGHT = 'rgba(245, 245, 245, 0.8)'
const STITCH_DARK = 'rgba(18, 18, 18, 0.5)'

const KIND_PALETTE: Record<ItemKind, Palette> = {
  frame: { fill: '#9a33f4', ink: LIGHT_INK, accent: '#ffd900', stitch: STITCH_LIGHT },
  glow: { fill: '#c58bff', ink: DARK_INK, accent: LIGHT_INK, stitch: STITCH_DARK },
  banner: { fill: '#38dddd', ink: DARK_INK, accent: LIGHT_INK, stitch: STITCH_DARK },
  boost: { fill: '#121212', ink: '#ffd900', accent: LIGHT_INK, stitch: 'rgba(255, 217, 0, 0.7)' },
  service: { fill: '#38dddd', ink: DARK_INK, accent: LIGHT_INK, stitch: STITCH_DARK },
  merch: { fill: '#f5f5f5', ink: DARK_INK, accent: '#9a33f4', stitch: STITCH_DARK },
}

// вариации по конкретному коду — поверх палитры типа
const CODE_PALETTE: Record<string, Partial<Palette>> = {
  'cosmetic-frame-gold': { fill: '#ffd900', ink: DARK_INK, accent: LIGHT_INK, stitch: STITCH_DARK },
  'cosmetic-frame-neon': { fill: '#0b1a1a', ink: '#2bffb4', accent: '#38dddd', stitch: 'rgba(43, 255, 180, 0.7)' },
  'cosmetic-frame-flame': { fill: '#ff5a1f', ink: '#fff3b0', accent: '#ffd900', stitch: 'rgba(255, 243, 176, 0.8)' },
  'cosmetic-glow-gold': { fill: '#ffd900', ink: DARK_INK, accent: LIGHT_INK, stitch: STITCH_DARK },
  'cosmetic-glow-rainbow': {
    fill: '#ff00ee',
    gradient: ['#ff3d6e', '#ffd900', '#2bffb4', '#38dddd', '#9a33f4'],
    ink: LIGHT_INK,
    accent: DARK_INK,
    stitch: STITCH_LIGHT,
  },
  'banner-night': { fill: '#1d1b4b', ink: '#38dddd', accent: '#ffd900', stitch: 'rgba(56, 221, 221, 0.6)' },
  'banner-sunset': { fill: '#ff5a1f', gradient: ['#ffd900', '#ff5a1f', '#ff00ee'], ink: LIGHT_INK, accent: DARK_INK, stitch: STITCH_LIGHT },
  'banner-matrix': { fill: '#0b1a0f', ink: '#2bff6a', accent: '#b6ffcb', stitch: 'rgba(43, 255, 106, 0.6)' },
  'banner-pixels': { fill: '#ff00ee', ink: LIGHT_INK, accent: '#ffd900', stitch: STITCH_LIGHT },
  'banner-aurora': { fill: '#38dddd', gradient: ['#2bffb4', '#38dddd', '#9a33f4'], ink: DARK_INK, accent: LIGHT_INK, stitch: STITCH_DARK },
  'banner-gold': { fill: '#ffd900', ink: DARK_INK, accent: LIGHT_INK, stitch: STITCH_DARK },
}

// «×2» для буста: мелкий знак в правом нижнем углу
const BOOST_X2 = [
  '#.#.###',
  '.#..#.#',
  '#.#...#',
  '......#',
  '....###',
]

/** Тип иконки: по слоту, иначе по коду, иначе по типу товара из API. */
function itemKind(code: string, slot?: string | null, itemType?: string | null): ItemKind {
  switch (slot) {
    case 'avatar_frame': return 'frame'
    case 'badge_glow': return 'glow'
    case 'profile_banner': return 'banner'
    case 'boost': return 'boost'
  }
  if (/frame/.test(code)) return 'frame'
  if (/glow/.test(code)) return 'glow'
  if (/^banner-/.test(code)) return 'banner'
  if (/^boost-/.test(code) || itemType === 'boost') return 'boost'
  if (itemType === 'service') return 'service'
  if (itemType === 'other') return 'merch'
  return 'service'
}

interface Props {
  code: string
  slot?: string | null
  itemType?: string | null
  size?: number
  className?: string
}

export default function ShopItemEmblem({ code, slot, itemType, size = 72, className = '' }: Props) {
  const kind = itemKind(code, slot, itemType)
  const palette = { ...KIND_PALETTE[kind], ...CODE_PALETTE[code] }
  const shape = SHAPES[kind]
  const glyph = GLYPHS[kind]
  const gradId = `item-grad-${useId().replace(/:/g, '')}`
  const stops = palette.gradient ?? []
  const cell = 8
  const gap = 1.5
  const span = cell * 7 + gap * 6
  const ox = 50 - span / 2
  const oy = 50 - span / 2

  // «×2» только у буста на удвоение: знак сдвигается, освобождая угол
  const showX2 = kind === 'boost' && /x2/.test(code)
  const x2Cell = 3.4
  const x2Gap = 0.8
  const x2W = x2Cell * 7 + x2Gap * 6

  return (
    <svg
      className={`emblem emblem--item emblem--item-${kind} ${className}`}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      aria-hidden="true"
    >
      {stops.length > 1 && (
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
            {stops.map((color, i) => (
              <stop key={`${color}-${i}`} offset={`${(i / (stops.length - 1)) * 100}%`} stopColor={color} />
            ))}
          </linearGradient>
        </defs>
      )}
      <path
        d={shape}
        fill={stops.length > 1 ? `url(#${gradId})` : palette.fill}
        stroke="#121212"
        strokeWidth={4}
        strokeLinejoin="round"
      />
      <path
        d={shape}
        fill="none"
        stroke={palette.stitch}
        strokeWidth="2"
        strokeDasharray="4 3.2"
        strokeLinecap="round"
        transform="translate(50 50) scale(0.8) translate(-50 -50)"
        vectorEffect="non-scaling-stroke"
      />
      <g transform={showX2 ? 'translate(-6 -8)' : undefined}>
        {glyph.flatMap((row, ri) =>
          Array.from(row).map((ch, ci) => (ch === '.' ? null : (
            <rect
              key={`${ri}-${ci}`}
              x={ox + ci * (cell + gap)}
              y={oy + ri * (cell + gap)}
              width={cell}
              height={cell}
              fill={ch === 'o' ? palette.accent : palette.ink}
            />
          ))),
        )}
      </g>
      {showX2 && (
        <g fill={palette.accent} transform={`translate(${74 - x2W / 2} 66)`}>
          {BOOST_X2.flatMap((row, ri) =>
            Array.from(row).map((ch, ci) => (ch === '#' ? (
              <rect
                key={`x-${ri}-${ci}`}
                x={ci * (x2Cell + x2Gap)}
                y={ri * (x2Cell + x2Gap)}
                width={x2Cell}
                height={x2Cell}
              />
            ) : null)),
          )}
        </g>
      )}
    </svg>
  )
}
