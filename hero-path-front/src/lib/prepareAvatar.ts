// Сторона готового аватара: на сайте он не бывает крупнее 200px, запас под ретину
const SIDE = 640

function loadImage(file: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('decode'))
    }
    img.src = url
  })
}

/**
 * Готовит фото к загрузке: квадрат по центру, не больше 640px, JPEG.
 * Снимок с айфона весит несколько мегабайт, бывает в HEIC, который сервер
 * не читает, и повёрнут через EXIF, — браузер сам его декодирует и
 * поворачивает, а на сервер уходит лёгкий обычный JPEG. GIF не трогаем,
 * чтобы не потерять анимацию; если браузер не смог прочитать файл,
 * отправляем как есть — сервер скажет, что не так.
 */
export async function prepareAvatar(file: File): Promise<File> {
  if (file.type === 'image/gif') return file
  try {
    const img = await loadImage(file)
    const side = Math.min(img.naturalWidth, img.naturalHeight)
    if (!side) return file
    const out = Math.min(SIDE, side)
    const canvas = document.createElement('canvas')
    canvas.width = out
    canvas.height = out
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, out, out)
    ctx.imageSmoothingQuality = 'high'
    ctx.drawImage(img, (img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2, side, side, 0, 0, out, out)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
    if (!blob) return file
    return new File([blob], 'avatar.jpg', { type: 'image/jpeg' })
  } catch {
    return file
  }
}
