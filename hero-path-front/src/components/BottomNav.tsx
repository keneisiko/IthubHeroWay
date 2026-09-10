import { Link, useLocation } from 'react-router-dom'
import { navItems } from './navItems'

/**
 * Навигация мобильной версии: в макете боковая панель уезжает вниз
 * и превращается в панель с одними иконками.
 *
 * Панель и боковой сайдбар рендерятся оба, а показывает нужный
 * медиазапрос — так переключение при повороте экрана не требует
 * слушателей resize и не сбрасывает состояние страницы.
 */
export default function BottomNav() {
  const location = useLocation()

  return (
    <nav className="bottom-nav" aria-label="Основная навигация">
      {navItems.map(({ path, Icon, label }) => {
        const isActive = location.pathname === path
        return (
          <Link
            key={path}
            to={path}
            className={`bottom-nav__item${isActive ? ' bottom-nav__item--active' : ''}`}
            aria-current={isActive ? 'page' : undefined}
            aria-label={label}
          >
            <span className="bottom-nav__icon">
              <Icon active={isActive} />
            </span>
          </Link>
        )
      })}
    </nav>
  )
}
