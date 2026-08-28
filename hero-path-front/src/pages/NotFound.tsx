import { useNavigate } from 'react-router-dom'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="error-page page-enter">
      {/* Пропорции цифр из макета: штрих 27 при высоте 100 */}
      <svg
        className="error-page__code"
        viewBox="0 0 268 100"
        fill="#9a33f4"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* 4 */}
        <rect x="0" y="0" width="27" height="68" />
        <rect x="0" y="41" width="68" height="27" />
        <rect x="41" y="0" width="27" height="100" />

        {/* 0 — рамка из четырёх полос и точка в центре */}
        <rect x="86" y="0" width="96" height="27" />
        <rect x="86" y="73" width="96" height="27" />
        <rect x="86" y="0" width="27" height="100" />
        <rect x="155" y="0" width="27" height="100" />
        <rect x="125" y="41" width="18" height="18" />

        {/* 4 */}
        <rect x="200" y="0" width="27" height="68" />
        <rect x="200" y="41" width="68" height="27" />
        <rect x="241" y="0" width="27" height="100" />
      </svg>

      <h1 className="error-page__label">Error</h1>

      <button type="button" className="error-page__btn btn-press" onClick={() => navigate('/dashboard')}>
        Вернуться на главную
      </button>
    </div>
  )
}
