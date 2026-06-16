import { useState, useRef, useEffect } from 'react'
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
  const [pillStyle, setPillStyle] = useState<{ left: number; width: number }>({ left: 0, width: 50 })

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

  return (
    <div className="dashboard shop-page page-enter">
      <div className="shop-page__band shop-page__band--tabs">
        <nav className="shop-tabs" aria-label="Категории магазина">
          <div className="shop-tabs__labels" role="tablist" ref={tabsRef}>
            {TABS.map((label, index) => (
              <button
                key={label} type="button" role="tab"
                aria-selected={activeTab === index}
                className={`shop-tab ${activeTab === index ? 'shop-tab--active' : ''}`}
                onClick={() => setActiveTab(index)}
                ref={el => { tabRefs.current[index] = el }}
              >{label}</button>
            ))}
          </div>
          <div className="shop-tabs__track" aria-hidden="true">
            <span className="shop-tabs__line" />
            <div className="shop-tabs__pill" style={{ left: `${pillStyle.left}px` }} />
          </div>
        </nav>
      </div>

      <div className="shop-page__band shop-page__band--split">
        <div className="shop-purchases-frame">
          <button type="button" className="shop-purchases-btn" onClick={() => setShowPurchases(true)}>
            <span className="shop-purchases-btn__label">Мои покупки</span>
          </button>
        </div>
        <div className="shop-page__split-spacer" aria-hidden="true" />
        <section className="shop-wallet" aria-label="Баланс монет">
          <div className="shop-wallet__stack">
            <p className="shop-wallet__label">Сколько монет у пользователя:</p>
            <div className="shop-wallet__amount">
              <span className="shop-wallet__coin" aria-hidden="true" />
              <span className="shop-wallet__value">{coins}</span>
            </div>
          </div>
          <button type="button" className="shop-wallet__history" onClick={() => setShowHistory(true)}>
            <span className="shop-wallet__history-label">История покупок</span>
          </button>
        </section>
      </div>

      <div className="shop-grid">
        {products.map(item => (
          <article key={item.id} className="shop-card hover-lift">
            <img className="shop-card__thumb" src={item.image ?? palmSky} alt="" width={300} height={184} loading="lazy" />
            <h2 className="shop-card__title">{item.title}</h2>
            <div className="shop-card__price">
              <span className="shop-card__coin" aria-hidden="true" />
              <span className="shop-card__price-value">{item.price}</span>
            </div>
            <div style={{ display: 'flex', gap: '8px', padding: '0 16px 16px' }}>
              <button type="button" className="shop-card__buy" style={{ flex: 1 }} onClick={() => setShowPurchase(item.id)}>
                Купить
              </button>
              <button
                type="button" onClick={() => setShowDetail(item.id)}
                style={{ width: '48px', height: '48px', borderRadius: '12px', border: '3px solid #9a33f4', background: 'transparent', color: '#9a33f4', cursor: 'pointer', fontSize: '20px', fontWeight: 700 }}
              >?</button>
            </div>
          </article>
        ))}
      </div>

      {showPurchase !== null && (
        <div className="overlay" onClick={() => setShowPurchase(null)}>
          <div className="popup" onClick={e => e.stopPropagation()} style={{ background: '#f5f5f5', borderRadius: '12px', border: '4px solid #9a33f4', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '20px', width: '460px', maxWidth: '90vw', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', textAlign: 'center' }}>
            <span style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '28px', color: '#9a33f4' }}>Подтвердите покупку</span>
            <span style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '20px', color: '#121212' }}>{selectedProduct?.title}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#121212', borderRadius: '12px', padding: '8px 20px' }}>
              <span style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#ffd900', display: 'inline-block' }} />
              <span style={{ fontFamily: 'TT Firs Neue, sans-serif', fontSize: '24px', fontWeight: 700, color: '#ffd900' }}>{selectedProduct?.price}</span>
            </div>
            <div style={{ display: 'flex', gap: '12px', width: '100%' }}>
              <button type="button" onClick={() => setShowPurchase(null)} style={{ flex: 1, height: '48px', borderRadius: '48px', border: '4px solid #121212', background: 'transparent', color: '#121212', fontFamily: 'Montserrat, sans-serif', fontWeight: 700, fontSize: '20px', cursor: 'pointer' }}>Отмена</button>
              <button type="button" onClick={() => setShowPurchase(null)} style={{ flex: 1, height: '48px', borderRadius: '48px', border: '4px solid #f5f5f5', background: '#9a33f4', color: '#f5f5f5', fontFamily: 'Montserrat, sans-serif', fontWeight: 700, fontSize: '20px', cursor: 'pointer' }}>Купить</button>
            </div>
          </div>
        </div>
      )}

      {showPurchases && (
        <div className="overlay" onClick={() => setShowPurchases(false)}>
          <div className="popup" onClick={e => e.stopPropagation()} style={{ background: '#f5f5f5', borderRadius: '24px', border: '4px solid #9a33f4', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '24px', width: '600px', maxWidth: '90vw', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h2 style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '28px', color: '#9a33f4', margin: 0 }}>Мои покупки</h2>
            {purchases.map(p => (
              <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: '16px', background: '#f5f5f5', borderRadius: '8px', border: '4px solid #9a33f4', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '14px' }}>
                <img src={palmSky} alt="" style={{ width: '60px', height: '60px', borderRadius: '4px', objectFit: 'cover' }} />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '20px', color: '#121212' }}>{p.title}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ width: '18px', height: '18px', borderRadius: '50%', background: '#ffd900', display: 'inline-block' }} />
                    <span style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '16px', color: '#ffd900' }}>{p.price}</span>
                  </div>
                </div>
                <span style={{ background: p.status === 'Применено' ? '#9a33f4' : '#121212', borderRadius: '48px', padding: '4px 16px', color: '#f5f5f5', fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '14px' }}>{p.status}</span>
                {p.status === 'Не применено' && (
                  <button style={{ background: '#9a33f4', borderRadius: '4px', padding: '8px 16px', border: 'none', color: '#f5f5f5', fontFamily: 'Montserrat, sans-serif', fontWeight: 700, fontSize: '16px', cursor: 'pointer' }}>Применить</button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {showDetail !== null && (
        <div className="overlay" onClick={() => setShowDetail(null)}>
          <div className="popup" onClick={e => e.stopPropagation()} style={{ background: '#f5f5f5', borderRadius: '24px', border: '4px solid #9a33f4', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '20px', width: '600px', maxWidth: '90vw', display: 'flex', gap: '20px' }}>
            <img src={palmSky} alt="" style={{ width: '240px', height: '240px', borderRadius: '12px', objectFit: 'cover', flexShrink: 0 }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
              <h3 style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '28px', color: '#9a33f4', margin: 0 }}>{selectedProduct?.title}</h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#121212', borderRadius: '12px', padding: '8px 16px', width: 'fit-content' }}>
                <span style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#ffd900', display: 'inline-block' }} />
                <span style={{ fontFamily: 'TT Firs Neue, sans-serif', fontSize: '24px', fontWeight: 700, color: '#ffd900' }}>{selectedProduct?.price}</span>
              </div>
              <span style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '22px', color: '#121212' }}>Описание:</span>
              <p style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 500, fontSize: '15px', color: '#292929', lineHeight: 1.3, margin: 0 }}>{selectedProduct?.desc}</p>
              <button type="button" onClick={() => { setShowDetail(null); setShowPurchase(showDetail) }} style={{ background: '#9a33f4', height: '48px', borderRadius: '16px', border: '4px solid #f5f5f5', padding: '3px 24px', fontFamily: 'Montserrat, sans-serif', fontWeight: 700, fontSize: '22px', color: '#f5f5f5', cursor: 'pointer', marginTop: 'auto' }}>Купить</button>
            </div>
          </div>
        </div>
      )}

      {showHistory && (
        <div className="overlay" onClick={() => setShowHistory(false)}>
          <div className="popup" onClick={e => e.stopPropagation()} style={{ background: '#f5f5f5', borderRadius: '24px', border: '4px solid #9a33f4', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '24px', width: '500px', maxWidth: '90vw', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <h2 style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '28px', color: '#9a33f4', margin: 0 }}>История покупок</h2>
            {history.map((h, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', borderRadius: '12px', border: '3px solid #9a33f4', background: '#fff' }}>
                <div>
                  <div style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '16px', color: '#121212' }}>{h.name}</div>
                  <div style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '14px', color: '#848484' }}>{h.date}</div>
                </div>
                <span style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 700, fontSize: '18px', color: h.amount.startsWith('+') ? '#6cd63e' : '#fd4e4e' }}>{h.amount}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}