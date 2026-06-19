export function isAuthenticated(): boolean {
  return Boolean(localStorage.getItem('access_token'))
}

export function clearAuthTokens(): void {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}
