/**
 * Сигнал «баланс монет изменился».
 *
 * Шапка запрашивает профиль один раз при загрузке, поэтому после покупки
 * в магазине там оставалось старое число. Страница, которая списывает
 * или начисляет монеты, зовёт notifyBalanceChanged(), а шапка
 * подписана через onBalanceChanged() и перечитывает профиль.
 */
const EVENT = 'hero:balance-changed'

export function notifyBalanceChanged(): void {
  window.dispatchEvent(new Event(EVENT))
}

export function onBalanceChanged(listener: () => void): () => void {
  window.addEventListener(EVENT, listener)
  return () => window.removeEventListener(EVENT, listener)
}
