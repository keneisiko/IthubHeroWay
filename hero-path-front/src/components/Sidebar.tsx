import { Link, useLocation } from 'react-router-dom'

import {
  IconHome,
  IconProfile,
  IconQuests,
  IconShop,
  IconLeaders,
  IconSquads
} from './icons'

const navItems = [
  { path: '/dashboard', Icon: IconHome, label: 'Главная' },
  { path: '/profile', Icon: IconProfile, label: 'Профиль' },
  { path: '/quests', Icon: IconQuests, label: 'Квесты' },
  { path: '/shop', Icon: IconShop, label: 'Магазин' },
  { path: '/leaderboard', Icon: IconLeaders, label: 'Лидеры' },
  { path: '/squads', Icon: IconSquads, label: 'Отряды' },
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside className="right-sidebar">
      {navItems.map((item) => {
        const isActive = location.pathname === item.path

        const Icon = item.Icon

        return (
          <Link
            key={item.path}
            to={item.path}
            className={`right-sidebar__item ${
              isActive ? 'right-sidebar__item--active' : ''
            }`}
          >
            {/* защита от падения */}
            {Icon && <Icon active={isActive} />}
            <span>{item.label}</span>
          </Link>
        )
      })}
    </aside>
  )
}