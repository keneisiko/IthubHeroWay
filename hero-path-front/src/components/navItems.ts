import {
  IconHome, IconProfile, IconQuests,
  IconShop, IconLeaders, IconSquads, IconBadges,
} from './icons'

/** Общий список пунктов навигации: им пользуются и боковая панель, и нижняя. */
export const navItems = [
  { path: '/dashboard',   Icon: IconHome,    label: 'Главная'  },
  { path: '/profile',     Icon: IconProfile, label: 'Профиль'  },
  { path: '/quests',      Icon: IconQuests,  label: 'Квесты'   },
  { path: '/shop',        Icon: IconShop,    label: 'Магазин'  },
  { path: '/leaderboard', Icon: IconLeaders, label: 'Лидеры'   },
  { path: '/squads',      Icon: IconSquads,  label: 'Отряды'   },
  { path: '/badges',      Icon: IconBadges,  label: 'Нашивки'  },
]
