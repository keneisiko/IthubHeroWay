import { useEffect, useState } from 'react'

/**
 * Кнопка «наверх» на длинных страницах: лидеры, нашивки, квесты на
 * телефоне уходят на несколько экранов вниз. Появляется, когда
 * прокрутил больше экрана.
 */
export default function ScrollTopButton() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    let frame = 0
    const onScroll = () => {
      if (frame) return
      frame = requestAnimationFrame(() => {
        frame = 0
        setVisible(window.scrollY > window.innerHeight)
      })
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      cancelAnimationFrame(frame)
    }
  }, [])

  const toTop = () => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' })
  }

  return (
    <button
      type="button"
      className={`scroll-top${visible ? ' scroll-top--visible' : ''}`}
      onClick={toTop}
      aria-label="Наверх"
      tabIndex={visible ? 0 : -1}
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M6 14l6-6 6 6" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  )
}
