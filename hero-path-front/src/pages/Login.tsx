import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ithubLogo from '../assets/other/лого-26 1.svg'
import api from '../api'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleLogin = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/token/', { username, password })
      localStorage.setItem('access_token', res.data.access)
      localStorage.setItem('refresh_token', res.data.refresh)
      navigate('/dashboard')
    } catch {
      setError('Неверный логин или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-container popup">
        <div className="login-inner">
          <div className="login-content">
            <div style={{ textAlign: 'center', marginBottom: '8px' }}>
              <img src={ithubLogo} alt="IThub" style={{ width: '120px', objectFit: 'contain' }} />
            </div>

            <h1 className="login-title">Путь героя</h1>

            <div className="login-form-fields">
              <div className="login-input-field">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Логин"
                  style={{ width: '100%', height: '100%', border: 'none', outline: 'none', background: 'transparent', fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '20px', color: '#121212', padding: '0 15px', borderRadius: '12px' }}
                />
              </div>

              <div className="login-input-field">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Пароль"
                  onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                  style={{ width: '100%', height: '100%', border: 'none', outline: 'none', background: 'transparent', fontFamily: 'Montserrat, sans-serif', fontWeight: 600, fontSize: '20px', color: '#121212', padding: '0 15px', borderRadius: '12px' }}
                />
              </div>

              {error && (
                <div style={{ color: 'red', fontFamily: 'Montserrat, sans-serif', fontSize: '14px' }}>
                  {error}
                </div>
              )}
            </div>

            <button
              type="button"
              className="login-submit-button"
              onClick={handleLogin}
              disabled={loading}
              style={{ width: '100%', border: 'none', cursor: 'pointer', opacity: loading ? 0.7 : 1 }}
            >
              <span className="login-submit-text">{loading ? 'Загрузка...' : 'Войти'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}