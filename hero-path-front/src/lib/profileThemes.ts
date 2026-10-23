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
