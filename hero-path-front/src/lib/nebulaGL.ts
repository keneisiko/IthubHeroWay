/**
 * Туманность на WebGL: дымка из шума с искажением координат
 * (domain warping) — облака сами медленно перетекают, как жидкость.
 * Рисуется в пониженном разрешении: дымка мягкая, а видеокарте легко.
 */

const VERTEX = `
attribute vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }
`

const FRAGMENT = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
uniform vec2 u_res;
uniform float u_t;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = m * p;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 p = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y * 2.4;
  float t = u_t * 0.04;
  // одно искажение координат: облака перетекают друг в друга
  vec2 q = vec2(fbm(p + vec2(0.0, t)), fbm(p + vec2(5.2, 1.3) - t * 0.8));
  float f = fbm(p + 2.8 * q + vec2(t * 0.6, -t * 0.4));
  // звёздный рукав по диагонали экрана
  vec2 d = normalize(vec2(1.0, 0.85));
  float across = dot(uv - 0.5, vec2(-d.y, d.x));
  float band = exp(-across * across * 9.0);
  float dens = smoothstep(0.32, 0.95, f) * (0.3 + 0.95 * band) + 0.2 * smoothstep(0.5, 0.9, q.x * q.y * 2.0);
  // тёмные пылевые прожилки внутри рукава — из той же дымки, без лишнего шума
  float dust = smoothstep(0.62, 0.8, f + 0.35 * (q.y - 0.5));
  dens *= 1.0 - 0.6 * dust * band;
  gl_FragColor = vec4(vec3(dens * 0.32), 1.0);
}
`

export interface Nebula {
  resize: (w: number, h: number, scale: number) => void
  render: (seconds: number) => void
  dispose: () => void
}

/**
 * null — WebGL недоступен, тогда небо рисует статичную туманность.
 * Шейдер собирается в фоне (KHR_parallel_shader_compile): холодная
 * компиляция занимала главный поток на треть секунды. Пока он не готов,
 * render ничего не рисует — на входе экран и так чёрный.
 */
export function createNebula(canvas: HTMLCanvasElement): Nebula | null {
  const gl = canvas.getContext('webgl', { antialias: false, alpha: false, depth: false, powerPreference: 'low-power' })
  if (!gl) return null
  const parallel = gl.getExtension('KHR_parallel_shader_compile') as { COMPLETION_STATUS_KHR: number } | null
  const vs = gl.createShader(gl.VERTEX_SHADER)
  const fs = gl.createShader(gl.FRAGMENT_SHADER)
  const program = gl.createProgram()
  const buffer = gl.createBuffer()
  if (!vs || !fs || !program || !buffer) return null
  gl.shaderSource(vs, VERTEX)
  gl.shaderSource(fs, FRAGMENT)
  gl.compileShader(vs)
  gl.compileShader(fs)
  gl.attachShader(program, vs)
  gl.attachShader(program, fs)
  gl.linkProgram(program)

  let state: 'pending' | 'ready' | 'broken' = 'pending'
  let uRes: WebGLUniformLocation | null = null
  let uT: WebGLUniformLocation | null = null
  let size: [number, number] = [1, 1]

  const ensure = () => {
    if (state !== 'pending') return state === 'ready'
    if (parallel && !gl.getProgramParameter(program, parallel.COMPLETION_STATUS_KHR)) return false
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      state = 'broken'
      return false
    }
    gl.useProgram(program)
    // один треугольник на весь экран
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
    const pos = gl.getAttribLocation(program, 'a_pos')
    gl.enableVertexAttribArray(pos)
    gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0)
    uRes = gl.getUniformLocation(program, 'u_res')
    uT = gl.getUniformLocation(program, 'u_t')
    gl.uniform2f(uRes, size[0], size[1])
    state = 'ready'
    return true
  }

  return {
    resize(w, h, scale) {
      canvas.width = Math.max(1, Math.round(w * scale))
      canvas.height = Math.max(1, Math.round(h * scale))
      size = [canvas.width, canvas.height]
      gl.viewport(0, 0, size[0], size[1])
      if (state === 'ready') gl.uniform2f(uRes, size[0], size[1])
    },
    render(seconds) {
      if (!ensure()) return
      gl.uniform1f(uT, seconds)
      gl.drawArrays(gl.TRIANGLES, 0, 3)
    },
    dispose() {
      gl.deleteBuffer(buffer)
      gl.deleteProgram(program)
      gl.deleteShader(vs)
      gl.deleteShader(fs)
      gl.getExtension('WEBGL_lose_context')?.loseContext()
    },
  }
}
