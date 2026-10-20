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
 *
 * Если вкладки лежат в прокручиваемой ленте, передайте её в scrollerRef:
 * выбранная вкладка будет подъезжать к центру ленты, иначе на узком
 * экране она могла остаться за краем.
 */
export function useTabIndicator(
  activeKey: string | number,
  ready: unknown = true,
  scrollerRef?: { current: HTMLElement | null },
) {
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

  // Подтягиваем выбранную вкладку к центру ленты. Двигаем scrollLeft самой
  // ленты, а не scrollIntoView: тот заодно прокрутил бы и страницу по вертикали.
  useEffect(() => {
    const scroller = scrollerRef?.current
    const tab = tabRefs.current[String(activeKey)]
    if (!scroller || !tab || !indicator.width) return
    const max = scroller.scrollWidth - scroller.clientWidth
    if (max <= 0) return
    // положение вкладки внутри прокручиваемого содержимого ленты; если лента
    // сама позиционирована, offsetLeft вкладки уже отсчитан от неё
    const tabLeft = tab.offsetParent === scroller
      ? tab.offsetLeft
      : tab.offsetLeft - scroller.offsetLeft - scroller.clientLeft
    const target = tabLeft + tab.offsetWidth / 2 - scroller.clientWidth / 2
    scroller.scrollTo({ left: Math.max(0, Math.min(target, max)), behavior: 'smooth' })
  }, [indicator, activeKey, scrollerRef])

  return { containerRef, registerTab, indicator }
}
