import { useState, useRef, useEffect } from 'react'
import palmSky from '../assets/shop/palm-sky.png'

const TABS = ['Кастомизация', 'Привилегии', 'Мерч', 'Статусные'] as const

const PRODUCTS = Array.from({ length: 9 }, (_, i) => ({
  id: i + 1,
  title: 'Название',
  price: '9.99',
  desc: 'Описание товара. Краткое описание для демонстрации MVP функционала магазина.',
}))

const PURCHASES = [
  { id: 1, title: 'Название', price: '9.99', status: 'Применено', image: palmSky },
  { id: 2, title: 'Название', price: '4.50', status: 'Не применено', image: palmSky },
]

export default function Shop() {
  const [activeTab, setActiveTab] = useState(0)
  const [showPurchase, setShowPurchase] = useState<number | null>(null)
  const [showPurchases, setShowPurchases] = useState(false)
  const [showDetail, setShowDetail] = useState<number | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const tabsRef = useRef<HTMLDivElement>(null)
  const tabRefs = useRef<Record<number, HTMLButtonElement | null>>({})
  const [pillStyle, setPillStyle] = useState<{ left: number; width: number }>({ left: 0, width: 50 })

  useEffect(() => {
    const container = tabsRef.current
    const activeBtn = tabRefs.current[activeTab]
    if (!container || !activeBtn) return
    const containerRect = container.getBoundingClientRect()
    const btnRect = activeBtn.getBoundingClientRect()
    setPillStyle({
      left: btnRect.left - containerRect.left + (btnRect.width - 50) / 2,
      width: 50,
    })
  }, [activeTab])

  return (
    <div className="dashboard shop-page page-enter">
      <div className="shop-page__band shop-page__band--tabs">
        <nav className="shop-tabs" aria-label="Категории магазина">
          <div className="shop-tabs__labels" role="tablist" ref={tabsRef}>
            {TABS.map((label, index) => (
              <button
                key={label}
                type="button"
                role="tab"
                aria-selected={activeTab === index}
                className={`shop-tab ${activeTab === index ? 'shop-tab--active' : ''}`}
                onClick={() => setActiveTab(index)}
                ref={(el) => { tabRefs.current[index] = el }}
              >
                {label}
              </button>
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
              <span className="shop-wallet__value">9.99</span>
            </div>
          </div>
          <button type="button" className="shop-wallet__history" onClick={() => setShowHistory(true)}>
            <span className="shop-wallet__history-label">История покупок</span>
          </button>
        </section>
      </div>

      <div className="shop-grid">
        {PRODUCTS.map((item) => (
          <article key={item.id} className="shop-card hover-lift">
            <img className="shop-card__thumb" src={palmSky} alt="" width={300} height={184} loading="lazy" />
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
                type="button"
                onClick={() => setShowDetail(item.id)}
                style={{
                  width: '48px', height: '48px', borderRadius: '12px', border: '3px solid #9a33f4',
                  background: 'transparent', color: '#9a33f4', cursor: 'pointer', fontSize: '20px',
                  fontWeight: 700, transition: 'background 0.2s',
                }}
              >
                ?
              </button>
            </div>
          </article>
        ))}
      </div>

      {/* Purchase confirmation popup */}
      {showPurchase !== null && (
        <div className="overlay" onClick={() => setShowPurchase(null)}>
          <div className="popup" onClick={(e) => e.stopPropagation()} style={{
            background: '#f5f5f5', borderRadius: '12px', border: '4px solid #9a33f4',
            boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '20px',
            width: '460px', maxWidth: '90vw', display: 'flex', flexDirection: 'column',
            alignItems: 'center', gap: '16px', textAlign: 'center',
          }}>
            <span style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '28px', color: '#9a33f4' }}>
              Подтвердите покупку
            </span>
            <span style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '20px', color: '#121212' }}>
              {PRODUCTS.find((p) => p.id === showPurchase)?.title}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#121212', borderRadius: '12px', padding: '8px 20px' }}>
              <span style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#ffd900', display: 'inline-block' }} />
              <span style={{ fontFamily: 'TT Firs Neue, sans-serif', fontSize: '24px', fontWeight: 700, color: '#ffd900' }}>
                {PRODUCTS.find((p) => p.id === showPurchase)?.price}
              </span>
            </div>
            <div style={{ display: 'flex', gap: '12px', width: '100%' }}>
              <button
                type="button"
                onClick={() => setShowPurchase(null)}
                style={{
                  flex: 1, height: '48px', borderRadius: '48px', border: '4px solid #121212',
                  background: 'transparent', color: '#121212', fontFamily: 'Montserrat, sans-serif',
                  fontWeight: 700, fontSize: '20px', cursor: 'pointer', transition: 'background 0.2s',
                }}
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={() => setShowPurchase(null)}
                style={{
                  flex: 1, height: '48px', borderRadius: '48px', border: '4px solid #f5f5f5',
                  background: '#9a33f4', color: '#f5f5f5', fontFamily: 'Montserrat, sans-serif',
                  fontWeight: 700, fontSize: '20px', cursor: 'pointer',
                  boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', transition: 'opacity 0.2s',
                }}
              >
                Купить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* My purchases modal */}
      {showPurchases && (
        <div className="overlay" onClick={() => setShowPurchases(false)}>
          <div className="popup" onClick={(e) => e.stopPropagation()} style={{
            background: '#f5f5f5', borderRadius: '24px', border: '4px solid #9a33f4',
            boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '24px',
            width: '600px', maxWidth: '90vw', display: 'flex', flexDirection: 'column', gap: '16px',
          }}>
            <h2 style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '28px', color: '#9a33f4', margin: 0 }}>
              Мои покупки
            </h2>
            {PURCHASES.map((p) => (
              <div key={p.id} style={{
                display: 'flex', alignItems: 'center', gap: '16px',
                background: '#f5f5f5', borderRadius: '8px', border: '4px solid #9a33f4',
                boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '14px',
              }}>
                <img src={p.image} alt="" style={{ width: '60px', height: '60px', borderRadius: '4px', objectFit: 'cover' }} />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '20px', color: '#121212' }}>
                    {p.title}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ width: '18px', height: '18px', borderRadius: '50%', background: '#ffd900', display: 'inline-block' }} />
                    <span style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '16px', color: '#ffd900' }}>
                      {p.price}
                    </span>
                  </div>
                </div>
                <span style={{
                  background: p.status === 'Применено' ? '#9a33f4' : '#121212',
                  borderRadius: '48px', padding: '4px 16px', color: '#f5f5f5',
                  fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '14px',
                }}>
                  {p.status}
                </span>
                {p.status === 'Не применено' && (
                  <button style={{
                    background: '#9a33f4', borderRadius: '4px', padding: '8px 16px',
                    border: 'none', color: '#f5f5f5', fontFamily: 'Montserrat, sans-serif',
                    fontWeight: 700, fontSize: '16px', cursor: 'pointer',
                  }}>
                    Применить
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detail popup */}
      {showDetail !== null && (
        <div className="overlay" onClick={() => setShowDetail(null)}>
          <div className="popup" onClick={(e) => e.stopPropagation()} style={{
            background: '#f5f5f5', borderRadius: '24px', border: '4px solid #9a33f4',
            boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '20px',
            width: '600px', maxWidth: '90vw', display: 'flex', gap: '20px',
          }}>
            <img src={palmSky} alt="" style={{ width: '240px', height: '240px', borderRadius: '12px', objectFit: 'cover', flexShrink: 0 }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
              <h3 style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '28px', color: '#9a33f4', margin: 0 }}>
                {PRODUCTS.find((p) => p.id === showDetail)?.title}
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#121212', borderRadius: '12px', padding: '8px 16px', width: 'fit-content' }}>
                <span style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#ffd900', display: 'inline-block' }} />
                <span style={{ fontFamily: 'TT Firs Neue, sans-serif', fontSize: '24px', fontWeight: 700, color: '#ffd900' }}>
                  {PRODUCTS.find((p) => p.id === showDetail)?.price}
                </span>
              </div>
              <span style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '22px', color: '#121212' }}>Описание:</span>
              <p style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 500, fontSize: '15px', color: '#292929', lineHeight: 1.3, letterSpacing: '1.35px', margin: 0 }}>
                {PRODUCTS.find((p) => p.id === showDetail)?.desc}
              </p>
              <button type="button" onClick={() => { setShowDetail(null); setShowPurchase(showDetail) }} style={{
                background: '#9a33f4', height: '48px', borderRadius: '16px',
                border: '4px solid #f5f5f5', boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)',
                padding: '3px 24px', fontFamily: 'Montserrat, sans-serif', fontWeight: 700,
                fontSize: '22px', color: '#f5f5f5', cursor: 'pointer', transition: 'opacity 0.2s',
                marginTop: 'auto',
              }}>
                Купить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Purchase history modal */}
      {showHistory && (
        <div className="overlay" onClick={() => setShowHistory(false)}>
          <div className="popup" onClick={(e) => e.stopPropagation()} style={{
            background: '#f5f5f5', borderRadius: '24px', border: '4px solid #9a33f4',
            boxShadow: '25px 25px 20px -20px rgba(0,0,0,0.45)', padding: '24px',
            width: '500px', maxWidth: '90vw', display: 'flex', flexDirection: 'column', gap: '12px',
          }}>
            <h2 style={{ fontFamily: 'TT Firs Neue, sans-serif', fontWeight: 700, fontSize: '28px', color: '#9a33f4', margin: 0 }}>
              История покупок
            </h2>
            {[
              { name: 'Название', amount: '-9.99', date: '12 мая 2026' },
              { name: 'Название', amount: '-4.50', date: '10 мая 2026' },
              { name: 'Награда за квест', amount: '+15.00', date: '8 мая 2026' },
            ].map((h, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '12px', borderRadius: '12px', border: '3px solid #9a33f4',
                background: '#fff',
              }}>
                <div>
                  <div style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '16px', color: '#121212' }}>{h.name}</div>
                  <div style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '14px', color: '#848484' }}>{h.date}</div>
                </div>
                <span style={{
                  fontFamily: 'Montserrat, sans-serif', fontWeight: 700, fontSize: '18px',
                  color: h.amount.startsWith('+') ? '#6cd63e' : '#fd4e4e',
                }}>
                  {h.amount}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
