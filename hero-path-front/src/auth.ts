const SESSION_KEY = 'hero-path-session'

interface AuthSession {
  id: string
  access: string
  refresh: string
}

export function readAuthSession(): AuthSession | null {
  const stored = localStorage.getItem(SESSION_KEY)
  if (stored) {
    try {
      const session = JSON.parse(stored) as Partial<AuthSession>
      if (typeof session.id === 'string' && typeof session.access === 'string' && typeof session.refresh === 'string') {
        return { id: session.id, access: session.access, refresh: session.refresh }
      }
    } catch {
      // A damaged session is treated as logged out.
    }
    return null
  }
  const access = localStorage.getItem('access_token')
  const refresh = localStorage.getItem('refresh_token')
  return access && refresh ? { id: `legacy-${access.slice(-24)}`, access, refresh } : null
}

export function saveAuthSession(session: AuthSession): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export function startAuthSession(access: string, refresh: string): void {
  const id = Array.from(crypto.getRandomValues(new Uint32Array(4))).join('-')
  saveAuthSession({ id, access, refresh })
}

export function isAuthenticated(): boolean {
  return readAuthSession() !== null
}

export function clearAuthTokens(): void {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem(SESSION_KEY)
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
