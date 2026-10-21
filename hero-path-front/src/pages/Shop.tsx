import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import api from '../api'
import { notifyBalanceChanged } from '../lib/balance'
import { celebrate } from '../lib/celebrate'
import { plural } from '../lib/plural'
import { useToasts } from '../useToasts'
import { apiErrorMessage, formatDateRu, SHOP_TAB_TYPES, unwrapList, formatRating } from '../lib/apiData'
import { useTabIndicator } from '../useTabIndicator'
import RollNumber from '../components/RollNumber'
import Avatar from '../components/Avatar'
import ShopItemEmblem from '../components/ShopItemEmblem'
import {
  BANNER_BY_CODE,
  FRAME_BY_CODE,
  GLOW_BY_CODE,
  SLOT_HINTS,
  isCosmeticSlot,
  slotOfItem,
  type CosmeticSlot,
} from '../lib/cosmetics'
import PixelText from '../components/PixelText'
import '../styles/shop.css'

const TABS = ['Кастомизация', 'Привилегии', 'Мерч', 'Статусные'] as const

type CatalogFilter = 'all' | 'afford' | 'fresh'
type PriceSort = 'none' | 'asc' | 'desc'
const CATALOG_FILTERS: [CatalogFilter, string][] = [
  ['all', 'Все'],
  ['afford', 'Хватает монет'],
  ['fresh', 'Ещё не куплено'],
]
const PRICE_SORT_LABEL: Record<PriceSort, string> = { none: 'По цене', asc: 'Сначала дешёвые', desc: 'Сначала дорогие' }
const NEXT_SORT: Record<PriceSort, PriceSort> = { none: 'asc', asc: 'desc', desc: 'none' }

// подписи типов товара — те же, что у вкладок магазина
const TYPE_LABELS: Record<string, string> = Object.fromEntries(
  SHOP_TAB_TYPES.map((type, i) => [type, TABS[i]]),
)

interface Product {
  id: number
  code: string
  title: string
  price: string
  desc: string
  slot: string
  itemType: string
}

interface Purchase {
  id: number
  code: string
  type: string
  title: string
  price: string
  status: string
  date: string
  isApplied: boolean
  /** Слот косметики или 'boost'; '' — услуга/мерч, надевать нечего. */
  slot: string
  /** Буст одноразовый: когда сработал, приходит дата. */
  consumed: boolean
}

interface HistoryItem {
  name: string
  amount: string
  date: string
}

function Modal({
  open, onClose, title, children, width = '460px'
}: {
  open: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
  width?: string
}) {
  const [visible, setVisible] = useState(false)
  // «Закрывается» — не отдельное состояние, а следствие: окно уже закрыто,
  // но ещё видно, пока идёт анимация. В эффекте остаются только таймеры.
  const closing = !open && visible

  useEffect(() => {
    const t = setTimeout(() => setVisible(open), open ? 10 : 220)
    return () => clearTimeout(t)
  }, [open])

  // Esc закрывает окно, как и тап мимо него
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!visible && !open) return null

  return (
    <div className={`overlay${closing ? ' overlay--closing' : ''}`} onClick={onClose}>
      <div
        className={`popup popup--closable${closing ? ' popup--closing' : ''}`}
        onClick={e => e.stopPropagation()}
        style={{ width, maxWidth: '90vw' }}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        {/* на телефоне окно почти во весь экран — мимо него не попасть */}
        <button type="button" className="popup__close" onClick={onClose} aria-label="Закрыть">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
        </button>
        {title && <h3 className="popup__title">{title}</h3>}
        {children}
      </div>
    </div>
  )
}

// Состояние покупки словами: косметика надевается, буст срабатывает сам.
function purchaseStateLabel(p: Purchase): string {
  if (p.slot === 'boost') return p.consumed ? 'Использован' : 'Сработает на следующем квесте'
  if (isCosmeticSlot(p.slot)) return p.isApplied ? 'Надета' : 'Куплена'
  return 'Куплена'
}

