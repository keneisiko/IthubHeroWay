/**
 * Общее для нашивок: типы ответа API, подписи категорий и наклон
 * эмблемы за курсором. Используют страница нашивок и профиль.
 */

export interface Badge {
  code: string
  title: string
  description: string
  category: string
  rarity: string
  reward_coins: number
}

export interface EarnedBadge {
  id: number
  badge: Badge
  acquired_at: string
  is_pinned?: boolean
}

// Категории приходят с бэка кодами (BadgeCategory), подписи — здесь.
export const CATEGORY_LABELS: Record<string, string> = {
  progress: 'Прогресс',
  academic: 'Учёба',
  social: 'Сообщество',
  special: 'Особые',
}

const canHover = () => window.matchMedia('(hover: hover) and (pointer: fine)').matches

/** Наклон эмблемы за курсором: только CSS-переменные, без перерисовки React. */
export function tiltHandlers() {
  return {
    onPointerMove: (e: React.PointerEvent<HTMLElement>) => {
      if (e.pointerType !== 'mouse' || !canHover()) return
      const el = e.currentTarget
      const rect = el.getBoundingClientRect()
      const x = (e.clientX - rect.left) / rect.width - 0.5
      const y = (e.clientY - rect.top) / rect.height - 0.5
      el.style.setProperty('--tilt-x', `${(-y * 14).toFixed(2)}deg`)
      el.style.setProperty('--tilt-y', `${(x * 18).toFixed(2)}deg`)
    },
    onPointerLeave: (e: React.PointerEvent<HTMLElement>) => {
      e.currentTarget.style.setProperty('--tilt-x', '0deg')
      e.currentTarget.style.setProperty('--tilt-y', '0deg')
    },
  }
}
