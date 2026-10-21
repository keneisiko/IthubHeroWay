import { useEffect, useRef, useState } from 'react'

interface PixelTextProps {
  text: string
  className?: string
}

/**
 * Заголовок проявляется по буквам: на месте каждой сначала вспыхивает
 * пиксель цвета текста, затем встаёт сама буква. Запускается, когда
 * заголовок доезжает до экрана.
 */
export default function PixelText({ text, className }: PixelTextProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        setShown(true)
        io.disconnect()
      }
    }, { threshold: 0.6 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  let index = 0
  const words = text.split(' ')

  return (
    <span ref={ref} className={`ptext${shown ? ' ptext--in' : ''}${className ? ` ${className}` : ''}`}>
      <span className="visually-hidden">{text}</span>
      <span aria-hidden="true">
        {words.map((word, w) => (
          <span key={w}>
            <span className="ptext__word">
              {Array.from(word, (ch, c) => (
                <span key={c} className="ptext__ch" style={{ '--i': index++ } as React.CSSProperties}>{ch}</span>
              ))}
            </span>
            {w < words.length - 1 ? ' ' : null}
          </span>
        ))}
      </span>
    </span>
  )
}
