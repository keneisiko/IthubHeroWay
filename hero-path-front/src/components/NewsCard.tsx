import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api'
import PixelText from './PixelText'
import { formatDateRu } from '../lib/apiData'
import '../styles/news.css'

interface NewsItem {
  id: number
  title: string
  body: string
  link: string
  published_at: string
}

/** Новости платформы на главной. Публикуются в админке, там же — рассылка в бот. */
export default function NewsCard() {
  const [items, setItems] = useState<NewsItem[] | null>(null)

  useEffect(() => {
    let alive = true
    api.get<NewsItem[]>('/api/v1/news/')
      .then((res) => { if (alive) setItems(res.data) })
      .catch(() => { if (alive) setItems([]) })
    return () => { alive = false }
  }, [])

  return (
    <section className="news-card dash-in" style={{ animationDelay: '300ms' }}>
      <h3 className="section-title"><PixelText text="Новости" /></h3>
      {items === null ? (
        <p className="loading-text">Загружаем…</p>
      ) : items.length === 0 ? (
        <p className="loading-text">Новостей пока нет</p>
      ) : (
        <div className="news">
          {items.map((item) => (
            <article key={item.id} className="news__item">
              <div className="news__head">
                <h4 className="news__title">{item.title}</h4>
                <time className="news__date" dateTime={item.published_at}>{formatDateRu(item.published_at)}</time>
              </div>
              <p className="news__body">{item.body}</p>
              {item.link.startsWith('/') && (
                <Link to={item.link} className="news__more">Подробнее →</Link>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
