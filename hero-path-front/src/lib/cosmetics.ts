/**
 * Косметика из магазина. Бэкенд отдаёт применённые покупки как
 * «тип товара → код» (applied_items), интерфейс по коду решает, что
 * рисовать.
 */

export const AVATAR_FRAME = 'cosmetic-avatar-frame'
export const BADGE_GLOW = 'cosmetic-badge-glow'

export type AppliedItems = Partial<Record<string, string>>

export const hasFrame = (items?: AppliedItems | null) => items?.cosmetic === AVATAR_FRAME
export const hasGlow = (items?: AppliedItems | null) => items?.cosmetic === BADGE_GLOW

// где видно действие товара — подсказка в «Моих покупках»
export const COSMETIC_HINTS: Record<string, string> = {
  [AVATAR_FRAME]: 'Рамка видна у аватара в шапке, профиле и рейтинге',
  [BADGE_GLOW]: 'Закреплённые нашивки в профиле светятся',
}
