import { useState } from 'react'
import DevFrameArt from './DevFrameArt'

interface AvatarProps {
  src?: string | null
  name: string
  className?: string
  /** Рамка из API (avatar_frame): 'purple' из магазина, 'developer' от нашивки. */
  frame?: string | null
}

const TONES = ['light', 'purple', 'dark'] as const

// путь из API бывает полным адресом, бывает относительным — без
// ведущей косой браузер искал бы файл относительно текущей страницы
function avatarUrl(src?: string | null): string | null {
  if (!src) return null
  if (/^(https?:|blob:|data:)/.test(src)) return src
  return src.startsWith('/') ? src : `/${src}`
}

// две буквы, только если позывной из двух слов; одно слово — одна
// крупная буква, так знак читается и в квадрате на 40px
function initialsOf(name: string): string {
  const words = name.trim().split(/[\s_\-.@]+/).filter(Boolean)
  const first = (word: string) => Array.from(word).find((ch) => /[\p{L}\d]/u.test(ch)) ?? ''
  if (words.length >= 2) return (first(words[0]) + first(words[1])).toUpperCase()
  return first(words[0] ?? '').toUpperCase() || '?'
}

function toneOf(name: string): (typeof TONES)[number] {
  let hash = 0
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) | 0
  return TONES[Math.abs(hash) % TONES.length]
}

/**
 * Аватар человека. Пока фото грузится — под ним уже стоит знак с
 * буквами, фото проявляется поверх. Не загрузилось (битый файл, нет
 * доступа) — остаётся знак, а не значок сломанной картинки.
 * Фото обрезает внутренний слой, поэтому рамка может выходить за край.
 */
export default function Avatar({ src, name, className, frame }: AvatarProps) {
  const url = avatarUrl(src)
  const [loaded, setLoaded] = useState<string | null>(null)
  const [failed, setFailed] = useState<string | null>(null)
  const showImage = url !== null && failed !== url

  return (
    <span
      className={`avatar${className ? ` ${className}` : ''}${showImage && loaded === url ? ' avatar--photo' : ''}${frame ? ` avatar--frame-${frame}` : ''}`}
      data-tone={toneOf(name)}
    >
      <span className="avatar__clip">
        <span className="avatar__initials" aria-hidden="true">{initialsOf(name)}</span>
        {showImage && (
          <img
            key={url}
            className="avatar__img"
            src={url}
            alt=""
            loading="lazy"
            decoding="async"
            onLoad={() => setLoaded(url)}
            onError={() => setFailed(url)}
          />
        )}
      </span>
      {frame === 'developer' && <DevFrameArt />}
    </span>
  )
}
