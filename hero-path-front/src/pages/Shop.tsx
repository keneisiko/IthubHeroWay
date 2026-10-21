import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import palmSky from '../assets/shop/palm-sky.png'
import api from '../api'
import { notifyBalanceChanged } from '../lib/balance'
import { celebrate } from '../lib/celebrate'
import { plural } from '../lib/plural'
import { useToasts } from '../useToasts'
import { apiErrorMessage, formatDateRu, SHOP_TAB_TYPES, unwrapList, formatRating } from '../lib/apiData'
import { useTabIndicator } from '../useTabIndicator'
import RollNumber from '../components/RollNumber'
import Avatar from '../components/Avatar'
import BadgeEmblem from '../components/BadgeEmblem'
import { AVATAR_FRAME, BADGE_GLOW, COSMETIC_HINTS } from '../lib/cosmetics'
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
  image?: string
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
  const [closing, setClosing] = useState(false)

  useEffect(() => {
    if (open) {
      setClosing(false)
      const t = setTimeout(() => setVisible(true), 10)
      return () => clearTimeout(t)
    } else {
      setClosing(true)
      const t = setTimeout(() => setVisible(false), 220)
      return () => clearTimeout(t)
    }
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
  // id покупки, по которой сейчас идёт запрос: кнопка блокируется, чтобы
  // двойной клик не отправил применение и снятие подряд.
  const [applyingId, setApplyingId] = useState<number | null>(null)
  // кольцо вокруг нажатой кнопки; чередование имени перезапускает анимацию
  const [ring, setRing] = useState<{ id: number; n: number } | null>(null)
  // свой аватар — для превью рамки прямо в карточке покупки
  const [me, setMe] = useState<{ avatar: string | null; name: string }>({ avatar: null, name: '' })
  const [loading, setLoading] = useState(true)
  const { toasts, addToast } = useToasts()

  // лента категорий прокручивается на узких экранах; выбранная подъезжает к центру
  const tabsScrollRef = useRef<HTMLElement>(null)
  const tabIndicator = useTabIndicator(activeTab, loading, tabsScrollRef)

  // quiet — обновить после покупки без лоадера: иначе сетка товаров
  // пропадает, страница сжимается и прокрутка прыгает вверх.
  // Экран загрузки — только при первом открытии. Смена вкладки раньше
  // прятала всю страницу вместе с вкладками и рисовала заново; теперь
  // сетка товаров гаснет на месте и проявляется с новыми.
  const loadedOnce = useRef(false)
  const loadShop = useCallback(({ quiet = false }: { quiet?: boolean } = {}) => {
    if (!loadedOnce.current) setLoading(true)
    else if (!quiet) setSwitching(true)
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
      }>(itemsRes.data)

      setProducts(items.map((item) => ({
        id: item.id,
        code: item.code,
        title: item.title,
        price: String(item.price_coins),
        desc: item.description || '',
      })))

      const purchaseRows = unwrapList<{
        id: number
        coins_spent: number
        created_at: string
        is_applied?: boolean
        item: { title: string; code?: string; item_type?: string }
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


  // Одновременно активна одна покупка на тип товара — правило на бэкенде,
  // поэтому после переключения список перезагружаем целиком.
  // Карточка переключается сразу, не дожидаясь ответа: статус
  // переворачивается, кнопка меняет вид. Ошибка возвращает как было.
  const togglePurchase = useCallback((purchase: Purchase) => {
    const next = !purchase.isApplied
    const flip = (value: boolean) => setPurchases((list) => list.map((x) => (
      x.id === purchase.id ? { ...x, isApplied: value } : x
    )))
    setApplyingId(purchase.id)
    flip(next)
    setRing((r) => ({ id: purchase.id, n: (r?.n ?? 0) + 1 }))
    const request = next
      ? api.post(`/api/v1/shop/purchases/${purchase.id}/apply/`)
      : api.delete(`/api/v1/shop/purchases/${purchase.id}/apply/`)
    request
      .then(() => {
        addToast(next ? 'Покупка применена' : 'Покупка снята', 'success')
        loadShop({ quiet: true })
        // шапка перечитает профиль — рамка у аватара появится сразу
        notifyBalanceChanged()
      })
      .catch(() => {
        flip(purchase.isApplied)
        addToast('Не удалось изменить покупку', 'error')
      })
      .finally(() => setApplyingId(null))
  }, [addToast, loadShop])

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
    if (applied) chips.push(['applied', 'Применённые', applied])
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
  // Бэкенд отдаёт одно изображение на товар, галереи в данных нет
  const detailImages = [selectedDetail?.image ?? palmSky]

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
                className={`shop-purchase${p.isApplied ? ' shop-purchase--on' : ''}${applyingId === p.id ? ' shop-purchase--pending' : ''}`}
              >
                <span className="shop-purchase__frame">
                  {p.code === AVATAR_FRAME ? (
                    <span className="shop-purchase__preview">
                      <Avatar src={me.avatar} name={me.name || p.title} framed={p.isApplied} className="shop-purchase__avatar" />
                    </span>
                  ) : p.code === BADGE_GLOW ? (
                    <span className={`shop-purchase__preview${p.isApplied ? ' shop-purchase__preview--glow' : ''}`}>
                      <BadgeEmblem code="glow" rarity="epic" size={40} />
                    </span>
                  ) : (
                    <img src={palmSky} alt="" className="shop-purchase__image" />
                  )}
                </span>
                <span className="shop-purchase__name">{p.title}</span>
                {COSMETIC_HINTS[p.code] && (
                  <span className="shop-purchase__hint">
                    {p.isApplied ? COSMETIC_HINTS[p.code] : 'Примените, чтобы увидеть'}
                  </span>
                )}
                <span key={String(p.isApplied)} className="shop-purchase__state">
                  <i className="shop-purchase__tick" aria-hidden="true" />
                  {p.isApplied ? 'Применена' : 'Куплена'}
                </span>
                <button
                  type="button"
                  className={`shop-purchase__apply btn-press${ring?.id === p.id ? ` ring-${ring.n % 2 ? 'a' : 'b'}` : ''}`}
                  onClick={() => togglePurchase(p)}
                  disabled={applyingId === p.id}
                  aria-pressed={p.isApplied}
                  aria-busy={applyingId === p.id}
                >
                  <span key={String(p.isApplied)} className="shop-purchase__apply-label">
                    {p.isApplied ? 'Снять' : 'Применить'}
                  </span>
                  <span className="shop-purchase__apply-dots" aria-hidden="true"><i /><i /><i /></span>
                </button>
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
            <div className="shop-detail__thumbs">
              {detailImages.map((src, i) => (
                <img key={i} src={src} alt="" className="shop-detail__thumb" />
              ))}
            </div>
            <img src={detailImages[0]} alt="" className="shop-detail__image" />
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
            <div className="shop-tabs__labels" role="tablist" ref={tabIndicator.containerRef}>
              {TABS.map((label, index) => (
                <button
                  key={label} type="button" role="tab"
                  aria-selected={activeTab === index}
                  className={`shop-tab ${activeTab === index ? 'shop-tab--active' : ''} btn-press`}
                  onClick={() => setActiveTab(index)}
                  ref={tabIndicator.registerTab(index)}
                >{label}</button>
              ))}
            </div>
            <div className="shop-tabs__track" aria-hidden="true">
              <span className="shop-tabs__line" />
              <div
                className="shop-tabs__pill"
                style={{ left: tabIndicator.indicator.left + (tabIndicator.indicator.width - 50) / 2 }}
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
            <img className="shop-card__thumb" src={item.image ?? palmSky} alt="" width={300} height={184} loading="lazy" />
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