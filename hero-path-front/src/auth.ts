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
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && typeof detail[0] === 'string') return detail[0]
  const nonField = data.non_field_errors
  if (Array.isArray(nonField) && typeof nonField[0] === 'string') return nonField[0]
  if (err.response?.status === 401) return 'Неверный логин или пароль'
  return 'Не удалось войти. Попробуйте позже.'
}
