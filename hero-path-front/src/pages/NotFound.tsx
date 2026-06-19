import { useNavigate } from 'react-router-dom'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="error-page page-enter">
      <svg
        className="error-page__code"
        viewBox="0 0 346 110"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* 4 */}
        <rect x="0" y="0" width="18" height="58" fill="#9a33f4" />
        <rect x="0" y="40" width="100" height="18" fill="#9a33f4" />
        <rect x="82" y="0" width="18" height="110" fill="#9a33f4" />

        {/* 0 */}
        <rect x="132" y="9" width="82" height="92" fill="none" stroke="#9a33f4" strokeWidth="18" />
        <rect x="165" y="47" width="16" height="16" fill="#9a33f4" />

        {/* 4 */}
        <rect x="246" y="0" width="18" height="58" fill="#9a33f4" />
        <rect x="246" y="40" width="100" height="18" fill="#9a33f4" />
        <rect x="328" y="0" width="18" height="110" fill="#9a33f4" />
      </svg>

      <h1 className="error-page__label">Error</h1>

      <button type="button" className="error-page__btn btn-press" onClick={() => navigate('/dashboard')}>
        Вернуться на главную
      </button>
    </div>
  )
}
