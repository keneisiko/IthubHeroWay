/** Распаковка ответа DRF: массив или paginated `{ results: [] }`. */
export function unwrapList<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object' && Array.isArray((data as { results?: T[] }).results)) {
    return (data as { results: T[] }).results
  }
  return []
}

const QUEST_TYPE_LABELS: Record<string, string> = {
  daily: 'Ежедневный',
  weekly: 'Еженедельный',
  event: 'Событийный',
  long: 'Долгий',
  self_report: 'Самоотчёт',
  mixed: 'Смешанный',
}

export function questTypeLabel(type: string): string {
  return QUEST_TYPE_LABELS[type] ?? type
}

export function formatReward(coins: number, ratingDelta?: number): string {
  const parts: string[] = []
  if (coins) parts.push(`${coins} монет`)
  if (ratingDelta) parts.push(`+${ratingDelta} рейтинг`)
  return parts.join(', ') || '—'
}

export function progressPercent(value: number): number {
  if (value <= 1) return Math.round(Math.max(0, value) * 100)
  return Math.round(Math.min(100, Math.max(0, value)))
}

export function daysLeft(endAt: string | null | undefined): string {
  // Пустая строка, а не прочерк: у квеста без срока «Осталось —» читается
  // как поломка. Подпись «Без срока» подставляет вызывающий код.
  if (!endAt) return ''
  const diff = new Date(endAt).getTime() - Date.now()
  if (diff <= 0) return '0 дн.'
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24))
  return `${days} дн.`
}

export function formatDateRu(iso: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

/** «14 октября» — для близких дат, где год только мешает. */
export function formatDayMonth(iso: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' }).format(new Date(iso))
  } catch {
    return iso
  }
}

export function formatDateTimeRu(iso: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

export const SHOP_TAB_TYPES = ['cosmetic', 'boost', 'other', 'service'] as const

export const RARITY_LABELS: Record<string, string> = {
  common: 'Обычный',
  rare: 'Редкий',
  epic: 'Эпический',
  legendary: 'Легендарный',
}

// Часть ответов бэкенда — по-английски. Переводим то, что знаем.
const KNOWN_DETAILS: Record<string, string> = {
  'Insufficient coins.': 'Не хватает монет',
  'Item is not available yet.': 'Товар пока недоступен',
  'Item is no longer available.': 'Товар больше недоступен',
  'Cannot send respect to yourself.': 'Себе респект не отправить',
  'Weekly respect limit reached.': 'Респекты на эту неделю закончились',
  'You can respect this user again in two weeks.': 'Этому студенту снова можно будет отправить респект через две недели',
  'Cannot duel yourself.': 'Себя на дуэль не вызвать',
  'You already have an active duel.': 'У тебя уже есть активная дуэль',
  'Opponent already has an active duel.': 'У соперника уже есть активная дуэль',
  'Cannot mentor yourself.': 'Себе наставником не стать',
  'You are already in a squad.': 'Ты уже состоишь в отряде',
  'Squad not found.': 'Отряд с таким кодом не найден',
  'Squad is full.': 'В отряде нет свободных мест',
  'Only agents can create squads.': 'Отряды создают только студенты',
  'Could not allocate a squad code, try again.': 'Не получилось выдать код отряда, попробуй ещё раз',
  'Quest does not accept self-reports.': 'Этот квест не принимает самоотчёты',
  'Quest is not started yet.': 'Квест ещё не начался',
  'Quest is already ended.': 'Срок квеста уже истёк',
  'Quest is already completed.': 'Квест уже выполнен',
  'Too frequent. Try again later.': 'Слишком часто, попробуй чуть позже',
  'Progress for this quest is updated automatically.': 'Прогресс этого квеста считается автоматически',
}

// Ответы с числом внутри: лимиты берутся из настроек бэкенда.
const KNOWN_PATTERNS: [RegExp, (n: string) => string][] = [
  [/^Rating difference must be (\d+) or less\.$/, (n) => `Разница рейтинга должна быть не больше ${n}`],
  [/^Mentee limit reached \((\d+)\)\.$/, (n) => `Подшефных уже ${n} — это максимум`],
  [/^Daily self-report limit reached \((\d+)\/day\)\.$/, (n) => `Самоотчётов на сегодня больше нельзя: лимит ${n}`],
]

/**
 * Текст ошибки запроса для пользователя.
 *
 * Бэкенд объясняет отказ в detail («Срок квеста уже истёк», «Квест уже
 * выполнен»), а страницы показывали безликое «Ошибка». Русскую причину
 * отдаём как есть, известную английскую переводим, остальное — fallback.
 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail !== 'string' || !detail.trim()) return fallback
  if (KNOWN_DETAILS[detail]) return KNOWN_DETAILS[detail]
  for (const [pattern, translate] of KNOWN_PATTERNS) {
    const match = detail.match(pattern)
    if (match) return translate(match[1])
  }
  return /[а-яё]/i.test(detail) ? detail : fallback
}
