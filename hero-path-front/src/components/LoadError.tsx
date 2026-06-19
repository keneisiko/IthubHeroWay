interface LoadErrorProps {
  message?: string
  onRetry?: () => void
  className?: string
}

export default function LoadError({
  message = 'Не удалось загрузить данные. Проверьте соединение и попробуйте снова.',
  onRetry,
  className = 'profile-loading',
}: LoadErrorProps) {
  return (
    <div className={className}>
      <p className="loading-text">{message}</p>
      {onRetry && (
        <button type="button" className="error-page__btn btn-press" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  )
}