// ключ перезапускает анимацию статуса при смене состояния
const purchaseStateKey = (p: Purchase) => `${p.slot}-${p.isApplied}-${p.consumed}`

function purchaseHint(p: Purchase): string {
  if (p.slot === 'boost') return 'Одноразовый: сработает на ближайшем квесте и исчезнет'
  if (isCosmeticSlot(p.slot)) return SLOT_HINTS[p.slot as CosmeticSlot]
  return ''
}

// Превью в карточке покупки: рамка, свечение и баннер показывают сам
// эффект, остальное — иконку товара.
function PurchasePreview({ purchase: p, me }: { purchase: Purchase; me: { avatar: string | null; name: string } }) {
  if (p.slot === 'avatar_frame') {
    return (
      <span className="shop-purchase__preview">
        <Avatar src={me.avatar} name={me.name || p.title} frame={FRAME_BY_CODE[p.code] ?? 'purple'} className="shop-purchase__avatar" />
      </span>
    )
  }
  if (p.slot === 'badge_glow') {
    const variant = GLOW_BY_CODE[p.code] ?? 'purple'
    return (
      <span className={`shop-purchase__preview shop-purchase__preview--glow shop-purchase__preview--glow-${variant}`}>
        <ShopItemEmblem code={p.code} slot={p.slot} size={40} />
      </span>
    )
  }
  if (p.slot === 'profile_banner') {
    const variant = BANNER_BY_CODE[p.code]
    return (
      <span className="shop-purchase__preview shop-purchase__preview--banner">
        <span className={`banner-swatch${variant ? ` banner--${variant}` : ''}`} aria-hidden="true" />
      </span>
    )
  }
  return (
    <span className="shop-purchase__preview shop-purchase__preview--emblem">
      <ShopItemEmblem code={p.code} slot={p.slot} itemType={p.type} size={44} />
    </span>
  )
}

