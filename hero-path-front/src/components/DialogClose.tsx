export default function DialogClose({ onClose }: { onClose: () => void }) {
  return (
    <button type="button" className="popup__close" onClick={onClose} aria-label="Закрыть">
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    </button>
  )
}
