/**
 * Косметика из магазина. Бэкенд отдаёт применённые покупки как
 * «слот → код товара» (applied_items), интерфейс по коду решает, что
 * рисовать. В одном слоте одновременно надета одна вещь.
 */

export const AVATAR_FRAME = 'cosmetic-avatar-frame'
export const BADGE_GLOW = 'cosmetic-badge-glow'
export const BOOST_QUEST_X2 = 'boost-quest-x2'

export type CosmeticSlot = 'avatar_frame' | 'badge_glow' | 'profile_banner'
export type ShopSlot = CosmeticSlot | 'boost'

// Ключи слотов приходят от бэкенда; лишние (старый `cosmetic`) игнорируем.
export type AppliedItems = Partial<Record<string, string>>

export interface ActiveBoost {
  code: string
  title: string
}

/** Слоты косметики, которые можно надеть/снять (буст не «надевается»). */
export const isCosmeticSlot = (slot?: string | null): slot is CosmeticSlot => (
  slot === 'avatar_frame' || slot === 'badge_glow' || slot === 'profile_banner'
)

// код товара → значение avatar_frame, по которому Avatar рисует рамку
export const FRAME_BY_CODE: Record<string, string> = {
  [AVATAR_FRAME]: 'purple',
  'cosmetic-frame-gold': 'gold',
  'cosmetic-frame-neon': 'neon',
  'cosmetic-frame-flame': 'flame',
}

// код товара → вариант цвета свечения (класс ach--glow-<вариант>)
export const GLOW_BY_CODE: Record<string, string> = {
  [BADGE_GLOW]: 'purple',
  'cosmetic-glow-gold': 'gold',
  'cosmetic-glow-rainbow': 'rainbow',
}

// код баннера → вариант оформления (класс banner--<вариант>)
export const BANNER_BY_CODE: Record<string, string> = {
  'banner-night': 'night',
  'banner-sunset': 'sunset',
  'banner-matrix': 'matrix',
  'banner-pixels': 'pixels',
  'banner-aurora': 'aurora',
  'banner-gold': 'gold',
}


/** Вариант свечения для класса; неизвестный код — фирменное фиолетовое. */
export const glowVariant = (items?: AppliedItems | null): string | null => {
  const code = items?.badge_glow
  return code ? (GLOW_BY_CODE[code] ?? 'purple') : null
}

/** Вариант баннера профиля или null, если баннер не надет/код неизвестен. */
export const bannerVariant = (items?: AppliedItems | null): string | null => {
  const code = items?.profile_banner
  return code ? (BANNER_BY_CODE[code] ?? null) : null
}

/** Где видно действие товара — подсказка в «Моих покупках». */
export const SLOT_HINTS: Record<CosmeticSlot, string> = {
  avatar_frame: 'Рамка видна у аватара в шапке, профиле и рейтинге',
  badge_glow: 'Закреплённые нашивки в профиле светятся',
  profile_banner: 'Баннер заменяет фон шапки вашего профиля',
}

export const SLOT_LABELS: Record<CosmeticSlot, string> = {
  avatar_frame: 'Рамка',
  badge_glow: 'Свечение',
  profile_banner: 'Баннер',
}

/**
 * Слот товара. Бэкенд присылает его полем `slot`; если поля нет (старый
 * ответ), слот выводится из кода по известным префиксам, чтобы кнопки
 * «Надеть» не пропадали. Незнакомый код слота не получает.
 */
export function slotOfItem(code: string, slot?: string | null): string {
  if (slot) return slot
  if (code === AVATAR_FRAME || code.startsWith('cosmetic-frame-')) return 'avatar_frame'
  if (code === BADGE_GLOW || code.startsWith('cosmetic-glow-')) return 'badge_glow'
  if (code.startsWith('banner-')) return 'profile_banner'
  if (code.startsWith('boost-')) return 'boost'
  return ''
}
