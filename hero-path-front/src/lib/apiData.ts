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
  if (!endAt) return '—'
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
