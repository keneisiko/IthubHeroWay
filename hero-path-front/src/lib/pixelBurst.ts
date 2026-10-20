export const BURST_EVENT = 'pixelfield:burst'

export interface BurstDetail {
  x: number
  y: number
  power?: number
  tone?: 'light' | 'coin' | 'error'
}

/** Волна по живому фону входа из точки экрана (см. PixelField). */
export function pixelBurst(detail: BurstDetail) {
  window.dispatchEvent(new CustomEvent<BurstDetail>(BURST_EVENT, { detail }))
}
