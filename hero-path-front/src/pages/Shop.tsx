import { useState, useRef, useEffect, useCallback } from 'react'
import palmSky from '../assets/shop/palm-sky.png'
import api from '../api'

const TABS = ['Кастомизация', 'Привилегии', 'Мерч', 'Статусные'] as const

interface Product {
  id: number
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
  const [products, setProducts] = useState<Product[]>(Array.from({ length: 9 }, (_, i) => ({
    id: i + 1, title: 'Название', price: '9.99',
    desc: 'Описание товара. Краткое описание для демонстрации MVP функционала магазина.',
  })))
  const [purchases, setPurchases] = useState<Purchase[]>([
    { id: 1, title: 'Название', price: '9.99', status: 'Применено' },
    { id: 2, title: 'Название', price: '4.50', status: 'Не применено' },
  ])
  const [history, setHistory] = useState<HistoryItem[]>([
    { name: 'Название', amount: '-9.99', date: '12 мая 2026' },
    { name: 'Название', amount: '-4.50', date: '10 мая 2026' },
    { name: 'Награда за квест', amount: '+15.00', date: '8 мая 2026' },
  ])
  const [coins, setCoins] = useState('0')

  const tabsRef = useRef<HTMLDivElement>(null)
  const tabRefs = useRef<Record<number, HTMLButtonElement | null>>({})
  const [pillStyle, setPillStyle] = useState({ left: 0, width: 50 })

  useEffect(() => {
    api.get('/api/v1/shop/items/').then(res => {
      if (res.data?.length) setProducts(res.data)
    }).catch(() => {})

    api.get('/api/v1/shop/purchases/').then(res => {
      if (res.data?.length) setPurchases(res.data)
    }).catch(() => {})

    api.get('/api/v1/shop/history/').then(res => {
      if (res.data?.length) setHistory(res.data)
    }).catch(() => {})

    api.get('/api/v1/profile/me/').then(res => {
      setCoins(res.data.coins ?? '0')
    }).catch(() => {})
  }, [])

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
    api.post('/api/v1/shop/buy/', { item_id: showPurchase })
      .catch(() => {})
      .finally(() => setShowPurchase(null))
  }, [showPurchase])

  const handleApply = useCallback((purchaseId: number) => {
    api.post(`/api/v1/shop/apply/${purchaseId}/`)
      .then(() => {
        setPurchases(prev => prev.map(p =>
          p.id === purchaseId ? { ...p, status: 'Применено' } : p
        ))
      })
      .catch(() => {})
  }, [])

  return (
    <div className="dashboard shop-page page-enter">
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
        {products.map((item, i) => (
          <article key={item.id} className="shop-card hover-lift" style={{ animationDelay: `${i * 50}ms` }}>
            <img className="shop-card__thumb" src={item.image ?? palmSky} alt="" width={300} height={184} loading="lazy" />
            <h2 className="shop-card__title">{item.title}</h2>
            <div className="shop-card__price">
              <span className="shop-card__coin" aria-hidden="true" />
              <span className="shop-card__price-value">{item.price}</span>
            </div>
            <div className="shop-card__actions">
              <button type="button" className="shop-card__buy btn-press" onClick={() => setShowPurchase(item.id)}>
                Купить
              </button>
              <button type="button" className="shop-card__detail btn-press" onClick={() => setShowDetail(item.id)}>
                ?
              </button>
            </div>
          </article>
        ))}
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
          {purchases.map(p => (
            <div key={p.id} className="shop-modal__purchase-item">
              <img src={palmSky} alt="" className="shop-modal__purchase-img" />
              <div className="shop-modal__purchase-info">
                <span className="shop-modal__purchase-name">{p.title}</span>
                <div className="shop-modal__price-tag shop-modal__price-tag--small">
                  <span className="shop-wallet__coin" aria-hidden="true" />
                  <span>{p.price}</span>
                </div>
              </div>
              <span className={`shop-modal__purchase-status${p.status === 'Применено' ? ' shop-modal__purchase-status--applied' : ''}`}>
                {p.status}
              </span>
              {p.status === 'Не применено' && (
                <button type="button" className="shop-modal__btn shop-modal__btn--small btn-press" onClick={() => handleApply(p.id)}>Применить</button>
              )}
            </div>
          ))}
        </div>
      </Modal>

      <Modal open={showHistory} onClose={() => setShowHistory(false)} title="История покупок" width="500px">
        <div className="shop-modal__history">
          {history.map((h, i) => (
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
    </div>
  )
}