import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import ithubLogo from '../assets/other/лого-26 1.svg'
import api from '../api'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [shake, setShake] = useState(false)
  const [focusedField, setFocusedField] = useState<string | null>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const redirectTo = (location.state as { from?: string } | null)?.from || '/dashboard'

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) navigate(redirectTo, { replace: true })
  }, [navigate, redirectTo])

  const validate = () => {
    if (!username.trim()) return 'Введите логин'
    if (username.length < 3) return 'Логин минимум 3 символа'
    if (!password) return 'Введите пароль'
    if (password.length < 4) return 'Пароль минимум 4 символа'
    return ''
  }

  const handleLogin = async () => {
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      setShake(true)
      setTimeout(() => setShake(false), 500)
      return
    }

    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/token/', { username, password })
      localStorage.setItem('access_token', res.data.access)
      localStorage.setItem('refresh_token', res.data.refresh)
      navigate(redirectTo, { replace: true })
    } catch (err: any) {
      const msg = err.response?.status === 401 
        ? 'Неверный логин или пароль' 
        : 'Ошибка соединения. Попробуйте позже'
      setError(msg)
      setShake(true)
      setTimeout(() => setShake(false), 500)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleLogin()
  }

  return (
    <div className="login-page">
      <div className={`login-container ${shake ? 'login-shake' : ''}`}>
        <div className="login-inner">
          <div className="login-content">
            <div className="login-brand">
              <div className="login-logo-wrap">
                <img src={ithubLogo} alt="IThub" className="login-logo" />
              </div>
            </div>

            <h1 className="login-title">Путь героя</h1>
            <p className="login-subtitle">Войди, чтобы начать свой путь</p>

            <div className="login-form-fields">
              <div className={`login-input-field ${focusedField === 'username' ? 'login-input-field--focused' : ''} ${error && !username ? 'login-input-field--error' : ''}`}>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => { setUsername(e.target.value); if (error) setError('') }}
                  onFocus={() => setFocusedField('username')}
                  onBlur={() => setFocusedField(null)}
                  placeholder="Логин"
                  autoFocus
                  className="login-input"
                />
              </div>

              <div className={`login-input-field ${focusedField === 'password' ? 'login-input-field--focused' : ''} ${error && !password ? 'login-input-field--error' : ''}`}>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); if (error) setError('') }}
                  onFocus={() => setFocusedField('password')}
                  onBlur={() => setFocusedField(null)}
                  placeholder="Пароль"
                  onKeyDown={handleKeyDown}
                  className="login-input"
                />
              </div>

              {error && (
                <div className="login-error">
                  <span className="login-error-icon">⚠</span>
                  {error}
                </div>
              )}
            </div>

            <button
              type="button"
              className={`login-submit-button ${loading ? 'login-submit-button--loading' : ''}`}
              onClick={handleLogin}
              disabled={loading}
            >
              {loading ? (
                <span className="login-spinner">
                  <span className="login-spinner-dot" />
                  <span className="login-spinner-dot" />
                  <span className="login-spinner-dot" />
                </span>
              ) : (
                <span className="login-submit-text">Войти</span>
              )}
            </button>

            <div className="login-footer">
              <span className="login-hint">Забыли пароль? Обратитесь к администратору</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}