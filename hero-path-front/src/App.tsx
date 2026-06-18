import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import PageTransition from './PageTransition'

import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Profile from './pages/Profile'
import Leaderboard from './pages/Leaderboard'
import Quests from './pages/Quests'
import Shop from './pages/Shop'
import Squads from './pages/Squads'

import './App.css'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<AppShell />} />
    </Routes>
  )
}

function AppShell() {
  const location = useLocation()

  return (
    <div className="app-shell">
      <Header />
      <div className="app-content">
        <main className="page-content">
          <PageTransition>
            <Routes location={location} key={location.pathname}>
              <Route path="/" element={<Navigate to="/dashboard" />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/profile/:username" element={<Profile />} />
              <Route path="/leaderboard" element={<Leaderboard />} />
              <Route path="/quests" element={<Quests />} />
              <Route path="/shop" element={<Shop />} />
              <Route path="/squads" element={<Squads />} />
            </Routes>
          </PageTransition>
        </main>
        <Sidebar />
      </div>
    </div>
  )
}

export default App