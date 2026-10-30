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
 * Баллы и монеты везде показаны одинаковыми жетонами: фиолетовый
 * пиксель — рейтинг, жёлтая монета — кошелёк.
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
const coinsWord = (n: number) => plural(n, ['монета', 'монеты', 'монет'])
const pointsWord = (n: number) => plural(n, ['балл', 'балла', 'баллов'])
const range = (a: number, b: number) => (a === b ? fmt(a) : `${fmt(a)}–${fmt(b)}`)

const SECTIONS = [
  { id: 'rules-points', label: 'Баллы и монеты' },
  { id: 'rules-coins', label: 'Только монеты' },
  { id: 'rules-minus', label: 'Что снимают' },
]

/** Жетон рейтинга: фиолетовый, с пиксельным квадратом IThub. */
function Pts({ value, max, sign = '' }: { value: number; max?: boolean; sign?: string }) {
  return (
    <span className="rt rt--pts" aria-label={`${max ? 'до ' : ''}${sign}${fmt(value)} ${pointsWord(value)}`}>
      <i className="rt__px" aria-hidden="true" />
      <span aria-hidden="true">{max ? 'до ' : ''}{sign}{fmt(value)}</span>
    </span>
  )
}

/** Жетон монет: жёлтая монета, как в шапке у баланса. */
function Coins({ text, count, max }: { text?: string; count: number; max?: boolean }) {
  const shown = text ?? fmt(count)
  return (
    <span className="rt rt--coin" aria-label={`${max ? 'до ' : ''}${shown} ${coinsWord(count)}`}>
      <i className="rt__coin" aria-hidden="true" />
      <span aria-hidden="true">{max ? 'до ' : ''}{shown}</span>
    </span>
  )
}

function Pair({ cell, max }: { cell: Cell; max?: boolean }) {
  return (
    <span className="rt-pair">
      <Pts value={cell.rating} max={max} />
      <Coins count={cell.coins} max={max} />
    </span>
  )
}

function Row({ title, children }: { title: React.ReactNode; children: React.ReactNode }) {
  return (
    <li className="rules-row">
      <span className="rules-row__title">{title}</span>
      <span className="rules-row__value">{children}</span>
    </li>
  )
}

function RewardList({ items }: { items: Reward[] }) {
  return (
    <ul className="rules-rows">
      {items.map((item) => (
        <Row key={item.title} title={item.title}><Pair cell={item} /></Row>
      ))}
    </ul>
  )
}

/** Лесенка уровня: от колледжа до федерации — от одной клетки до четырёх. */
function Ladder({ step, of }: { step: number; of: number }) {
  return (
    <span className="rules-ladder" aria-hidden="true">
      {Array.from({ length: of }, (_, i) => (
        <i key={i} className={i <= step ? 'is-on' : ''} style={{ height: `${6 + i * 3}px` }} />
      ))}
    </span>
  )
}

