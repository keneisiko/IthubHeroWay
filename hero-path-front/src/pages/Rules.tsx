import { useCallback, useEffect, useState } from 'react'
import api from '../api'
import BrandLoader from '../components/BrandLoader'
import LoadError from '../components/LoadError'
import PixelText from '../components/PixelText'
import { plural } from '../lib/plural'
import '../styles/rules.css'

/*
 * «Правила»: за что даются баллы и монеты. Цифры приходят с сервера —
 * из тех же настроек, по которым идут начисления, поэтому страница не
 * расходится с тем, что студент получает на самом деле.
 */

interface Reward { title: string; rating: number; coins: number }
interface Cell { rating: number; coins: number }
interface Matrix { columns: string[]; rows: { title: string; cells: Cell[] }[] }
interface QuestRange { title: string; coins_min: number; coins_max: number }

interface RulesData {
  polozhenie: { version: string; date: string }
  academic: { ct_weekly_max: number; attendance_weekly_max: number }
  roles: Reward[]
  events: Matrix
  olympiads: Matrix
  projects: Reward[]
  mentorship: { share_percent: number; cap_per_mentee: number }
  penalties: { per_missed_lesson: number; daily_max: number }
  coins_only: {
    quests: QuestRange[]
    max_daily_quest_coins: number
    badges: { coins_min: number; coins_max: number }
    respect_coins: number
    duel_bet: number
    king: {
      top: number[]
      course_leader: number
      streak_days: number
      streak_reward: number
      dethrone: number
      squad_leader: number
    }
  }
}

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/, '').replace('.', ','))
const coins = (n: number) => `${fmt(n)} ${plural(n, ['монета', 'монеты', 'монет'])}`
const points = (n: number) => `${fmt(n)} ${plural(n, ['балл', 'балла', 'баллов'])}`
const range = (a: number, b: number) => (a === b ? fmt(a) : `${fmt(a)}–${fmt(b)}`)

function Pair({ cell }: { cell: Cell }) {
  return (
    <span className="rules-pair">
      <b>{fmt(cell.rating)}</b>
      <span className="rules-pair__coins">{fmt(cell.coins)} мон.</span>
    </span>
  )
}

function RewardList({ items }: { items: Reward[] }) {
  return (
    <ul className="rules-list">
      {items.map((item) => (
        <li key={item.title} className="rules-list__row">
          <span className="rules-list__title">{item.title}</span>
          <Pair cell={item} />
        </li>
      ))}
    </ul>
  )
}

