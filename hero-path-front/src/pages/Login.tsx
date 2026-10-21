import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import ithubLogo from '../assets/other/лого-26 1.svg'
import api from '../api'
import { clearAuthTokens, extractLoginError } from '../auth'
import PixelField from '../components/PixelField'
import { pixelBurst } from '../lib/pixelBurst'
import { markEntered } from '../lib/enterFlag'
import { releaseBoot } from '../lib/boot'
import '../styles/login.css'

type Phase = 'idle' | 'loading' | 'success'

function burstFrom(el: HTMLElement | null, power: number, tone: 'light' | 'coin' | 'error' = 'light') {
  if (!el) return
  const rect = el.getBoundingClientRect()
  pixelBurst({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, power, tone })
}

interface Glyph {
  ch: string
  id: number
}

let glyphSeq = 0

// новые символы получают новый ключ — анимируются только они,
// даже если вставка пришлась в середину строки
function diffGlyphs(prev: Glyph[], next: string): Glyph[] {
  const old = prev.map((g) => g.ch)
  const chars = Array.from(next)
  let head = 0
  while (head < old.length && head < chars.length && old[head] === chars[head]) head++
  let tail = 0
  while (
    tail < old.length - head &&
    tail < chars.length - head &&
    old[old.length - 1 - tail] === chars[chars.length - 1 - tail]
  ) tail++
  const fresh = chars.slice(head, chars.length - tail).map((ch) => ({ ch, id: ++glyphSeq }))
  return [...prev.slice(0, head), ...fresh, ...prev.slice(prev.length - tail)]
}

interface FieldProps {
  id: string
  label: string
  hint: string
  type: 'text' | 'password'
  value: string
  minLength: number
  invalid: boolean
  autoComplete: string
  autoFocus?: boolean
  onChange: (value: string) => void
  onKeyState?: (e: React.KeyboardEvent<HTMLInputElement>) => void
}

