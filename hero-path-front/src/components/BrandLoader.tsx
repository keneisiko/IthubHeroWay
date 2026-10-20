/** Лоадер страницы: знак IThub прорисовывается и заполняется, как в заставке. */
export default function BrandLoader({ label = 'Загрузка' }: { label?: string }) {
  return (
    <div className="brand-loader" role="status" aria-live="polite">
      <svg className="brand-loader__mark" viewBox="0 0 64 64" aria-hidden="true">
        <rect className="brand-loader__frame" x="4.5" y="4.5" width="55" height="55" rx="3" />
        <rect className="brand-loader__core" x="22" y="22" width="20" height="20" />
      </svg>
      <span className="visually-hidden">{label}</span>
    </div>
  )
}
