import { useCallback, useEffect, useRef, useState } from 'react'

export interface TabIndicator {
  left: number
  width: number
}

/**
 * Положение «пилюли» под активным табом.
 *
 * Меряем сам таб через offset-величины: getBoundingClientRect возвращает
 * размеры вместе с трансформами, а блоки появляются с анимацией масштаба —
 * замер попадал бы в её середину и пилюля вставала мимо надписи.
 *
 * Пересчитываем при изменении размеров и после загрузки шрифтов: пока
 * гарнитура не подгрузилась, ширина текста другая.
 */
export function useTabIndicator(activeKey: string | number, ready: unknown = true) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const tabRefs = useRef<Record<string, HTMLElement | null>>({})
  const [indicator, setIndicator] = useState<TabIndicator>({ left: 0, width: 0 })

  const registerTab = useCallback(
    (key: string | number) => (el: HTMLElement | null) => {
      tabRefs.current[String(key)] = el
    },
    [],
  )

  const update = useCallback(() => {
    const container = containerRef.current
    const tab = tabRefs.current[String(activeKey)]
    if (!container || !tab) return
    setIndicator({ left: tab.offsetLeft - container.offsetLeft, width: tab.offsetWidth })
  }, [activeKey])

  useEffect(() => {
    update()
    const container = containerRef.current
    if (!container) return
    const observer = new ResizeObserver(update)
    observer.observe(container)
    Object.values(tabRefs.current).forEach((el) => el && observer.observe(el))
    document.fonts?.ready.then(update)
    return () => observer.disconnect()
  }, [update, ready])

  return { containerRef, registerTab, indicator }
}
