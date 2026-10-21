import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../api'
import { onBalanceChanged } from '../lib/balance'
import type { ActiveBoost } from '../lib/cosmetics'
import ShopItemEmblem from './ShopItemEmblem'

/** Короткая подпись буста: «×2» берём из кода, остальное — из названия. */
function boostLabel(boost: ActiveBoost): string {
  if (/x2/.test(boost.code)) return 'Активен буст ×2'
  return `Активен буст: ${boost.title}`
}

/** Ненавязчивая плашка «Активен буст»; без буста ничего не рисует. */
export function BoostPlaque({ boost }: { boost?: ActiveBoost | null }) {
  if (!boost) return null
  return (
    <div className="boost-plaque">
      <ShopItemEmblem code={boost.code} slot="boost" size={28} />
      <span className="boost-plaque__text">
        {boostLabel(boost)} <span className="boost-plaque__hint">· сработает на следующем квесте</span>
      </span>
    </div>
  )
}

/**
 * Плашка для страниц, у которых своего профиля в данных нет (главная):
 * сама читает активный буст и обновляется после покупки или квеста.
 */
export default function ActiveBoostNotice() {
  const [boost, setBoost] = useState<ActiveBoost | null>(null)

  // Ответы могут прийти не по порядку (покупка + возврат во вкладку):
  // каждый новый запрос отменяет предыдущий, устаревший ответ не пишется.
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    api.get('/api/v1/profile/me/', { signal: controller.signal })
      .then((res) => setBoost(res.data?.active_boost ?? null))
      .catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const off = onBalanceChanged(load)
    return () => {
      off()
      abortRef.current?.abort()
    }
  }, [load])

  return <BoostPlaque boost={boost} />
}