/** Таблица «роль × уровень». На телефоне каждая роль — отдельный список уровней. */
function MatrixTable({ data, caption }: { data: Matrix; caption: string }) {
  const of = data.columns.length
  return (
    <table className="rules-table">
      <caption className="visually-hidden">{caption}</caption>
      <thead>
        <tr>
          <th scope="col"><span className="visually-hidden">Роль</span></th>
          {data.columns.map((col, i) => (
            <th key={col} scope="col">
              <Ladder step={i} of={of} />
              {col}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.rows.map((row) => (
          <tr key={row.title}>
            <th scope="row">{row.title}</th>
            {row.cells.map((cell, i) => (
              <td key={data.columns[i]}>
                <span className="rules-table__level" aria-hidden="true">
                  <Ladder step={i} of={of} />
                  {data.columns[i]}
                </span>
                <span className="visually-hidden">{data.columns[i]}: </span>
                <span className="rules-table__value">
                  <Pts value={cell.rating} />
                  <Coins count={cell.coins} />
                </span>
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Card({ title, who, wide, children }: { title: string; who?: string; wide?: boolean; children: React.ReactNode }) {
  return (
    <article className={`rules-card${wide ? ' rules-card--wide' : ''}`}>
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
        <p className="rules-hero__lead">За что начисляют и за что снимают. Цифры здесь те же, по которым идут начисления.</p>
        <div className="rules-legend">
          <div className="rules-legend__tile rules-legend__tile--pts">
            <i className="rt__px rt__px--big" aria-hidden="true" />
            <div>
              <b className="rules-legend__name">Баллы</b>
              <p className="rules-legend__text">Рейтинг: место в топе, статус и сравнение с другими. Растут за учёбу и активность.</p>
            </div>
          </div>
          <div className="rules-legend__tile rules-legend__tile--coin">
            <i className="rt__coin rt__coin--big" aria-hidden="true" />
            <div>
              <b className="rules-legend__name">Монеты</b>
              <p className="rules-legend__text">Кошелёк для магазина. За учёбу их столько же, сколько баллов, за квесты и нашивки — только монеты.</p>
            </div>
          </div>
        </div>
        <nav className="rules-jump" aria-label="Разделы правил">
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`} className="rules-jump__link">{s.label}</a>
          ))}
        </nav>
      </section>

      <section id="rules-points" className="rules-slot rules-slot--points">
        <header className="rules-slot__head">
          <h2 className="rules-slot__title">Баллы и монеты</h2>
          <p className="rules-slot__hint">Каждое начисление растит рейтинг и пополняет кошелёк.</p>
        </header>
        <div className="rules-grid">
          <div className="rules-stack">
            <Card title="Учёба, каждую неделю" who="Считается сама по данным LXP, приходит в понедельник за прошлую неделю.">
              <ul className="rules-rows">
                <Row title="Контрольные точки"><Pair cell={{ rating: academic.ct_weekly_max, coins: academic.ct_weekly_max }} max /></Row>
                <Row title="Посещаемость пар"><Pair cell={{ rating: academic.attendance_weekly_max, coins: academic.attendance_weekly_max }} max /></Row>
              </ul>
            </Card>

            <Card title="Проекты" who="Начисляет руководитель проекта после приёмки. Одна работа — одно начисление.">
              <RewardList items={data.projects} />
            </Card>
          </div>

          <Card title="Роли, каждую неделю" who="Роль назначает администрация. За неполную неделю — пропорционально дням.">
            <RewardList items={data.roles} />
          </Card>

          <Card wide title="Шефство" who="Каждый понедельник, автоматически.">
            <div className="rules-big">
              <span className="rules-big__num">{mentorship.share_percent}%</span>
              <span className="rules-big__text">
                от баллов, которые подшефный заработал сам за неделю, — но не больше{' '}
                <Pts value={mentorship.cap_per_mentee} /> за одного подшефного.
              </span>
            </div>
            <p className="rules-card__text">Шефство начинается, когда подшефный принял предложение.</p>
          </Card>

          <Card wide title="Мероприятия" who="Подтверждает ответственный за мероприятия. За одно мероприятие засчитывается одна роль — самая высокая.">
            <MatrixTable data={data.events} caption="Баллы и монеты за мероприятия по уровням" />
          </Card>

          <Card wide title="Олимпиады" who="Подтверждает ответственный. Если после участия засчитали победу, доплачивается разница.">
            <MatrixTable data={data.olympiads} caption="Баллы и монеты за олимпиады по уровням" />
          </Card>
        </div>
      </section>

      <section id="rules-coins" className="rules-slot rules-slot--coins">
        <header className="rules-slot__head">
          <h2 className="rules-slot__title">Только монеты</h2>
          <p className="rules-slot__hint">Рейтинг от этого не меняется — только кошелёк.</p>
        </header>
        <div className="rules-grid">
          <div className="rules-stack">
            <Card title="Квесты" who={`За квесты — не больше ${co.max_daily_quest_coins} ${coinsWord(co.max_daily_quest_coins)} в день.`}>
              <ul className="rules-rows">
                {co.quests.map((q) => (
                  <Row key={q.title} title={q.title}><Coins text={range(q.coins_min, q.coins_max)} count={q.coins_max} /></Row>
                ))}
              </ul>
            </Card>

            <Card title="Остальное">
              <ul className="rules-rows">
                {co.badges.coins_max > 0 && (
                  <Row title="Нашивка"><Coins text={range(co.badges.coins_min, co.badges.coins_max)} count={co.badges.coins_max} /></Row>
                )}
                <Row title="Получил респект"><Coins count={co.respect_coins} /></Row>
                <Row title="Выиграл дуэль — ставка соперника"><Coins count={co.duel_bet} /></Row>
              </ul>
            </Card>
          </div>

          <Card title="Царь горы" who="Начисляется каждый вечер по рейтингу на сайте.">
            <ul className="rules-rows">
              {king.top.map((c, i) => (
                <Row key={i} title={<><span className="rules-place">{i + 1}</span>место в общем рейтинге, за день</>}>
                  <Coins count={c} />
                </Row>
              ))}
              <Row title="Первый на своём курсе, за день"><Coins count={king.course_leader} /></Row>
              <Row title={`${king.streak_days} дней подряд первым — и нашивка «Царь горы»`}><Coins count={king.streak_reward} /></Row>
              <Row title="Сместил вчерашнего лидера"><Coins count={king.dethrone} /></Row>
              <Row title="Твой отряд — лидер недели"><Coins count={king.squad_leader} /></Row>
            </ul>
          </Card>
        </div>
      </section>

      <section id="rules-minus" className="rules-slot rules-slot--minus">
        <header className="rules-slot__head">
          <h2 className="rules-slot__title">Что снимают</h2>
          <p className="rules-slot__hint">Только рейтинг — монеты не списываются.</p>
        </header>
        <div className="rules-penalty">
          <div className="rules-penalty__main">
            <span className="rules-penalty__num">−{fmt(penalties.per_missed_lesson)}</span>
            <span className="rules-penalty__label">{pointsWord(penalties.per_missed_lesson)} за каждую пропущенную пару</span>
          </div>
          <div className="rules-penalty__cap">
            <span className="rules-penalty__cap-num">−{fmt(penalties.daily_max)}</span>
            <span className="rules-penalty__label">не больше за день</span>
          </div>
          <p className="rules-penalty__note">Опоздания баллы не снимают — только мешают квестам «без опозданий».</p>
        </div>
      </section>

      <p className="rules-foot">
        По Положению о системе рейтинга, редакция {data.polozhenie.version} от{' '}
        {new Date(data.polozhenie.date).toLocaleDateString('ru-RU')}. Если начисление кажется неверным,
        напиши своему куратору.
      </p>
    </div>
  )
}
