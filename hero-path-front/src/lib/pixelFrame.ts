export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

// контур вокруг фото по часовой стрелке; углы срезаны ступенькой
export function outline(o: number, s: number, u: number): Rect[] {
  const n = Math.max(1, Math.round(s / u))
  const at = (i: number) => o + Math.round((i * s) / n)
  const cells: Rect[] = []
  for (let i = 0; i < n; i++) cells.push({ x: at(i), y: o - u, w: at(i + 1) - at(i), h: u })
  cells.push({ x: o + s - u, y: o, w: u, h: u })
  for (let i = 0; i < n; i++) cells.push({ x: o + s, y: at(i), w: u, h: at(i + 1) - at(i) })
  cells.push({ x: o + s - u, y: o + s - u, w: u, h: u })
  for (let i = n - 1; i >= 0; i--) cells.push({ x: at(i), y: o + s, w: at(i + 1) - at(i), h: u })
  cells.push({ x: o, y: o + s - u, w: u, h: u })
  for (let i = n - 1; i >= 0; i--) cells.push({ x: o - u, y: at(i), w: u, h: at(i + 1) - at(i) })
  cells.push({ x: o, y: o, w: u, h: u })
  return cells
}
