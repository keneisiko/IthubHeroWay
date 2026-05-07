import { Routes, Route, Navigate } from 'react-router-dom'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Profile from './pages/Profile'
import './App.css'

function App() {
  return (
    <div className="app-shell">
      <Header />
      <div className="app-content">
        <main className="page-content">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/profile/:username?" element={<Profile />} />
            <Route path="/leaderboard" element={<div>Лидерборд</div>} />
            <Route path="/shop" element={<div>Магазин</div>} />
            <Route path="/quests" element={<div>Квесты</div>} />
            <Route path="/squads" element={<div>Отряды</div>} />
          </Routes>
        </main>
        <Sidebar />
      </div>
    </div>
  )
}

export default App