import ithubLogo from '../assets/other/лого-26 1.svg'
import userAvatar from '../assets/branding/user-avatar.png'

export default function Header() {
  return (
    <header className="top-header">
      <div className="top-header__brand">
        <img src={ithubLogo} alt="IThub" className="top-header__logo-image" />
        <span className="top-header__divider" />
        <span className="top-header__title">Путь героя</span>
      </div>
      <div className="top-header__user">
        <div className="top-header__user-meta">
          <div className="top-header__username">имя пользователя</div>
          <div className="top-header__money">
            <span>Money:</span> <strong>9.99</strong>
          </div>
        </div>
        <img src={userAvatar} alt="Аватар пользователя" className="top-header__avatar" />
      </div>
    </header>
  )
}