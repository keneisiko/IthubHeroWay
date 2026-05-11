import { useState } from 'react'
import palmSky from '../assets/shop/palm-sky.png'

const TABS = ['Кастомизация', 'Привилегии', 'Мерч', 'Статусные'] as const

const PRODUCTS = Array.from({ length: 9 }, (_, i) => ({ id: i + 1, title: 'Название', price: '9.99' }))

export default function Shop() {
  const [activeTab, setActiveTab] = useState(0)

  return (
    <div className="dashboard shop-page">
      <div className="shop-page__band shop-page__band--tabs">
        <nav className="shop-tabs" aria-label="Категории магазина">
          <div className="shop-tabs__labels" role="tablist">
            {TABS.map((label, index) => (
              <button
                key={label}
                type="button"
                role="tab"
                aria-selected={activeTab === index}
                className={`shop-tab ${activeTab === index ? 'shop-tab--active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="shop-tabs__track" aria-hidden="true">
            <span className="shop-tabs__line" />
            <div className="shop-tabs__pill" style={{ gridColumn: activeTab + 1 }} />
          </div>
        </nav>
      </div>

      <div className="shop-page__band shop-page__band--split">
        <div className="shop-purchases-frame">
          <button type="button" className="shop-purchases-btn">
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
          <button type="button" className="shop-wallet__history">
            <span className="shop-wallet__history-label">История покупок</span>
          </button>
        </section>
      </div>

      <div className="shop-grid">
        {PRODUCTS.map((item) => (
          <article key={item.id} className="shop-card">
            <img className="shop-card__thumb" src={palmSky} alt="" width={300} height={184} loading="lazy" />
            <h2 className="shop-card__title">{item.title}</h2>
            <div className="shop-card__price">
              <span className="shop-card__coin" aria-hidden="true" />
              <span className="shop-card__price-value">{item.price}</span>
            </div>
            <button type="button" className="shop-card__buy">
              Купить
            </button>
          </article>
        ))}
      </div>
    </div>
  )
}
