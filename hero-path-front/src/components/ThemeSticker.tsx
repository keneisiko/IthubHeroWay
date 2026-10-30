import { useId } from 'react'
import { PUMPKIN } from '../lib/pixelSprites'
import type { FrameThemeSticker } from '../lib/profileThemes'

const PUMPKIN_COLORS: Record<string, string> = {
  s: '#4f8a3a',
  o: '#ff7a1a',
  d: '#b8480c',
  y: '#ffd23f',
}

/** Чёрная дыра: тень горизонта, диск в наклоне, пара звёзд — как рамка космоса. */
function BlackHole() {
  const glow = `bh-${useId().replace(/:/g, '')}`
  return (
    <svg viewBox="0 0 64 64" className="theme-sticker__art">
      <circle cx="32" cy="32" r="30" fill="#050507" />
      <defs>
        <filter id={glow} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.2" />
        </filter>
      </defs>
      <g transform="rotate(-12 32 32)">
        {/* дальняя сторона диска, согнутая гравитацией в яркое кольцо вокруг тени */}
        <circle cx="32" cy="32" r="17.5" fill="none" stroke="#fff" strokeWidth="6" opacity="0.55" filter={`url(#${glow})`} />
        <circle cx="32" cy="32" r="17" fill="none" stroke="#e9e9ef" strokeWidth="4.6" />
        <path d="M3 33 A29 3.6 0 0 1 61 33" fill="none" stroke="#7d7d8a" strokeWidth="2" />
        <circle cx="32" cy="32" r="14.6" fill="#000" />
        {/* ближняя сторона диска проходит перед тенью */}
        <path d="M3 33 A29 3.6 0 0 0 61 33" fill="none" stroke="#fff" strokeWidth="2.8" />
      </g>
      <path d="M50 10 l1.4 3.6 3.6 1.4 -3.6 1.4 -1.4 3.6 -1.4 -3.6 -3.6 -1.4 3.6 -1.4 z" fill="#f4f4f7" />
      <circle cx="15" cy="50" r="1.4" fill="#f4f4f7" />
    </svg>
  )
}

/** Пиксельная тыква-фонарь — та же, что горит в рамке-склепе. */
function Pumpkin() {
  return (
    <svg viewBox="-1 -1 13 11" className="theme-sticker__art" shapeRendering="crispEdges">
      <rect x="-1" y="-1" width="13" height="11" rx="2.5" fill="#1a0f2e" />
      {PUMPKIN.flatMap((row, y) =>
        Array.from(row).map((ch, x) => (ch === '.' ? null : <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill={PUMPKIN_COLORS[ch]} />)),
      )}
    </svg>
  )
}

/**
 * Стикер темы профиля: наклейка с белой высечкой по контуру, чуть
 * наискосок. Наклеивается на эмблему нашивки и стоит в её описании.
 */
export default function ThemeSticker({ kind, className = '' }: { kind: FrameThemeSticker; className?: string }) {
  return (
    <span className={`theme-sticker theme-sticker--${kind} ${className}`} aria-hidden="true">
      {kind === 'blackhole' ? <BlackHole /> : <Pumpkin />}
    </span>
  )
}
