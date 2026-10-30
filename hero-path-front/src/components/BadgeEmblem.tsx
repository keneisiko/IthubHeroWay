import { useId, useMemo } from 'react'

/**
 * Нашивка как предмет: пришитый патч с прострочкой по краю.
 *
 * Форма говорит о редкости ещё до подписи: обычная — квадрат (знак IThub),
 * редкая — щит, эпическая — шестигранник, легендарная — восьмигранник.
 * Цвета — системные цвета макета (те же, что у мест в рейтинге).
 *
 * В центре — пиксельный знак 5×5, симметричный, выведенный из кода
 * нашивки: у каждой свой, и он не меняется между заходами.
 */

type Rarity = 'common' | 'rare' | 'epic' | 'legendary'

const SHAPES: Record<Rarity, string> = {
  common: 'M20 4H80Q96 4 96 20V80Q96 96 80 96H20Q4 96 4 80V20Q4 4 20 4Z',
  rare: 'M50 3L93 15V51C93 74 75 89 50 97C25 89 7 74 7 51V15Z',
  epic: 'M50 3L91 26.5V73.5L50 97L9 73.5V26.5Z',
  legendary: 'M31 4H69L96 31V69L69 96H31L4 69V31Z',
}

const PALETTE: Record<Rarity, { fill: string; ink: string; stitch: string }> = {
  common: { fill: '#9a33f4', ink: '#f5f5f5', stitch: 'rgba(245, 245, 245, 0.75)' },
  rare: { fill: '#38dddd', ink: '#121212', stitch: 'rgba(18, 18, 18, 0.45)' },
  epic: { fill: '#ff00ee', ink: '#f5f5f5', stitch: 'rgba(245, 245, 245, 0.8)' },
  legendary: { fill: '#ffd900', ink: '#121212', stitch: 'rgba(18, 18, 18, 0.5)' },
}

const LOCKED = { fill: '#e6e6e6', ink: '#c4c4c4', stitch: '#c9c9c9' }

// Сезонные нашивки рисуются своим знаком и цветом, а не знаком из кода:
// «Самый страшный» — рожица тыквенного фонаря на оранжевом.
const SPECIAL: Record<string, { cells: boolean[][]; colors: typeof LOCKED }> = {
  'halloween-scariest': {
    cells: ['X...X', 'XX.XX', '..X..', 'X.X.X', '.XXX.'].map((r) => Array.from(r, (ch) => ch === 'X')),
    colors: { fill: '#ff7a1a', ink: '#1a0f2e', stitch: 'rgba(26, 15, 46, 0.55)' },
  },
}

function hash(text: string): number {
  let h = 2166136261
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

/** 15 бит на левую половину и середину, правая — зеркало. */
function sigil(code: string): boolean[][] {
  let bits = hash(code)
  const grid: boolean[][] = []
  let on = 0
  for (let r = 0; r < 5; r++) {
    const row: boolean[] = []
    for (let c = 0; c < 3; c++) {
      const v = (bits & 1) === 1
      bits >>>= 1
      row.push(v)
      if (v) on += c === 2 ? 1 : 2
    }
    grid.push([row[0], row[1], row[2], row[1], row[0]])
  }
  // слишком пустой знак не читается — добавляем сердцевину
  if (on < 7) {
    grid[1][2] = grid[2][2] = grid[3][2] = true
    grid[2][1] = grid[2][3] = true
  }
  return grid
}

function normalizeRarity(rarity: string): Rarity {
  return (rarity in SHAPES ? rarity : 'common') as Rarity
}

interface Props {
  code: string
  rarity: string
  locked?: boolean
  size?: number
  className?: string
}

export default function BadgeEmblem({ code, rarity, locked = false, size = 72, className = '' }: Props) {
  const r = normalizeRarity(rarity)
  const special = SPECIAL[code]
  const colors = locked ? LOCKED : special?.colors ?? PALETTE[r]
  const cells = useMemo(() => SPECIAL[code]?.cells ?? sigil(code), [code])
  const clipId = `emblem-${useId().replace(/:/g, '')}`
  const shape = SHAPES[r]
  const cell = 8
  const gap = 1.5
  const span = cell * 5 + gap * 4
  const ox = 50 - span / 2
  const oy = 50 - span / 2 + (r === 'rare' ? -2 : 0)

  return (
    <svg
      className={`emblem emblem--${r}${locked ? ' emblem--locked' : ''} ${className}`}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      aria-hidden="true"
    >
      <path d={shape} fill={colors.fill} stroke="#121212" strokeWidth={locked ? 0 : 4} strokeLinejoin="round" />
      {locked && (
        <path d={shape} fill="none" stroke="#bdbdbd" strokeWidth="3" strokeDasharray="6 5" strokeLinejoin="round" />
      )}
      <path
        d={shape}
        fill="none"
        stroke={colors.stitch}
        strokeWidth="2"
        strokeDasharray="4 3.2"
        strokeLinecap="round"
        transform="translate(50 50) scale(0.8) translate(-50 -50)"
        vectorEffect="non-scaling-stroke"
      />
      <g fill={colors.ink}>
        {cells.flatMap((row, ri) =>
          row.map((v, ci) =>
            v ? (
              <rect
                key={`${ri}-${ci}`}
                x={ox + ci * (cell + gap)}
                y={oy + ri * (cell + gap)}
                width={cell}
                height={cell}
              />
            ) : null,
          ),
        )}
      </g>
      {!locked && (
        <>
          <clipPath id={clipId}>
            <path d={shape} />
          </clipPath>
          <g clipPath={`url(#${clipId})`}>
            <rect className="emblem__shine" x="-70" y="-20" width="34" height="140" />
          </g>
        </>
      )}
    </svg>
  )
}
