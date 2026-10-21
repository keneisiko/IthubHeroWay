import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import ts from 'typescript'

const frontend = resolve(import.meta.dirname, '../..')
const source = await readFile(resolve(frontend, 'src/PageTransition.tsx'), 'utf8')
const code = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText

function transition(reduced = false) {
  let pathname = '/dashboard'
  let children = 'dashboard'
  const slots = []
  let cursor = 0
  let dirty = false
  let mounted = true
  let effects = []
  let tree
  let now = 0
  let nextTimer = 0
  const timers = new Map()
  const scrolls = []
  const listeners = new Set()
  const query = {
    matches: reduced,
    addEventListener: (_type, callback) => listeners.add(callback),
    removeEventListener: (_type, callback) => listeners.delete(callback),
  }
  const react = {
    useState(initial) {
      const index = cursor++
      slots[index] ??= { value: typeof initial === 'function' ? initial() : initial }
      return [slots[index].value, (next) => {
        const value = typeof next === 'function' ? next(slots[index].value) : next
        if (!Object.is(slots[index].value, value)) { slots[index].value = value; dirty = true }
      }]
    },
    useRef(initial) { return slots[cursor++] ??= { current: initial } },
    useEffect(callback, deps) {
      const index = cursor++
      const previous = slots[index]
      if (previous?.deps && deps?.length === previous.deps.length && deps.every((value, i) => Object.is(value, previous.deps[i]))) return
      slots[index] = { deps, cleanup: previous?.cleanup }
      effects.push(() => { slots[index].cleanup?.(); slots[index].cleanup = callback() })
    },
  }
  const window = {
    matchMedia: () => query,
    setTimeout(callback, delay) { const id = ++nextTimer; timers.set(id, { at: now + delay, callback }); return id },
    clearTimeout: (id) => timers.delete(id),
    scrollTo: (...args) => scrolls.push(args),
  }
  const jsx = (type, props) => ({ type, props })
  const exports = {}
  runInNewContext(code, {
    exports, window,
    require(name) {
      if (name === 'react') return react
      if (name === 'react/jsx-runtime') return { jsx, jsxs: jsx }
      if (name === 'react-router-dom') return { useLocation: () => ({ pathname }) }
      if (name === './components/navItems') return { navItems: ['/dashboard', '/profile', '/quests', '/shop'].map((path) => ({ path })) }
      throw new Error(`Unexpected import: ${name}`)
    },
  })
  const render = () => {
    if (!mounted) return
    for (let pass = 0; pass < 20; pass++) {
      dirty = false
      cursor = 0
      tree = exports.default({ children })
      const pending = effects
      effects = []
      pending.forEach((effect) => effect())
      if (!dirty) return
    }
    throw new Error('PageTransition did not settle')
  }
  render()
  return {
    timers, scrolls, listeners,
    get content() { return tree.props.children[0].props.children },
    get contentStyle() { return tree.props.children[0].props.style },
    get contentClass() { return tree.props.children[0].props.className },
    navigate(path, content) { pathname = path; children = content; render() },
    rerender(content) { children = content; render() },
    reduce(matches) { query.matches = matches; [...listeners].forEach((callback) => callback({ matches })); render() },
    advance(ms) {
      const target = now + ms
      while (true) {
        const next = [...timers.entries()].filter(([, timer]) => timer.at <= target).sort((a, b) => a[1].at - b[1].at)[0]
        if (!next) break
        const [id, timer] = next
        timers.delete(id)
        now = timer.at
        timer.callback()
        render()
      }
      now = target
    },
    unmount() {
      mounted = false
      slots.forEach((slot) => slot?.cleanup?.())
    },
  }
}

