/** Вход только что случился: оболочка приложения играет заставку один раз. */
export const ENTER_FLAG = 'hp:entered'

export function hasEnterFlag(): boolean {
  try {
    return sessionStorage.getItem(ENTER_FLAG) === '1'
  } catch {
    return false
  }
}

export function clearEnterFlag(): void {
  try {
    sessionStorage.removeItem(ENTER_FLAG)
  } catch {
    // хранилище недоступно — флага и не было
  }
}

export function markEntered(): void {
  try {
    sessionStorage.setItem(ENTER_FLAG, '1')
  } catch {
    // приватный режим без хранилища — просто без заставки
  }
}
