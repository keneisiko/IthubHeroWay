import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ithubLogo from '../assets/other/лого-26 1.svg'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const navigate = useNavigate()

  const handleLogin = () => {
    // MVP: any values work
    localStorage.setItem('loggedIn', 'true')
    localStorage.setItem('username', username || 'Пользователь')
    navigate('/dashboard')
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
                  style={{
                    width: '100%',
                    height: '100%',
                    border: 'none',
                    outline: 'none',
                    background: 'transparent',
                    fontFamily: 'Montserrat, sans-serif',
                    fontWeight: 600,
                    fontSize: '20px',
                    color: '#121212',
                    padding: '0 15px',
                    borderRadius: '12px',
                  }}
                />
              </div>

              <div className="login-input-field">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Пароль"
                  onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                  style={{
                    width: '100%',
                    height: '100%',
                    border: 'none',
                    outline: 'none',
                    background: 'transparent',
                    fontFamily: 'Montserrat, sans-serif',
                    fontWeight: 600,
                    fontSize: '20px',
                    color: '#121212',
                    padding: '0 15px',
                    borderRadius: '12px',
                  }}
                />
              </div>

              <div style={{ fontSize: '15px', color: '#9a33f4', fontFamily: 'Montserrat, sans-serif', fontWeight: 500, letterSpacing: '1.35px', lineHeight: '114.86%' }}>
                Введите любые данные для входа (MVP)
              </div>
            </div>

            <button
              type="button"
              className="login-submit-button"
              onClick={handleLogin}
              style={{
                width: '100%',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              <span className="login-submit-text">Войти</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
