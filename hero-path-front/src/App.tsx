import { lazy, Suspense, useEffect, useState } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Header from './components/Header'
import ProtectedRoute from './components/ProtectedRoute'
import Sidebar from './components/Sidebar'
import BottomNav from './components/BottomNav'
import ScrollTopButton from './components/ScrollTopButton'
import BrandLoader from './components/BrandLoader'
import Atmosphere from './components/Atmosphere'
import PageTransition from './PageTransition'
import { releaseBoot } from './lib/boot'
import { clearEnterFlag, hasEnterFlag } from './lib/enterFlag'

import './App.css'
import './styles/atmosphere.css'
import './styles/interaction.css'
import './styles/motion.css'
import './styles/avatar.css'
import './styles/cosmetics.css'

const pages = {
  dashboard: () => import('./pages/Dashboard'),
  profile: () => import('./pages/Profile'),
  leaderboard: () => import('./pages/Leaderboard'),
  quests: () => import('./pages/Quests'),
  shop: () => import('./pages/Shop'),
  squads: () => import('./pages/Squads'),
  badges: () => import('./pages/Badges'),
}

const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(pages.dashboard)
const Profile = lazy(pages.profile)
const Leaderboard = lazy(pages.leaderboard)
const Quests = lazy(pages.quests)
const Shop = lazy(pages.shop)
const Squads = lazy(pages.squads)
const Badges = lazy(pages.badges)
const NotFound = lazy(() => import('./pages/NotFound'))

/**
 * Код всех разделов подтягиваем, пока человек смотрит первую страницу:
 * иначе первый переход в каждый раздел ждал загрузку файла и показывал
 * лоадер посреди перехода.
 */
function prefetchPages() {
  const run = () => Object.values(pages).forEach((load) => { load().catch(() => {}) })
  const idle = (window as Window & { requestIdleCallback?: (cb: () => void) => number }).requestIdleCallback
  if (idle) idle(run)
  else window.setTimeout(run, 1200)
}

function App() {
  return (
    <Suspense fallback={<BrandLoader />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        } />
      </Routes>
    </Suspense>
  )
}

function AppShell() {
  const location = useLocation()
  const KNOWN_PATHS = ['/dashboard', '/profile', '/leaderboard', '/quests', '/shop', '/squads', '/badges']
  const isKnownRoute = location.pathname === '/' || KNOWN_PATHS.some(p => location.pathname.startsWith(p))
  // заставку после входа играем один раз: флаг ставит страница входа
  const [entering, setEntering] = useState(hasEnterFlag)

  useEffect(() => {
    prefetchPages()
  }, [])

  useEffect(() => {
    releaseBoot()
    if (!entering) return
    clearEnterFlag()
    const timer = window.setTimeout(() => setEntering(false), 1600)
    return () => window.clearTimeout(timer)
  }, [entering])

  return (
    <div className={`app-shell${entering ? ' app-shell--entering' : ''}`}>
      <Atmosphere />
      <Header />
      <div className="app-content">
        <main className="page-content">
          <PageTransition>
            <Suspense fallback={<BrandLoader />}>
              <Routes location={location} key={location.pathname}>
                <Route path="/" element={<Navigate to="/dashboard" />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="/profile/:username" element={<Profile />} />
                <Route path="/leaderboard" element={<Leaderboard />} />
                <Route path="/quests" element={<Quests />} />
                <Route path="/shop" element={<Shop />} />
                <Route path="/squads" element={<Squads />} />
                <Route path="/badges" element={<Badges />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </PageTransition>
        </main>
        {isKnownRoute && <Sidebar />}
      </div>
      {isKnownRoute && <BottomNav />}
      <ScrollTopButton />
      {entering && (
        <div className="shell-intro" aria-hidden="true">
          <span className="shell-intro__mark" />
        </div>
      )}
    </div>
  )
}

export default App
