import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

const front = path.resolve(import.meta.dirname, '../..')
const output = ts.transpileModule(fs.readFileSync(path.join(front, 'src/components/PixelField.tsx'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText

class Events {
  listeners = new Map()
  addEventListener(type, callback) {
    const handlers = this.listeners.get(type) ?? new Set()
    handlers.add(callback)
    this.listeners.set(type, handlers)
  }
  removeEventListener(type, callback) { this.listeners.get(type)?.delete(callback) }
  dispatch(type, event = {}) { for (const callback of this.listeners.get(type) ?? []) callback({ type, ...event }) }
  count(type) { return type ? this.listeners.get(type)?.size ?? 0 : [...this.listeners.values()].reduce((total, handlers) => total + handlers.size, 0) }
}

function environment({ reduced = false, visibility = 'visible', width = 800, height = 600 } = {}) {
  const query = new Events()
  query.matches = reduced
  query.set = (matches) => { query.matches = matches; query.dispatch('change', { matches }) }
  const window = new Events()
  window.matchMedia = () => query
  window.devicePixelRatio = 1
  const document = new Events()
  document.visibilityState = visibility
  let renders = 0
  const ctx = new Proxy({
    clearRect: () => renders++,
    drawImage: (source) => {
      assert.ok(source.width > 0 && source.height > 0, 'drawImage requires a nonempty source canvas')
    },
  }, {
    get: (target, key) => target[key] ?? (() => {}),
    set: (target, key, value) => { target[key] = value; return true },
  })
  const size = { width, height }
  const canvas = { getContext: () => ctx, getBoundingClientRect: () => ({ ...size, left: 0, top: 0 }) }
  document.createElement = () => ({ getContext: () => ctx })
  const frames = new Map()
  const observers = []
  let nextFrame = 0
  let time = 0
  let effect
  let cleanup
  class ResizeObserver {
    connected = false
    constructor(callback) { this.callback = callback; observers.push(this) }
    observe() { this.connected = true }
    disconnect() { this.connected = false }
  }
  const exports = {}
  const imports = {
    react: { useEffect: (callback) => { effect = callback }, useRef: () => ({ current: canvas }) },
    'react/jsx-runtime': { jsx: () => ({}) },
    '../lib/pixelBurst': { BURST_EVENT: 'pixelfield:burst' },
  }
  vm.runInNewContext(output, {
    exports,
    require: (name) => { assert.ok(Object.hasOwn(imports, name)); return imports[name] },
    window, document, ResizeObserver,
    requestAnimationFrame: (callback) => { const id = ++nextFrame; frames.set(id, callback); return id },
    cancelAnimationFrame: (id) => frames.delete(id),
  }, { filename: 'src/components/PixelField.tsx' })
  exports.default({})
  const mount = () => { assert.equal(cleanup, undefined); cleanup = effect() }
  const unmount = () => { cleanup?.(); cleanup = undefined }
  mount()
  return {
    query, window, document, frames, observers, mount, unmount,
    get renders() { return renders },
    tick() {
      const next = frames.entries().next().value
      assert.ok(next, 'Expected a pending animation frame')
      const [id, callback] = next
      frames.delete(id)
      callback(time += 16.67)
    },
    visibility(state) { document.visibilityState = state; document.dispatch('visibilitychange') },
    resize(width = size.width, height = size.height) {
      Object.assign(size, { width, height })
      for (const observer of observers) if (observer.connected) observer.callback()
    },
  }
}

function scenario(name, options, run) {
  test(name, () => {
    const env = environment(options)
    try {
      run(env)
    } finally {
      env.unmount()
    }
  })
}

scenario('Dynamic reduce stops RAF and paints a still; no-preference resumes one RAF', {}, (env) => {
  assert.equal(env.frames.size, 1)
  env.tick()
  const rendersBefore = env.renders
  env.query.set(true)
  assert.equal(env.frames.size, 0)
  assert.equal(env.renders, rendersBefore + 1)
  env.query.set(false)
  assert.equal(env.frames.size, 1)
  env.tick()
  assert.equal(env.renders, rendersBefore + 2)
})

scenario('Initially reduced becomes animated without remount', { reduced: true }, (env) => {
  assert.equal(env.frames.size, 0)
  assert.ok(env.renders > 0)
  env.query.set(false)
  assert.equal(env.frames.size, 1)
  env.tick()
  env.query.set(true)
  assert.equal(env.frames.size, 0)
})

scenario('Initial hidden mount never starts RAF', { visibility: 'hidden' }, (env) => {
  assert.equal(env.frames.size, 0)
  env.visibility('visible')
  assert.equal(env.frames.size, 1)
})

scenario('Hidden tab stays stopped through preference changes', {}, (env) => {
  env.visibility('hidden')
  assert.equal(env.frames.size, 0)
  env.query.set(true)
  assert.equal(env.frames.size, 0)
  env.query.set(false)
  assert.equal(env.frames.size, 0)
  env.visibility('visible')
  assert.equal(env.frames.size, 1)
  env.query.set(true)
  env.visibility('hidden')
  env.visibility('visible')
  assert.equal(env.frames.size, 0)
})

scenario('Repeated visible/change events never duplicate RAF', {}, (env) => {
  for (let index = 0; index < 5; index++) {
    env.visibility('visible')
    env.query.set(false)
    assert.equal(env.frames.size, 1)
    env.tick()
  }
})

scenario('Reduced resize and bursts remain static', { reduced: true }, (env) => {
  env.resize()
  const before = env.renders
  env.window.dispatch('pixelfield:burst', { detail: { x: 80, y: 60 } })
  assert.equal(env.renders, before + 1)
  assert.equal(env.frames.size, 0)
})

scenario('Initially empty animated canvas paints after gaining size', { width: 0, height: 0 }, (env) => {
  env.tick()
  assert.equal(env.renders, 0)
  assert.equal(env.frames.size, 1)
  env.resize(800, 600)
  env.tick()
  assert.equal(env.renders, 1)
})

scenario('Initially empty reduced canvas paints a still after gaining size', { reduced: true, width: 0, height: 0 }, (env) => {
  assert.equal(env.renders, 0)
  assert.equal(env.frames.size, 0)
  env.resize(800, 600)
  assert.equal(env.renders, 1)
  assert.equal(env.frames.size, 0)
})

scenario('Animated resize through either empty dimension resumes drawing', {}, (env) => {
  env.tick()
  for (const [width, height] of [[0, 600], [800, 0], [0, 0]]) {
    const before = env.renders
    env.resize(width, height)
    env.tick()
    assert.equal(env.renders, before)
    env.resize(800, 600)
    env.tick()
    assert.equal(env.renders, before + 1)
    assert.equal(env.frames.size, 1)
  }
})

scenario('Empty reduced resize, burst and media changes recover without invalid drawing', { reduced: true }, (env) => {
  const before = env.renders
  for (const [width, height] of [[0, 600], [800, 0], [0, 0]]) {
    env.resize(width, height)
    env.window.dispatch('pixelfield:burst', { detail: { x: 80, y: 60 } })
    env.query.set(false)
    env.tick()
    env.query.set(true)
    assert.equal(env.renders, before)
    assert.equal(env.frames.size, 0)
  }
  env.resize(800, 600)
  assert.equal(env.renders, before + 1)
  assert.equal(env.frames.size, 0)
})

scenario('Unmount at zero size cancels RAF and observer; remount recovers', {}, (env) => {
  env.resize(0, 0)
  env.unmount()
  assert.equal(env.frames.size, 0)
  assert.equal(env.query.count(), 0)
  assert.equal(env.window.count(), 0)
  assert.equal(env.document.count(), 0)
  assert.ok(env.observers.every((observer) => !observer.connected))
  env.resize(800, 600)
  env.mount()
  env.tick()
  assert.equal(env.renders, 1)
  assert.equal(env.frames.size, 1)
  assert.equal(env.observers.filter((observer) => observer.connected).length, 1)
})

scenario('Unmount removes media/input/visibility listeners and RAF; remount is singular', {}, (env) => {
  assert.equal(env.query.count('change'), 1)
  const mountedWindowListeners = env.window.count()
  const mountedDocumentListeners = env.document.count()
  for (let index = 0; index < 5; index++) {
    env.unmount()
    assert.equal(env.frames.size, 0)
    assert.equal(env.query.count(), 0)
    assert.equal(env.window.count(), 0)
    assert.equal(env.document.count(), 0)
    assert.ok(env.observers.every((observer) => !observer.connected))
    const before = env.renders
    env.query.set(true)
    env.query.set(false)
    env.visibility('visible')
    assert.equal(env.frames.size, 0)
    assert.equal(env.renders, before)
    env.mount()
    assert.equal(env.frames.size, 1)
    assert.equal(env.query.count('change'), 1)
    assert.equal(env.window.count(), mountedWindowListeners)
    assert.equal(env.document.count(), mountedDocumentListeners)
    assert.equal(env.observers.filter((observer) => observer.connected).length, 1)
  }
})