/** Таблица «роль × уровень». На телефоне каждая строка — отдельный список. */
function MatrixTable({ data, caption }: { data: Matrix; caption: string }) {
  return (
    <table className="rules-table">
      <caption className="visually-hidden">{caption}</caption>
      <thead>
        <tr>
          <th scope="col" />
          {data.columns.map((col) => <th key={col} scope="col">{col}</th>)}
        </tr>
      </thead>
      <tbody>
        {data.rows.map((row) => (
          <tr key={row.title}>
            <th scope="row">{row.title}</th>
            {row.cells.map((cell, i) => (
              <td key={data.columns[i]} data-label={data.columns[i]}>
                <Pair cell={cell} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Card({ title, who, children }: { title: string; who?: string; children: React.ReactNode }) {
  return (
    <article className="rules-card">
      <h3 className="rules-card__title">{title}</h3>
      {children}
      {who && <p className="rules-card__who">{who}</p>}
    </article>
  )
}

export default function Rules() {
  const [data, setData] = useState<RulesData | null>(null)
  const [loadError, setLoadError] = useState(false)

  const load = useCallback(() => {
    api.get<RulesData>('/api/v1/rules/')
      .then((res) => { setData(res.data); setLoadError(false) })
      .catch(() => setLoadError(true))
  }, [])

  useEffect(() => { load() }, [load])

  if (loadError) return <LoadError className="rules rules--state" onRetry={load} />
  if (!data) {
    return (
      <div className="rules">
        <BrandLoader label="Загружаем правила" />
      </div>
    )
  }

  const { academic, coins_only: co, penalties, mentorship } = data
  const king = co.king

  return (
    <div className="rules page-enter">
      <section className="rules-hero">
        <h1 className="rules-hero__title"><PixelText text="Правила" /></h1>
        <div className="rules-hero__split">
          <div className="rules-hero__item">
            <span className="rules-hero__tag rules-hero__tag--rating">Баллы</span>
            Это рейтинг: твоё место в топе, статус и сравнение с другими. Растут за учёбу и активность.
          </div>
          <div className="rules-hero__item">
            <span className="rules-hero__tag rules-hero__tag--coins">Монеты</span>
            Это кошелёк для магазина. За учёбу их дают столько же, сколько баллов, а за квесты и нашивки — только монеты.
          </div>
        </div>
      </section>

      <section className="rules-slot">
        <h2 className="rules-slot__title">За что дают баллы</h2>
        <p className="rules-slot__hint">В таблицах: <b>баллы</b> и монеты за одно начисление.</p>
        <div className="rules-grid">
          <Card title="Учёба — каждую неделю" who="Считается сама по данным LXP, начисляется в понедельник за прошлую неделю.">
            <ul className="rules-list">
              <li className="rules-list__row">
                <span className="rules-list__title">Контрольные точки</span>
                <span className="rules-pair"><b>до {fmt(academic.ct_weekly_max)}</b></span>
              </li>
              <li className="rules-list__row">
                <span className="rules-list__title">Посещаемость пар</span>
                <span className="rules-pair"><b>до {fmt(academic.attendance_weekly_max)}</b></span>
              </li>
            </ul>
            <p className="rules-card__note">Монет — столько же, сколько баллов.</p>
          </Card>

          <Card title="Регулярные роли — каждую неделю" who="Роль назначает администрация. За неполную неделю — пропорционально дням.">
            <RewardList items={data.roles} />
          </Card>

          <Card title="Проекты" who="Начисляет руководитель проекта после приёмки работы. Одна работа — один раз.">
            <RewardList items={data.projects} />
          </Card>

          <Card title="Шефство" who="Каждый понедельник, автоматически.">
            <p className="rules-card__text">
              Наставник получает {mentorship.share_percent}% от баллов, которые подшефный заработал сам за неделю,
              но не больше {points(mentorship.cap_per_mentee)} за одного подшефного. Шефство начинается, когда
              подшефный принял предложение.
            </p>
          </Card>
        </div>

        <Card title="Мероприятия" who="Подтверждает ответственный за мероприятия. За одно мероприятие — одна, наивысшая роль.">
          <MatrixTable data={data.events} caption="Баллы и монеты за мероприятия" />
        </Card>
        <Card title="Олимпиады" who="Подтверждает ответственный. Победа после засчитанного участия доплачивается разницей.">
          <MatrixTable data={data.olympiads} caption="Баллы и монеты за олимпиады" />
        </Card>
      </section>

      <section className="rules-slot rules-slot--coins">
        <h2 className="rules-slot__title">За что дают только монеты</h2>
        <div className="rules-grid">
          <Card title="Квесты" who={`За квесты — не больше ${coins(co.max_daily_quest_coins)} в день.`}>
            <ul className="rules-list">
              {co.quests.map((q) => (
                <li key={q.title} className="rules-list__row">
                  <span className="rules-list__title">{q.title}</span>
                  <span className="rules-pair"><b>{range(q.coins_min, q.coins_max)}</b> мон.</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="Царь горы" who="Начисляется каждый вечер по рейтингу на сайте.">
            <ul className="rules-list">
              {king.top.map((c, i) => (
                <li key={i} className="rules-list__row">
                  <span className="rules-list__title">{i + 1}-е место в общем рейтинге — в день</span>
                  <span className="rules-pair"><b>{fmt(c)}</b> мон.</span>
                </li>
              ))}
              <li className="rules-list__row">
                <span className="rules-list__title">1-е место на своём курсе — в день</span>
                <span className="rules-pair"><b>{fmt(king.course_leader)}</b> мон.</span>
              </li>
              <li className="rules-list__row">
                <span className="rules-list__title">{king.streak_days} дней подряд первым — и нашивка «Царь горы»</span>
                <span className="rules-pair"><b>{fmt(king.streak_reward)}</b> мон.</span>
              </li>
              <li className="rules-list__row">
                <span className="rules-list__title">Сместил вчерашнего лидера</span>
                <span className="rules-pair"><b>{fmt(king.dethrone)}</b> мон.</span>
              </li>
              <li className="rules-list__row">
                <span className="rules-list__title">Твой отряд — лидер недели</span>
                <span className="rules-pair"><b>{fmt(king.squad_leader)}</b> мон.</span>
              </li>
            </ul>
          </Card>
          <Card title="Остальное">
            <ul className="rules-list">
              {co.badges.coins_max > 0 && (
                <li className="rules-list__row">
                  <span className="rules-list__title">Нашивки</span>
                  <span className="rules-pair"><b>{range(co.badges.coins_min, co.badges.coins_max)}</b> мон.</span>
                </li>
              )}
              <li className="rules-list__row">
                <span className="rules-list__title">Получил респект</span>
                <span className="rules-pair"><b>{fmt(co.respect_coins)}</b> мон.</span>
              </li>
              <li className="rules-list__row">
                <span className="rules-list__title">Выиграл дуэль — ставка соперника</span>
                <span className="rules-pair"><b>{fmt(co.duel_bet)}</b> мон.</span>
              </li>
            </ul>
          </Card>
        </div>
      </section>

      <section className="rules-slot rules-slot--minus">
        <h2 className="rules-slot__title">За что снимают</h2>
        <Card title="Пропуск пары" who="Только рейтинг, монеты не списываются.">
          <p className="rules-card__text">
            −{points(penalties.per_missed_lesson)} за каждую пропущенную пару, но не больше −{points(penalties.daily_max)} в день.
            Опоздания баллы не снимают — только мешают квестам «без опозданий».
          </p>
        </Card>
      </section>

      <p className="rules-foot">
        По Положению о системе рейтинга, редакция {data.polozhenie.version} от{' '}
        {new Date(data.polozhenie.date).toLocaleDateString('ru-RU')}. Если начисление кажется неверным,
        напиши своему куратору.
      </p>
    </div>
  )
}
