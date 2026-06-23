import { useState, useRef, useEffect, useCallback } from 'react'
import palmSky from '../assets/shop/palm-sky.png'
import api from '../api'
import { useToasts } from '../useToasts'
import { formatDateRu, SHOP_TAB_TYPES, unwrapList } from '../lib/apiData'

const TABS = ['Кастомизация', 'Привилегии', 'Мерч', 'Статусные'] as const

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
  title: string
  price: string
  status: string
  date: string
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

  if (!visible && !open) return null

  return (
    <div className={`overlay${closing ? ' overlay--closing' : ''}`} onClick={onClose}>
      <div
        className={`popup${closing ? ' popup--closing' : ''}`}
        onClick={e => e.stopPropagation()}
        style={{ width, maxWidth: '90vw' }}
      >
        {title && <h3 className="popup__title">{title}</h3>}
        {children}
      </div>
    </div>
  )
}

export default function Shop() {
  const [activeTab, setActiveTab] = useState(0)
  const [showPurchase, setShowPurchase] = useState<number | null>(null)
  const [showPurchases, setShowPurchases] = useState(false)
  const [showDetail, setShowDetail] = useState<number | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [products, setProducts] = useState<Product[]>([])
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [coins, setCoins] = useState('0')
  const [purchasedCodes, setPurchasedCodes] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const { toasts, addToast } = useToasts()

  const tabsRef = useRef<HTMLDivElement>(null)
  const tabRefs = useRef<Record<number, HTMLButtonElement | null>>({})
  const [pillStyle, setPillStyle] = useState({ left: 0, width: 50 })

  const loadShop = useCallback(() => {
    setLoading(true)
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
        item: { title: string; code?: string }
      }>(purchasesRes.data)

      setPurchasedCodes(new Set(
        purchaseRows.map((p) => p.item?.code).filter((code): code is string => Boolean(code)),
      ))

      setPurchases(purchaseRows.map((p) => ({
        id: p.id,
        title: p.item?.title ?? 'Покупка',
        price: String(p.coins_spent),
        status: p.created_at ? `Куплено · ${formatDateRu(p.created_at)}` : 'Куплено',
        date: formatDateRu(p.created_at),
      })))

      const rewardRows = unwrapList<{
        quest_title: string
        coins_delta: number
        granted_at: string
      }>(rewardsRes.data)

      const purchaseHistory: HistoryItem[] = purchaseRows.map((p) => ({
        name: p.item?.title ?? 'Покупка',
        amount: `-${p.coins_spent}`,
        date: formatDateRu(p.created_at),
      }))
      const rewardHistory: HistoryItem[] = rewardRows.map((r) => ({
        name: r.quest_title,
        amount: r.coins_delta >= 0 ? `+${r.coins_delta}` : String(r.coins_delta),
        date: formatDateRu(r.granted_at),
      }))
      setHistory([...purchaseHistory, ...rewardHistory].sort(
        (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
      ))

      setCoins(String(profileRes.data.coins_balance ?? 0))
    }).catch(() => addToast('Не удалось загрузить магазин', 'error'))
      .finally(() => setLoading(false))
  }, [activeTab, addToast])

  useEffect(() => {
    loadShop()
  }, [loadShop])

  useEffect(() => {
    const container = tabsRef.current
    const activeBtn = tabRefs.current[activeTab]
    if (!container || !activeBtn) return
    const containerRect = container.getBoundingClientRect()
    const btnRect = activeBtn.getBoundingClientRect()
    setPillStyle({ left: btnRect.left - containerRect.left + (btnRect.width - 50) / 2, width: 50 })
  }, [activeTab])

  const selectedProduct = products.find(p => p.id === (showPurchase ?? showDetail))

  const handleBuy = useCallback(() => {
    if (showPurchase === null) return
    const product = products.find((p) => p.id === showPurchase)
    if (!product) return
    api.post('/api/v1/shop/purchase/', { item_code: product.code })
      .then(() => {
        addToast('Покупка оформлена!', 'success')
        loadShop()
      })
      .catch(() => addToast('Не удалось оформить покупку', 'error'))
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
      ) : (
      <>
      <div className="shop-page__band shop-page__band--tabs">
        <nav className="shop-tabs" aria-label="Категории магазина">
          <div className="shop-tabs__labels" role="tablist" ref={tabsRef}>
            {TABS.map((label, index) => (
              <button
                key={label} type="button" role="tab"
                aria-selected={activeTab === index}
                className={`shop-tab ${activeTab === index ? 'shop-tab--active' : ''} btn-press`}
                onClick={() => setActiveTab(index)}
                ref={el => { tabRefs.current[index] = el }}
              >{label}</button>
            ))}
          </div>
          <div className="shop-tabs__track" aria-hidden="true">
            <span className="shop-tabs__line" />
            <div className="shop-tabs__pill" style={{ left: pillStyle.left }} />
          </div>
        </nav>
      </div>

      <div className="shop-page__band shop-page__band--split">
        <div className="shop-purchases-frame">
          <button type="button" className="shop-purchases-btn btn-press" onClick={() => setShowPurchases(true)}>
            <span className="shop-purchases-btn__label">Мои покупки</span>
          </button>
        </div>
        <div className="shop-page__split-spacer" aria-hidden="true" />
        <section className="shop-wallet" aria-label="Баланс монет">
          <div className="shop-wallet__stack">
            <p className="shop-wallet__label">Баланс:</p>
            <div className="shop-wallet__amount">
              <span className="shop-wallet__coin" aria-hidden="true" />
              <span className="shop-wallet__value">{coins}</span>
            </div>
          </div>
          <button type="button" className="shop-wallet__history btn-press" onClick={() => setShowHistory(true)}>
            <span className="shop-wallet__history-label">История</span>
          </button>
        </section>
      </div>

      <div className="shop-grid">
        {products.length === 0 ? (
          <p className="loading-text" style={{ gridColumn: '1 / -1', textAlign: 'center' }}>Товаров в этой категории пока нет</p>
        ) : products.map((item, i) => {
          const isPurchased = purchasedCodes.has(item.code)
          return (
          <article key={item.id} className="shop-card hover-lift" style={{ animationDelay: `${i * 50}ms` }}>
            <img className="shop-card__thumb" src={item.image ?? palmSky} alt="" width={300} height={184} loading="lazy" />
            <h2 className="shop-card__title">{item.title}</h2>
            <div className="shop-card__price">
              <span className="shop-card__coin" aria-hidden="true" />
              <span className="shop-card__price-value">{item.price}</span>
            </div>
            <div className="shop-card__actions">
              <button
                type="button"
                className="shop-card__buy btn-press"
                onClick={() => setShowPurchase(item.id)}
                disabled={isPurchased}
              >
                {isPurchased ? 'Куплено' : 'Купить'}
              </button>
              <button type="button" className="shop-card__detail btn-press" onClick={() => setShowDetail(item.id)}>
                ?
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

      <Modal open={showDetail !== null} onClose={() => setShowDetail(null)} title={selectedProduct?.title} width="600px">
        <div className="shop-modal__detail">
          <img src={selectedProduct?.image ?? palmSky} alt="" className="shop-modal__detail-img" />
          <div className="shop-modal__detail-info">
            <div className="shop-modal__price-tag">
              <span className="shop-wallet__coin" aria-hidden="true" />
              <span>{selectedProduct?.price}</span>
            </div>
            <p className="shop-modal__detail-desc">{selectedProduct?.desc}</p>
            <button type="button" className="shop-modal__btn shop-modal__btn--primary btn-press" onClick={() => { setShowDetail(null); setShowPurchase(showDetail) }}>
              Купить
            </button>
          </div>
        </div>
      </Modal>

      <Modal open={showPurchases} onClose={() => setShowPurchases(false)} title="Мои покупки" width="600px">
        <div className="shop-modal__purchases">
          {purchases.length === 0 ? (
            <p className="loading-text">Покупок пока нет</p>
          ) : purchases.map(p => (
            <div key={p.id} className="shop-modal__purchase-item">
              <img src={palmSky} alt="" className="shop-modal__purchase-img" />
              <div className="shop-modal__purchase-info">
                <span className="shop-modal__purchase-name">{p.title}</span>
                <div className="shop-modal__price-tag shop-modal__price-tag--small">
                  <span className="shop-wallet__coin" aria-hidden="true" />
                  <span>{p.price}</span>
                </div>
                <span className="shop-modal__history-date">{p.date}</span>
              </div>
              <span className="shop-modal__purchase-status shop-modal__purchase-status--applied">
                {p.status}
              </span>
            </div>
          ))}
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
            {toast.type === 'success' ? '✓ ' : '✕ '}
            {toast.message}
          </div>
        ))}
      </div>
      </>
      )}
    </div>
  )
}