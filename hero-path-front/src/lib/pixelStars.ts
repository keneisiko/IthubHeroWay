// Пиксельные звёзды темы «Плёнка»: клетки относительно центра и палитра
export type Cell = [number, number]

// уголь, графит, серебро, белый
export const TONES = ['#404040', '#808080', '#c0c0c0', '#ffffff']

export const DOT: Cell[] = [[0, 0]]
export const PLUS: Cell[] = [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]
export const RING: Cell[] = [[1, 0], [-1, 0], [0, 1], [0, -1]]
export const CROSS: Cell[] = [[0, 0], [1, 1], [-1, -1], [1, -1], [-1, 1]]
export const LONG: Cell[] = [[0, 0], [1, 0], [2, 0], [-1, 0], [-2, 0], [0, 1], [0, 2], [0, -1], [0, -2]]
export const THICK: Cell[] = []
for (let y = -3; y <= 3; y++) {
  for (let x = -3; x <= 3; x++) {
    if ((Math.abs(x) <= 1 && Math.abs(y) <= 3) || (Math.abs(y) <= 1 && Math.abs(x) <= 3)) THICK.push([x, y])
  }
}

export function paintShape(ctx: CanvasRenderingContext2D, x: number, y: number, u: number, shape: Cell[]) {
  const bx = Math.round(x - u / 2)
  const by = Math.round(y - u / 2)
  for (const [cx, cy] of shape) ctx.fillRect(bx + cx * u, by + cy * u, u, u)
}
