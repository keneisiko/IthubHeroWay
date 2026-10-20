/**
 * Русское склонение по числу: plural(21, ['день', 'дня', 'дней']) → 'день'.
 *
 * Простая проверка «2–4 → вторая форма» врёт на 12–14 и на 22, 23, 24:
 * получалось «21 дней» и «22 дней».
 */
export function plural(count: number, forms: [string, string, string]): string {
  const n = Math.abs(count) % 100
  if (n >= 11 && n <= 14) return forms[2]
  const last = n % 10
  if (last === 1) return forms[0]
  if (last >= 2 && last <= 4) return forms[1]
  return forms[2]
}
