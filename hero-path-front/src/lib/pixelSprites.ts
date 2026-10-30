// Пиксельные спрайты темы «Самый страшный»: строки — ряды клеток, буква —
// цвет из палитры, точка — пусто. Рисуются целыми клетками, без сглаживания.
export type Sprite = string[]
export type Palette = Record<string, string>

export const NIGHT: Palette = {
  k: '#0c0912',
  g: '#2a2140',
  e: '#ffcc33',
  r: '#ff4d2e',
  b: '#4a3f5c',
  l: '#5c4f6e',
  o: '#ff7a1a',
  d: '#b8480c',
  y: '#ffd23f',
  w: '#fff3c4',
  s: '#4f8a3a',
  t: '#e3dccb',
  T: '#a99f8c',
  c: '#efe6d8',
  C: '#c9bba3',
  E: '#ff9a2e',
}

// ворон сидит, смотрит влево; кадры: покой, моргнул, каркнул, повернул голову, взмахнул крылом
export const CROW_SIT: Sprite[] = [
  [
    '....kkk.....',
    '...kkekk....',
    '.bbkkkkk....',
    '....kkkkk...',
    '....kkgkkk..',
    '.....kggkkkk',
    '.....kkkkk.k',
    '......l.l...',
  ],
  [
    '....kkk.....',
    '...kkkkk....',
    '.bbkkkkk....',
    '....kkkkk...',
    '....kkgkkk..',
    '.....kggkkkk',
    '.....kkkkk.k',
    '......l.l...',
  ],
  [
    '....kkk.....',
    '...kkekk....',
    'bb..kkkk....',
    '.bb.kkkkk...',
    '....kkgkkk..',
    '.....kggkkkk',
    '.....kkkkk.k',
    '......l.l...',
  ],
  [
    '.....kkk....',
    '....kkkek...',
    '....kkkkkbb.',
    '....kkkkk...',
    '....kkgkkk..',
    '.....kggkkkk',
    '.....kkkkk.k',
    '......l.l...',
  ],
  [
    '....kkk...k.',
    '...kkekk.kk.',
    '.bbkkkkkkkk.',
    '....kkkkkk..',
    '....kkgkkk..',
    '.....kggkkkk',
    '.....kkkkk.k',
    '......l.l...',
  ],
]

// ворон в полёте влево: крылья вверх и вниз
export const CROW_FLY: Sprite[] = [
  [
    '.k......k.',
    '..k....k..',
    '..kkkkkk..',
    'bkkekkk...',
    '..........',
  ],
  [
    '..........',
    '..kkkkkkk.',
    'bkkekkkk..',
    '..k....k..',
    '.k......k.',
  ],
]

// летучая мышь: два взмаха
export const BAT: Sprite[] = [
  [
    'k.......k',
    'kk.k.k.kk',
    '.kkkkkkk.',
    '...krk...',
  ],
  [
    '.........',
    '...k.k...',
    '.kkkkkkk.',
    'kk.krk.kk',
  ],
]

// ведьма на метле летит влево, развевается плащ и прутья метлы
export const WITCH: Sprite[] = [
  [
    '......k...............',
    '.....kk...............',
    '....kkkk..............',
    '...kkkkkk.............',
    '..kkkkkkkkk...........',
    '.....kek..............',
    '....kkkkk.kk..........',
    '...kkkkkkkkkkk........',
    'bbbbbbkkkkkbbbbbbbddd.',
    '......kkkk.....dddddyd',
    '.......k.k......dd.d..',
  ],
  [
    '......k...............',
    '.....kk...............',
    '....kkkk..............',
    '...kkkkkk.............',
    '..kkkkkkkkk...........',
    '.....kek..............',
    '....kkkkk..kkk........',
    '...kkkkkkkkkk.k.......',
    'bbbbbbkkkkkbbbbbbbddd.',
    '......kkkk.....ddddydd',
    '.......k.k.....d.dd.d.',
  ],
]

// фонарь-тыква: лицо горит свечой, цвет лица задаёт мерцание
export const PUMPKIN: Sprite = [
  '.....ss....',
  '..ddosoodd.',
  '.ooooooooo.',
  'oooyoooyooo',
  'ooyyyoyyyoo',
  'oooooyooooo',
  'ooyoyoyoyoo',
  '.ooyyyyyoo.',
  '..ddooodd..',
]

export const PUMPKIN_SMALL: Sprite = [
  '...s...',
  '.dosod.',
  'oyoooyo',
  'ooooooo',
  'oyyyyyo',
  '.doood.',
]

export const SPIDER: Sprite = [
  'k.k.k',
  '.kkk.',
  'kkrkk',
  'k.k.k',
]

// череп — замковый камень кладки, глаза горят отсветом свечи
export const SKULL: Sprite = [
  '.ttttt.',
  'ttttttt',
  'tEEtEEt',
  'tEEtEEt',
  'TttkttT',
  '.ttttt.',
  '.tTtTt.',
]

// призрак поднимается из тумана; два кадра — колышется подол
export const GHOST: Sprite[] = [
  [
    '...ttt...',
    '.ttttttt.',
    'ttttttttt',
    'tkkttkktt',
    'tkkttkktt',
    'ttttttttt',
    'tttkkkttt',
    'tttkkkttt',
    'ttttttttt',
    'ttttttttt',
    't.tt.tt.t',
  ],
  [
    '...ttt...',
    '.ttttttt.',
    'ttttttttt',
    'tkkttkktt',
    'tkkttkktt',
    'ttttttttt',
    'tttkkkttt',
    'tttkkkttt',
    'ttttttttt',
    'ttttttttt',
    '.tt.tt.tt',
  ],
]

// оплывшая свеча и три кадра пламени
export const CANDLE: Sprite = [
  '.k.',
  'ccc',
  'ccC',
  'Ccc',
  'ccc',
  'cCc',
  'ccc',
  'CcC',
]

export const FLAME: Sprite[] = [
  ['.y.', '.yy', 'ywy', 'yoy', '.o.'],
  ['.y.', 'yy.', 'ywy', 'yoy', '.o.'],
  ['..y', '.yy', 'yww', 'yoy', '.o.'],
]

export function drawSprite(
  ctx: CanvasRenderingContext2D,
  sprite: Sprite,
  x: number,
  y: number,
  u: number,
  palette: Palette = NIGHT,
  flip = false,
) {
  const w = sprite[0].length
  for (let j = 0; j < sprite.length; j++) {
    const row = sprite[j]
    for (let i = 0; i < w; i++) {
      const ch = row[flip ? w - 1 - i : i]
      if (ch === '.') continue
      ctx.fillStyle = palette[ch] ?? ch
      ctx.fillRect(Math.round(x + i * u), Math.round(y + j * u), u, u)
    }
  }
}
