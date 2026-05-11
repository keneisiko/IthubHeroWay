import userAvatar from '../assets/branding/user-avatar.png'

const members = [1, 2, 3, 4].map((i) => ({ id: i }))

export default function Squads() {
  return (
    <div className="dashboard squad-page">
      <div className="squad-page__top">
        <section className="squad-my" aria-labelledby="squad-my-title">
          <div className="squad-my__title-row">
            <h2 id="squad-my-title" className="squad-my__title">
              Название отряда
            </h2>
            <div className="squad-my__course">
              <span>Курс: 2</span>
            </div>
          </div>

          <dl className="squad-my__stats">
            <div className="squad-my__row">
              <dt className="squad-my__label">Рейтинг:</dt>
              <dd>
                <span className="squad-pill squad-pill--dark squad-pill--firs">199</span>
              </dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Агентов:</dt>
              <dd>
                <span className="squad-pill squad-pill--light">19</span>
              </dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Дельта роста за неделю:</dt>
              <dd>
                <span className="squad-pill squad-pill--dark squad-pill--delta">
                  +47
                  <svg
                    className="squad-pill__arrow"
                    width="14"
                    height="7"
                    viewBox="0 0 14 7"
                    fill="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M2 6L7 1L12 6"
                      stroke="#6CD63E"
                      strokeWidth="4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
              </dd>
            </div>
            <div className="squad-my__row">
              <dt className="squad-my__label">Место в общем рейтинге отрядов:</dt>
              <dd>
                <span className="squad-pill squad-pill--dark squad-pill--wide">3 место из 18</span>
              </dd>
            </div>
          </dl>
        </section>

        <div className="squad-page__right">
          <section className="squad-bonus" aria-label="Прогресс командного бонуса">
            <p className="squad-bonus__lead">80% отряда выполнили еженедельный квест</p>
            <div className="squad-bonus__chip squad-bonus__chip--purple">
              При 80% - вы получите +5 монет в пятницу
            </div>
            <div className="squad-bonus__chip squad-bonus__chip--dark">
              <span className="squad-bonus__chip-num">12</span>
              <span> из 15 агентов выполнили</span>
            </div>

            <div className="squad-bonus__progress-block">
              <p className="squad-bonus__hint">До бонуса осталось 3 человека</p>
              <div className="squad-bonus__progress">
                <span className="squad-bonus__dot squad-bonus__dot--start" aria-hidden="true" />
                <div className="squad-bonus__track">
                  <div className="squad-bonus__track-slot">
                    <div className="squad-bonus__fill" style={{ width: '80%' }} />
                  </div>
                </div>
                <span className="squad-bonus__dot squad-bonus__dot--end" aria-hidden="true" />
              </div>
            </div>
          </section>

          <section className="squad-actions" aria-label="Действия отряда">
            <div className="squad-actions__coins">
              <span className="squad-actions__coins-text">В этом месяце отряд получил</span>
              <span className="squad-actions__coins-badge">340</span>
              <span className="squad-actions__coins-text">монет</span>
            </div>
            <button type="button" className="squad-actions__btn squad-actions__btn--share">
              поделиться
            </button>
            <button type="button" className="squad-actions__btn squad-actions__btn--invite">
              пригласить
            </button>
          </section>
        </div>
      </div>

      <section className="squad-members" aria-labelledby="squad-members-title">
        <div className="squad-members__head">
          <h2 id="squad-members-title" className="squad-members__title">
            Участники отряда
          </h2>
          <button type="button" className="squad-members__sort">
            Сортировка
          </button>
        </div>

        <div className="squad-members__search">
          <span>Поиск</span>
          <svg viewBox="0 0 26 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="10.11" cy="10.11" r="8.11" stroke="#848484" strokeWidth="4" />
            <line x1="17.6" y1="17.11" x2="25.67" y2="25.17" stroke="#848484" strokeWidth="4" strokeLinecap="round" />
          </svg>
        </div>

        <div className="squad-members__panel">
          <ul className="squad-members__list">
            {members.map((m) => (
              <li key={m.id} className="squad-member-row">
                <div className="squad-member-row__main">
                  <img className="squad-member-row__avatar" src={userAvatar} alt="" width={50} height={50} />
                  <div className="squad-member-row__tags">
                    <span className="squad-member-tag squad-member-tag--dark">Никнейм</span>
                    <span className="squad-member-tag squad-member-tag--purple">Трек</span>
                    <span className="squad-member-tag squad-member-tag--purple">статус</span>
                  </div>
                </div>
                <button type="button" className="squad-member-row__rating">
                  Рейтинг
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  )
}
