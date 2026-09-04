import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Header from './components/Header'
import ProtectedRoute from './components/ProtectedRoute'
import Sidebar from './components/Sidebar'
import PageTransition from './PageTransition'

import './App.css'

const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Profile = lazy(() => import('./pages/Profile'))
const Leaderboard = lazy(() => import('./pages/Leaderboard'))
const Quests = lazy(() => import('./pages/Quests'))
const Shop = lazy(() => import('./pages/Shop'))
const Squads = lazy(() => import('./pages/Squads'))
const Badges = lazy(() => import('./pages/Badges'))
const NotFound = lazy(() => import('./pages/NotFound'))

function PageFallback() {
  return (
    <div className="profile-loading">
      <div className="loading-spinner">
        <span className="loading-spinner-dot" />
        <span className="loading-spinner-dot" />
        <span className="loading-spinner-dot" />
      </div>
      <p className="loading-text">Загрузка...</p>
    </div>
  )
}

function App() {
  return (
    <Suspense fallback={<PageFallback />}>
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

  return (
    <div className="app-shell">
      <Header />
      <div className="app-content">
        <main className="page-content">
          <PageTransition>
            <Suspense fallback={<PageFallback />}>
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
    </div>
  )
}

export default App
