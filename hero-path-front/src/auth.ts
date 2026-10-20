export function isAuthenticated(): boolean {
  return Boolean(localStorage.getItem('access_token'))
}

export function clearAuthTokens(): void {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export function isAuthApiPath(url = ''): boolean {
  return (
    url.includes('/auth/login') ||
    url.includes('/auth/jwt/') ||
    url.includes('/auth/refresh')
  )
}

export function extractLoginError(error: unknown): string {
  const err = error as { response?: { status?: number; data?: Record<string, unknown> } }
  const data = err.response?.data
  if (!data) {
    return 'Ошибка соединения. Проверьте, что бэкенд запущен.'
  }
  // Русскую причину показываем как есть. Английскую («Invalid
  // email/password.») — нет: на отказ во входе понятнее своя фраза.
  const russian = (value: unknown) =>
    typeof value === 'string' && /[а-яё]/i.test(value) ? value : null
  const detail = data.detail
  const nonField = data.non_field_errors
  const reason =
    russian(detail) ??
    (Array.isArray(detail) ? russian(detail[0]) : null) ??
    (Array.isArray(nonField) ? russian(nonField[0]) : null)
  if (reason) return reason
  const status = err.response?.status
  if (status === 400 || status === 401) return 'Неверный логин или пароль'
  if (status === 429) return 'Слишком много попыток. Подождите минуту.'
  return 'Не удалось войти. Попробуйте позже.'
}
