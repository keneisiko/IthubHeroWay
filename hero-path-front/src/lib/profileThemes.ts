/**
 * Личные оформления профиля. Закреплены за аккаунтом: не покупаются в
 * магазине, не зависят от нашивок и видны всем, кто открыл профиль.
 * Личная тема сильнее темы нашивки «Разработчик».
 */
export type PersonalTheme = 'film'

const PERSONAL_THEMES: Record<string, PersonalTheme> = {
  'haupadk26-866ebe4f': 'film',
}

export function personalTheme(username?: string | null): PersonalTheme | null {
  return (username && PERSONAL_THEMES[username]) || null
}

/**
 * Темы, которые дают нашивки (поле avatar_frame у нашивки): работают, пока
 * нашивка закреплена в профиле. Описание показывается в шторке нашивки.
 */
export type FrameThemeSticker = 'blackhole' | 'pumpkin'

export interface FrameTheme {
  name: string
  text: string
  sticker: FrameThemeSticker
}

export const FRAME_THEMES: Record<string, FrameTheme> = {
  developer: {
    name: 'Горизонт событий',
    text: 'Профиль уходит в чёрно-белый космос: звёздное небо с чёрной дырой, рамка из космической туши, планеты на карте пути.',
    sticker: 'blackhole',
  },
  halloween: {
    name: 'Ночь на кладбище',
    text: 'Профиль превращается в пиксельную хэллоуинскую ночь: луна, ведьма на метле, вороны, тыквы на карте пути и рамка-склеп со свечой и вороном.',
    sticker: 'pumpkin',
  },
}