function Field({ id, label, hint, type, value, minLength, invalid, autoComplete, autoFocus, onChange, onKeyState }: FieldProps) {
  const [visible, setVisible] = useState(false)
  const [glyphs, setGlyphs] = useState<Glyph[]>([])
  const wrapRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const runRef = useRef<HTMLSpanElement>(null)
  const probeRef = useRef<HTMLInputElement>(null)
  const isPassword = type === 'password'
  const masked = isPassword && !visible
  const ready = value.trim().length >= minLength

  // ширина одной скрытой точки у браузера своя — снимаем её с невидимого
  // поля-образца, чтобы пиксели слоя стояли ровно над кареткой
  const measurePitch = () => {
    const probe = probeRef.current
    if (probe && wrapRef.current) wrapRef.current.style.setProperty('--pitch', `${probe.scrollWidth / 10}px`)
  }

  useEffect(() => {
    if (!isPassword) return
    measurePitch()
    document.fonts?.ready.then(measurePitch)
  })

  // слой с символами двигается вместе с прокруткой длинного значения
  const syncScroll = () => {
    requestAnimationFrame(() => {
      const input = inputRef.current
      if (input && runRef.current) runRef.current.style.transform = `translateX(${-input.scrollLeft}px)`
    })
  }

  const sparkAtCaret = (power: number) => {
    const wrap = wrapRef.current
    if (!wrap) return
    const box = wrap.getBoundingClientRect()
    const run = runRef.current?.getBoundingClientRect()
    const x = run && run.width > 0 ? Math.min(box.right - 24, run.right) : box.left + 24
    pixelBurst({ x, y: box.top + box.height / 2, power, tone: 'light' })
  }

  return (
    <div
      ref={wrapRef}
      className={`lp-field${value ? ' lp-field--filled' : ''}${invalid ? ' lp-field--invalid' : ''}${isPassword ? ' lp-field--password' : ''}${ready ? ' lp-field--ready' : ''}`}
    >
      <input
        ref={inputRef}
        id={id}
        name={id}
        className="lp-field__input"
        type={masked ? 'password' : 'text'}
        value={value}
        autoComplete={autoComplete}
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        autoFocus={autoFocus}
        aria-invalid={invalid}
        placeholder=" "
        onChange={(e) => {
          const next = e.target.value
          setGlyphs((prev) => diffGlyphs(prev, next))
          onChange(next)
          syncScroll()
          if (next.length > value.length) requestAnimationFrame(() => sparkAtCaret(0.3))
        }}
        onScroll={syncScroll}
        onSelect={syncScroll}
        onBlur={syncScroll}
        onFocus={() => {
          measurePitch()
          burstFrom(wrapRef.current, 0.55)
        }}
        onKeyDown={onKeyState}
        onKeyUp={onKeyState}
      />
      <label htmlFor={id} className="lp-field__label">{label}</label>
      <span className="lp-field__hint" aria-hidden="true">{hint}</span>
      <span className={`lp-field__glyphs${masked ? ' lp-field__glyphs--masked' : ''}`} aria-hidden="true">
        <span ref={runRef} className="lp-field__run">
          {glyphs.map((g) => <span key={g.id} className="lp-ch">{masked ? '' : g.ch}</span>)}
        </span>
      </span>
      {isPassword && (
        <input ref={probeRef} className="lp-field__probe" type="password" value="0000000000" readOnly tabIndex={-1} aria-hidden="true" />
      )}
      <span className="lp-field__ok" aria-hidden="true"><i /></span>
      {isPassword && (
        <button
          type="button"
          className={`lp-field__eye${visible ? ' lp-field__eye--open' : ''}`}
          onClick={() => {
            setVisible((v) => !v)
            inputRef.current?.focus()
            syncScroll()
          }}
          aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'}
          aria-pressed={visible}
        >
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path className="lp-eye__lid" d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z" />
            <rect className="lp-eye__pupil" x="9" y="9" width="6" height="6" />
            <path className="lp-eye__slash" d="M4 4l16 16" />
          </svg>
        </button>
      )}
    </div>
  )
}

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [shaking, setShaking] = useState(false)
  const [capsOn, setCapsOn] = useState(false)
  const [origin, setOrigin] = useState<DOMRect | null>(null)
  const [ready, setReady] = useState(false)
  const cardRef = useRef<HTMLFormElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const redirectTo = (location.state as { from?: string } | null)?.from || '/dashboard'

  useEffect(() => {
    let alive = true
    releaseBoot().then(() => { if (alive) setReady(true) })
    return () => { alive = false }
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    api.get('/api/v1/profile/me/')
      .then(() => navigate(redirectTo, { replace: true }))
      .catch(() => clearAuthTokens())
  }, [navigate, redirectTo])

  const validate = () => {
    if (!username.trim()) return 'Введите логин'
    if (username.trim().length < 3) return 'Логин минимум 3 символа'
    if (!password) return 'Введите пароль'
    if (password.length < 4) return 'Пароль минимум 4 символа'
    return ''
  }

  const fail = (message: string) => {
    setError(message)
    // снять и снова поставить класс — иначе повторная ошибка не трясёт
    setShaking(false)
    requestAnimationFrame(() => setShaking(true))
    burstFrom(cardRef.current, 1, 'error')
    navigator.vibrate?.(40)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (phase !== 'idle') return
    const validationError = validate()
    if (validationError) {
      fail(validationError)
      return
    }

    setPhase('loading')
    setError('')
    try {
      const res = await api.post('/api/v1/auth/login/', { login: username.trim(), password })
      localStorage.setItem('access_token', res.data.access)
      localStorage.setItem('refresh_token', res.data.refresh)
      setPhase('success')
      burstFrom(buttonRef.current, 1, 'coin')

      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      const rect = buttonRef.current?.getBoundingClientRect()
      if (rect) setOrigin(rect)
      markEntered()
      window.setTimeout(() => navigate(redirectTo, { replace: true }), reduce ? 150 : 900)
    } catch (err: unknown) {
      setPhase('idle')
      fail(extractLoginError(err))
    }
  }

  const trackCaps = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (typeof e.getModifierState === 'function') setCapsOn(e.getModifierState('CapsLock'))
  }

  const clearError = () => { if (error) setError('') }

  return (
    <div className={`lp${ready ? ' lp--ready' : ''}`}>
      <PixelField className="lp__field" />
      <div className="lp__vignette" aria-hidden="true" />

      <div className="lp__layout">
        <header className="lp__hero">
          <img src={ithubLogo} alt="IThub" className="lp__logo" />
          <h1 className="lp__title">
            <span className="lp__line"><span>Путь</span></span>
            <span className="lp__line"><span>героя</span></span>
          </h1>
          <p className="lp__lead">Квесты, рейтинг и нашивки колледжа. Каждый день — шаг по своей тропе.</p>
        </header>

        <div className="lp__card-slot">
        <form
          ref={cardRef}
          className={`lp-card${shaking ? ' lp-card--shake' : ''}${phase === 'success' ? ' lp-card--done' : ''}`}
          onSubmit={handleSubmit}
          onAnimationEnd={(e) => { if (e.target === e.currentTarget) setShaking(false) }}
          noValidate
        >
          <div className="lp-card__head">
            <h2 className="lp-card__title">Вход</h2>
            <span className="lp-card__mark" aria-hidden="true"><i /></span>
          </div>

          <div className="lp-card__fields">
            <Field
              id="login"
              label="Логин"
              hint="позывной, логин или почта"
              type="text"
              value={username}
              minLength={3}
              invalid={Boolean(error) && !username.trim()}
              autoComplete="username"
              autoFocus
              onChange={(v) => { setUsername(v); clearError() }}
            />
            <Field
              id="password"
              label="Пароль"
              hint="выдаёт администратор"
              type="password"
              value={password}
              minLength={4}
              invalid={Boolean(error) && !password}
              autoComplete="current-password"
              onChange={(v) => { setPassword(v); clearError() }}
              onKeyState={trackCaps}
            />
          </div>

          <div className="lp-card__notes" aria-live="polite">
            {error && <p className="lp-card__error" role="alert">{error}</p>}
            {!error && capsOn && <p className="lp-card__caps">Включён Caps Lock</p>}
          </div>

          <button
            ref={buttonRef}
            type="submit"
            className={`lp-submit lp-submit--${phase}`}
            disabled={phase !== 'idle'}
            aria-busy={phase === 'loading'}
          >
            <span className="lp-submit__label">Войти</span>
            <span className="lp-submit__loader" aria-hidden="true"><i /><i /><i /></span>
            <svg className="lp-submit__check" viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
              <path d="M5 12.5l4.5 4.5L19 7.5" />
            </svg>
          </button>

          <p className="lp-card__foot">
            Забыли пароль? Обратитесь к <span>администратору</span>
          </p>
        </form>
        </div>
      </div>

      {origin && (
        <div
          className="lp__wipe"
          aria-hidden="true"
          style={{
            '--wt': `${origin.top}px`,
            '--wr': `${window.innerWidth - origin.right}px`,
            '--wb': `${window.innerHeight - origin.bottom}px`,
            '--wl': `${origin.left}px`,
          } as React.CSSProperties}
        />
      )}
    </div>
  )
}
