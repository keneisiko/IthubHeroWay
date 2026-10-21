import DevFrameArt from './DevFrameArt'

/**
 * Рамка разработчика в карточке профиля: при открытии тушь
 * прорисовывается вокруг аватара, цепь затягивается, звёзды вспыхивают,
 * снизу выезжает плашка «Разработчик». Стили — styles/avatar-frames.css.
 */
export default function DevFrame() {
  return (
    <span className="dev-frame" aria-hidden="true">
      <DevFrameArt intro large />
      <span className="dev-frame__tag">
        <span className="dev-frame__code">&lt;/&gt;</span>
        Разработчик
      </span>
    </span>
  )
}