export default function Shop() {
  const [activeTab, setActiveTab] = useState(0)
  const [switching, setSwitching] = useState(false)
  const [showPurchase, setShowPurchase] = useState<number | null>(null)
  const [showPurchases, setShowPurchases] = useState(false)
  const [catalogFilter, setCatalogFilter] = useState<CatalogFilter>('all')
  const [priceSort, setPriceSort] = useState<PriceSort>('none')
  const [purchaseFilter, setPurchaseFilter] = useState<string>('all')
  const [showDetail, setShowDetail] = useState<number | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [products, setProducts] = useState<Product[]>([])
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [coins, setCoins] = useState('0')
  const [purchasedCodes, setPurchasedCodes] = useState<Set<string>>(new Set())
  // id покупок, по которым сейчас идут запросы. Набор, а не один id: пока
  // летит запрос, в том же слоте нельзя нажать вторую кнопку — иначе
  // применение и снятие обгоняют друг друга.
  const [applyingIds, setApplyingIds] = useState<Set<number>>(new Set())
  // кольцо вокруг нажатой кнопки; чередование имени перезапускает анимацию
  const [ring, setRing] = useState<{ id: number; n: number } | null>(null)
  // свой аватар — для превью рамки прямо в карточке покупки
  const [me, setMe] = useState<{ avatar: string | null; name: string }>({ avatar: null, name: '' })
  const [loading, setLoading] = useState(true)
  const { toasts, addToast } = useToasts()

  // лента категорий прокручивается на узких экранах; выбранная подъезжает к центру
  const tabsScrollRef = useRef<HTMLElement>(null)
  // ref отдельно от состояния: в одном объекте линтер React считал рефом всё.
  const {
    containerRef: tabsContainerRef,
    registerTab,
    indicator: tabIndicatorBox,
  } = useTabIndicator(activeTab, loading, tabsScrollRef)

  // quiet — обновить после покупки без лоадера: иначе сетка товаров
  // пропадает, страница сжимается и прокрутка прыгает вверх.
  // Экран загрузки — только при первом открытии. Смена вкладки раньше
  // прятала всю страницу вместе с вкладками и рисовала заново; теперь
  // сетка товаров гаснет на месте и проявляется с новыми.
  const loadedOnce = useRef(false)
  const loadShop = useCallback(({ quiet = false }: { quiet?: boolean } = {}) => {
    const itemType = SHOP_TAB_TYPES[activeTab]

    Promise.all([
      api.get('/api/v1/shop/items/', { params: { item_type: itemType } }),
      api.get('/api/v1/shop/my-purchases/'),
      api.get('/api/v1/quests/rewards/history/'),
      api.get('/api/v1/profile/me/'),
    ]).then(([itemsRes, purchasesRes, rewardsRes, profileRes]) => {
      const items = unwrapList<{
        id: number
        code: string
        title: string
        description?: string
        price_coins: number
        slot?: string
        item_type?: string
      }>(itemsRes.data)

      setProducts(items.map((item) => ({
        id: item.id,
        code: item.code,
        title: item.title,
        price: String(item.price_coins),
        desc: item.description || '',
        slot: slotOfItem(item.code, item.slot),
        itemType: item.item_type ?? itemType,
      })))

      const purchaseRows = unwrapList<{
        id: number
        coins_spent: number
        created_at: string
        is_applied?: boolean
        slot?: string
        consumed_at?: string | null
        item: { title: string; code?: string; item_type?: string; slot?: string }
      }>(purchasesRes.data)

      setPurchasedCodes(new Set(
        purchaseRows.map((p) => p.item?.code).filter((code): code is string => Boolean(code)),
      ))

      setPurchases(purchaseRows.map((p) => ({
        id: p.id,
        code: p.item?.code ?? '',
        type: p.item?.item_type ?? '',
        title: p.item?.title ?? 'Покупка',
        price: String(p.coins_spent),
        status: p.created_at ? `Куплено · ${formatDateRu(p.created_at)}` : 'Куплено',
        date: formatDateRu(p.created_at),
        isApplied: Boolean(p.is_applied),
        slot: slotOfItem(p.item?.code ?? '', p.slot ?? p.item?.slot),
        consumed: Boolean(p.consumed_at),
      })))

      const rewardRows = unwrapList<{
        quest_title: string
        coins_delta: number
        granted_at: string
      }>(rewardsRes.data)

      const purchaseHistory: HistoryItem[] = purchaseRows.map((p) => ({
        name: p.item?.title ?? 'Покупка',
        amount: `-${formatRating(p.coins_spent)}`,
        date: formatDateRu(p.created_at),
      }))
      const rewardHistory: HistoryItem[] = rewardRows.map((r) => ({
        name: r.quest_title,
        amount: r.coins_delta >= 0 ? `+${formatRating(r.coins_delta)}` : formatRating(r.coins_delta),
        date: formatDateRu(r.granted_at),
      }))
      setHistory([...purchaseHistory, ...rewardHistory].sort(
        (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
      ))

      setCoins(formatRating(profileRes.data.coins_balance))
      setMe({ avatar: profileRes.data.avatar ?? null, name: profileRes.data.callsign || profileRes.data.username || '' })
    }).catch(() => addToast(quiet ? 'Не удалось обновить магазин' : 'Не удалось загрузить магазин', 'error'))
      .finally(() => {
        loadedOnce.current = true
        setLoading(false)
        setSwitching(false)
      })
  }, [activeTab, addToast])

  useEffect(() => {
    loadShop()
  }, [loadShop])


  // Одновременно надета одна вещь на слот — правило на бэкенде, поэтому
  // после переключения список перезагружаем целиком.
  // Карточка переключается сразу, не дожидаясь ответа: статус
  // переворачивается, кнопка меняет вид. Ошибка возвращает как было.
  const togglePurchase = useCallback((purchase: Purchase) => {
    const next = !purchase.isApplied
    // снимок до переключения: при ошибке возвращаем его целиком, вместе с
    // вещью, которую надевание вытеснило из слота
    const snapshot = purchases
    setPurchases(snapshot.map((x) => {
      if (x.id === purchase.id) return { ...x, isApplied: next }
      // в слоте надета одна вещь: прежнюю снимаем сразу
      return next && x.slot === purchase.slot ? { ...x, isApplied: false } : x
    }))
    setApplyingIds((ids) => new Set(ids).add(purchase.id))
    setRing((r) => ({ id: purchase.id, n: (r?.n ?? 0) + 1 }))
    const request = next
      ? api.post(`/api/v1/shop/purchases/${purchase.id}/apply/`)
      : api.delete(`/api/v1/shop/purchases/${purchase.id}/apply/`)
    request
      .then(() => {
        addToast(next ? 'Надето' : 'Снято', 'success')
        // шапка перечитает профиль — рамка у аватара появится сразу
        notifyBalanceChanged()
      })
      .catch(() => {
        setPurchases(snapshot)
        addToast('Не удалось изменить покупку', 'error')
      })
      .finally(() => {
        setApplyingIds((ids) => {
          const rest = new Set(ids)
          rest.delete(purchase.id)
          return rest
        })
        // дополнительная сверка с сервером
        loadShop({ quiet: true })
      })
  }, [purchases, addToast, loadShop])

  // слот занят, пока по любой покупке из него идёт запрос
  const busySlots = useMemo(() => new Set(
    purchases.filter((p) => applyingIds.has(p.id)).map((p) => p.slot),
  ), [purchases, applyingIds])

  const shownProducts = useMemo(() => {
    const list = products.filter((item) => {
      if (catalogFilter === 'afford') return !purchasedCodes.has(item.code) && Number(item.price) <= Number(coins)
      if (catalogFilter === 'fresh') return !purchasedCodes.has(item.code)
      return true
    })
    if (priceSort === 'none') return list
    const dir = priceSort === 'asc' ? 1 : -1
    return [...list].sort((a, b) => (Number(a.price) - Number(b.price)) * dir)
  }, [products, catalogFilter, priceSort, purchasedCodes, coins])

  // фильтр покупок: все, применённые и по типу — только типы, что есть
  const purchaseChips = useMemo<[string, string, number][]>(() => {
    const types = SHOP_TAB_TYPES.filter((type) => purchases.some((p) => p.type === type))
    const chips: [string, string, number][] = [['all', 'Все', purchases.length]]
    const applied = purchases.filter((p) => p.isApplied).length
    if (applied) chips.push(['applied', 'Надетые', applied])
    for (const type of types) chips.push([type, TYPE_LABELS[type], purchases.filter((p) => p.type === type).length])
    return chips
  }, [purchases])

  const shownPurchases = useMemo(() => purchases.filter((p) => (
    purchaseFilter === 'all' || (purchaseFilter === 'applied' ? p.isApplied : p.type === purchaseFilter)
  )), [purchases, purchaseFilter])

  const selectedProduct = products.find(p => p.id === (showPurchase ?? showDetail))
  const selectedDetail = showDetail !== null ? products.find(p => p.id === showDetail) : undefined
  // сколько монет не хватает на открытый товар (0 — хватает)
  const detailLack = selectedDetail ? Math.max(0, Number(selectedDetail.price) - Number(coins)) : 0

  const handleBuy = useCallback(() => {
    if (showPurchase === null) return
    const product = products.find((p) => p.id === showPurchase)
    if (!product) return
    api.post('/api/v1/shop/purchase/', { item_code: product.code })
      .then(() => {
        addToast('Покупка оформлена!', 'success')
        celebrate('big')
        notifyBalanceChanged()
        loadShop({ quiet: true })
      })
      .catch((err) => addToast(apiErrorMessage(err, 'Не удалось оформить покупку'), 'error'))
      .finally(() => setShowPurchase(null))
  }, [showPurchase, products, addToast, loadShop])

  return (
    <div className="dashboard shop-page page-enter">
      {loading ? (
        <div className="profile-loading" style={{ minHeight: '40vh' }}>
          <div className="loading-spinner">
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
            <span className="loading-spinner-dot" />
          </div>
          <p className="loading-text">Загрузка магазина...</p>
        </div>
      ) : showPurchases ? (
      <section className="shop-purchases">
        <button
          type="button"
          className="shop-detail__back btn-press"
          onClick={() => setShowPurchases(false)}
        >
          Назад в магазин
        </button>

        <div className="shop-purchases__card">
          <h2 className="shop-purchases__title"><PixelText text="Мои покупки" /></h2>
          {purchases.length > 0 && (
            <div className="shop-chips" role="group" aria-label="Фильтр покупок">
              {purchaseChips.map(([value, label, count]) => (
                <button
                  key={value}
                  type="button"
                  className="shop-chip"
                  aria-pressed={purchaseFilter === value}
                  onClick={() => setPurchaseFilter(value)}
                >
                  {label}<span className="shop-chip__count">{count}</span>
                </button>
              ))}
            </div>
          )}
          <div key={purchaseFilter} className="shop-purchases__list">
            {purchases.length === 0 ? (
              <p className="shop-purchases__empty">Покупок пока нет</p>
            ) : shownPurchases.length === 0 ? (
              <p className="shop-purchases__empty">Здесь пока пусто</p>
            ) : shownPurchases.map((p) => (
              <article
                key={p.id}
                className={`shop-purchase${p.isApplied ? ' shop-purchase--on' : ''}${applyingIds.has(p.id) ? ' shop-purchase--pending' : ''}`}
              >
                <span className="shop-purchase__frame">
                  <PurchasePreview purchase={p} me={me} />
                </span>
                <span className="shop-purchase__name">{p.title}</span>
                {purchaseHint(p) && <span className="shop-purchase__hint">{purchaseHint(p)}</span>}
                <span key={purchaseStateKey(p)} className="shop-purchase__state">
                  <i className="shop-purchase__tick" aria-hidden="true" />
                  {purchaseStateLabel(p)}
                </span>
                {isCosmeticSlot(p.slot) && (
                  <button
                    type="button"
                    className={`shop-purchase__apply btn-press${ring?.id === p.id ? ` ring-${ring.n % 2 ? 'a' : 'b'}` : ''}`}
                    onClick={() => togglePurchase(p)}
                    disabled={busySlots.has(p.slot)}
                    aria-pressed={p.isApplied}
                    aria-busy={applyingIds.has(p.id)}
                  >
                    <span key={String(p.isApplied)} className="shop-purchase__apply-label">
                      {p.isApplied ? 'Снять' : 'Надеть'}
                    </span>
                    <span className="shop-purchase__apply-dots" aria-hidden="true"><i /><i /><i /></span>
                  </button>
                )}
              </article>
            ))}
          </div>
        </div>
      </section>
      ) : selectedDetail ? (
      <section className="shop-detail">
        <button
          type="button"
          className="shop-detail__back btn-press"
          onClick={() => setShowDetail(null)}
        >
          Назад в магазин
        </button>

        <div className="shop-detail__body">
          <div className="shop-detail__gallery">
            <div className="shop-detail__emblem">
              <ShopItemEmblem code={selectedDetail.code} slot={selectedDetail.slot} itemType={selectedDetail.itemType} size={200} />
            </div>
          </div>

          <div className="shop-detail__info">
            <h2 className="shop-detail__title">{selectedDetail.title}</h2>
            <div className="shop-detail__price">
              <span className="shop-card__coin" aria-hidden="true" />
              <span className="shop-card__price-value">{selectedDetail.price}</span>
            </div>
            <div className="shop-detail__about">
              <h3 className="shop-detail__about-title">Описание</h3>
              <p className="shop-detail__desc">
                {selectedDetail.desc || 'Описание пока не заполнено.'}
              </p>
            </div>
            {purchasedCodes.has(selectedDetail.code) ? (
              <button type="button" className="shop-detail__buy" disabled>
                Куплено
              </button>
            ) : detailLack > 0 ? (
              <button type="button" className="shop-detail__buy shop-card__buy--lack" disabled>
                {`Не хватает ${detailLack} ${plural(detailLack, ['монеты', 'монет', 'монет'])}`}
              </button>
            ) : (
              <button
                type="button"
                className="shop-detail__buy btn-press"
                onClick={() => setShowPurchase(selectedDetail.id)}
              >
                Купить
              </button>
            )}
          </div>
        </div>
      </section>
      ) : (
      <>
      <div className="shop-page__head">
        <div className="shop-page__head-left">
        <nav className="shop-tabs" aria-label="Категории магазина" ref={tabsScrollRef}>
          {/* Вкладки и линия под ними в общем блоке: лента прокручивается
              целиком, и линия всегда тянется на всю её длину. */}
          <div className="shop-tabs__inner">
            <div className="shop-tabs__labels" role="tablist" ref={tabsContainerRef}>
              {TABS.map((label, index) => (
                <button
                  key={label} type="button" role="tab"
                  aria-selected={activeTab === index}
                  className={`shop-tab ${activeTab === index ? 'shop-tab--active' : ''} btn-press`}
                  onClick={() => {
                    // «Переключаю» — здесь, а не в эффекте загрузки вкладки.
                    if (index === activeTab) return
                    setSwitching(true)
                    setActiveTab(index)
                  }}
                  ref={registerTab(index)}
                >{label}</button>
              ))}
            </div>
            <div className="shop-tabs__track" aria-hidden="true">
              <span className="shop-tabs__line" />
              <div
                className="shop-tabs__pill"
                style={{ left: tabIndicatorBox.left + (tabIndicatorBox.width - 50) / 2 }}
              />
            </div>
          </div>
        </nav>

          <div className="shop-purchases-frame">
            <button type="button" className="shop-purchases-btn btn-press" onClick={() => setShowPurchases(true)}>
              <span className="shop-purchases-btn__label">Мои покупки</span>
            </button>
          </div>
        </div>

        <section className="shop-wallet" aria-label="Баланс монет">
          <p className="shop-wallet__label">Сколько монет у пользователя:</p>
          <div className="shop-wallet__amount">
            <span className="shop-wallet__coin" aria-hidden="true" />
            <RollNumber className="shop-wallet__value" value={coins} />
          </div>
          <button type="button" className="shop-wallet__history btn-press" onClick={() => setShowHistory(true)}>
            <span className="shop-wallet__history-label">История покупок</span>
          </button>
        </section>
      </div>

      {products.length > 0 && (
        <div className="shop-chips shop-chips--catalog" role="group" aria-label="Фильтр товаров">
          {CATALOG_FILTERS.map(([value, label]) => (
            <button
              key={value}
              type="button"
              className="shop-chip"
              aria-pressed={catalogFilter === value}
              onClick={() => setCatalogFilter(value)}
            >
              {label}
            </button>
          ))}
          <button
            type="button"
            className={`shop-chip shop-chip--sort shop-chip--${priceSort}`}
            aria-pressed={priceSort !== 'none'}
            onClick={() => setPriceSort((v) => NEXT_SORT[v])}
          >
            <svg className="shop-chip__arrow" viewBox="0 0 12 14" width="12" height="14" aria-hidden="true">
              <path d="M6 13V2M1.5 6L6 1.5 10.5 6" />
            </svg>
            {PRICE_SORT_LABEL[priceSort]}
          </button>
        </div>
      )}

      <div key={`${catalogFilter}-${priceSort}`} className={`shop-grid${switching ? ' shop-grid--switching' : ''}`} aria-busy={switching}>
        {products.length === 0 ? (
          <p className="loading-text" style={{ gridColumn: '1 / -1', textAlign: 'center' }}>Товаров в этой категории пока нет</p>
        ) : shownProducts.length === 0 ? (
          <p className="loading-text" style={{ gridColumn: '1 / -1', textAlign: 'center' }}>
            {catalogFilter === 'afford' ? 'Пока не хватает монет ни на что из этого раздела' : 'Всё из этого раздела уже куплено'}
          </p>
        ) : shownProducts.map((item, i) => {
          const isPurchased = purchasedCodes.has(item.code)
          // В макете товар, на который не хватает монет, сразу показывает
          // серую кнопку с недостающей суммой, а не ошибку после нажатия.
          const lack = Number(item.price) - Number(coins)
          const tooExpensive = !isPurchased && lack > 0
          return (
          <article
            key={item.id}
            className="shop-card hover-lift spot"
            style={{ animationDelay: `${i * 50}ms` }}
            onClick={() => setShowDetail(item.id)}
          >
            <div className="shop-card__emblem">
              <ShopItemEmblem code={item.code} slot={item.slot} itemType={item.itemType} size={120} />
            </div>
            <h2 className="shop-card__title">{item.title}</h2>
            <div className="shop-card__price">
              <span className="shop-card__coin" aria-hidden="true" />
              <span className="shop-card__price-value">{item.price}</span>
            </div>
            <div className="shop-card__actions">
              <button
                type="button"
                className={`shop-card__buy${tooExpensive ? ' shop-card__buy--lack' : ''} btn-press`}
                onClick={(e) => { e.stopPropagation(); setShowPurchase(item.id) }}
                disabled={isPurchased || tooExpensive}
              >
                {isPurchased
                  ? 'Куплено'
                  : tooExpensive
                    ? `Не хватает ${lack} ${plural(lack, ['монеты', 'монет', 'монет'])}`
                    : 'Купить'}
              </button>
            </div>
          </article>
        )})}
      </div>

      <Modal open={showPurchase !== null} onClose={() => setShowPurchase(null)} title="Подтвердите покупку">
        <div className="shop-modal__product">
          <span className="shop-modal__name">{selectedProduct?.title}</span>
          <div className="shop-modal__price-tag">
            <span className="shop-wallet__coin" aria-hidden="true" />
            <span>{selectedProduct?.price}</span>
          </div>
        </div>
        <div className="shop-modal__buttons">
          <button type="button" className="shop-modal__btn shop-modal__btn--secondary btn-press" onClick={() => setShowPurchase(null)}>
            Отмена
          </button>
          <button type="button" className="shop-modal__btn shop-modal__btn--primary btn-press" onClick={handleBuy}>
            Купить
          </button>
        </div>
      </Modal>



      <Modal open={showHistory} onClose={() => setShowHistory(false)} title="История операций" width="500px">
        <div className="shop-modal__history">
          {history.length === 0 ? (
            <p className="loading-text">История пуста</p>
          ) : history.map((h, i) => (
            <div key={i} className="shop-modal__history-item">
              <div>
                <div className="shop-modal__history-name">{h.name}</div>
                <div className="shop-modal__history-date">{h.date}</div>
              </div>
              <span className={`shop-modal__history-amount${h.amount.startsWith('+') ? ' shop-modal__history-amount--positive' : ' shop-modal__history-amount--negative'}`}>
                {h.amount}
              </span>
            </div>
          ))}
        </div>
      </Modal>

      <div className="toast-container toast-container--fixed-right">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast--${toast.type}`}>
            {toast.message}
          </div>
        ))}
      </div>
      </>
      )}
    </div>
  )
}