test('normal navigation preserves cover, content swap and uncover timing', () => {
  const page = transition()
  page.navigate('/profile', 'profile')
  assert.equal(page.content, 'dashboard')
  assert.equal(page.contentStyle.opacity, 0)
  page.advance(279)
  assert.equal(page.content, 'dashboard')
  page.advance(1)
  assert.equal(page.content, 'profile')
  assert.equal(page.contentClass, 'route-in')
  assert.equal(page.contentStyle.opacity, 1)
  page.advance(339)
  assert.equal(page.contentClass, 'route-in')
  page.advance(1)
  assert.equal(page.contentClass, undefined)
  assert.equal(page.timers.size, 0)
  assert.equal(page.scrolls.length, 1)
  page.unmount()
})

test('rapid navigation shows only the latest route after its own cover', () => {
  const page = transition()
  page.navigate('/profile', 'profile')
  page.advance(100)
  page.navigate('/shop', 'shop')
  page.advance(180)
  assert.equal(page.content, 'dashboard')
  assert.equal(page.contentStyle.opacity, 0)
  page.advance(100)
  assert.equal(page.content, 'shop')
  page.advance(340)
  assert.equal(page.content, 'shop')
  assert.equal(page.scrolls.length, 1)
  page.unmount()
})

test('same-route child rerenders do not cancel an active navigation', () => {
  const page = transition()
  page.navigate('/profile', 'profile')
  page.advance(100)
  page.rerender('profile updated')
  page.advance(180)
  assert.equal(page.content, 'profile updated')
  assert.equal(page.contentStyle.opacity, 1)
  assert.equal(page.scrolls.length, 1)
  page.unmount()
})

test('unmount cancels cover timers and prevents a late scroll', () => {
  const page = transition()
  page.navigate('/profile', 'profile')
  page.unmount()
  assert.equal(page.timers.size, 0)
  assert.equal(page.listeners.size, 0)
  page.advance(1000)
  assert.equal(page.scrolls.length, 0)
})

test('unmount also clears the remaining uncover timer', () => {
  const page = transition()
  page.navigate('/profile', 'profile')
  page.advance(280)
  page.unmount()
  assert.equal(page.timers.size, 0)
  assert.equal(page.listeners.size, 0)
  page.advance(1000)
  assert.equal(page.scrolls.length, 1)
})

test('reduced motion displays the new route immediately without timers', () => {
  const page = transition(true)
  page.navigate('/profile', 'profile')
  assert.equal(page.content, 'profile')
  assert.equal(page.contentStyle.opacity, 1)
  assert.equal(page.contentClass, undefined)
  assert.equal(page.timers.size, 0)
  assert.equal(page.scrolls.length, 1)
  page.unmount()
})

test('enabling reduced motion finishes the latest pending route immediately', () => {
  const page = transition()
  page.navigate('/profile', 'profile')
  page.advance(100)
  page.navigate('/shop', 'shop')
  page.reduce(true)
  assert.equal(page.content, 'shop')
  assert.equal(page.contentStyle.opacity, 1)
  assert.equal(page.timers.size, 0)
  assert.equal(page.scrolls.length, 1)
  page.advance(1000)
  assert.equal(page.scrolls.length, 1)
  page.reduce(false)
  page.navigate('/profile', 'profile again')
  assert.equal(page.contentStyle.opacity, 0)
  page.advance(280)
  assert.equal(page.content, 'profile again')
  page.unmount()
})

test('changing motion preference while idle does not scroll the page', () => {
  const page = transition()
  page.reduce(true)
  page.reduce(false)
  assert.equal(page.content, 'dashboard')
  assert.equal(page.scrolls.length, 0)
  page.unmount()
})

test('turning reduced motion off keeps the latest route already displayed', () => {
  const page = transition(true)
  page.navigate('/profile', 'profile')
  page.navigate('/shop', 'shop')
  page.reduce(false)
  assert.equal(page.content, 'shop')
  assert.equal(page.contentStyle.opacity, 1)
  assert.equal(page.timers.size, 0)
  assert.equal(page.scrolls.length, 2)
  page.unmount()
})
