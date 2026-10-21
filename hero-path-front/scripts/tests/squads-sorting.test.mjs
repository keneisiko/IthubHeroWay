import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import * as jsx from 'react/jsx-runtime'
import ts from 'typescript'

const frontend = resolve(import.meta.dirname, '../..')
const sources = new Map(await Promise.all([
  'pages/Squads.tsx', 'useToasts.ts', 'lib/apiData.ts', 'lib/plural.ts',
].map(async (file) => [file, ts.transpileModule(await readFile(resolve(frontend, 'src', file), 'utf8'), {
  compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2023,
  },
}).outputText])))
const sameDeps = (previous, current) => previous && current
  && previous.length === current.length
  && current.every((value, index) => Object.is(value, previous[index]))
const alpha = [
  { username: 'ivanov', callsign: 'Иван', rating_current: 10 },
  { username: 'petrov', callsign: 'Пётр', rating_current: 20 },
]

async function flush() {
  for (let i = 0; i < 12; i++) await Promise.resolve()
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

async function squads() {
  const hooks = []
  const effects = []
  const pending = []
  let cursor = 0
  const react = {
    useState(initial) {
      const index = cursor++
      if (!(index in hooks)) hooks[index] = initial
      return [hooks[index], (value) => {
        hooks[index] = typeof value === 'function' ? value(hooks[index]) : value
      }]
    },
    useRef(initial) {
      const index = cursor++
      return hooks[index] ??= { current: initial }
    },
    useCallback(callback, deps) {
      const index = cursor++
      if (!sameDeps(hooks[index]?.deps, deps)) hooks[index] = { callback, deps }
      return hooks[index].callback
    },
    useEffect(effect, deps) {
      const index = cursor++
      if (sameDeps(hooks[index]?.deps, deps)) return
      const previous = hooks[index]
      const current = { deps }
      hooks[index] = current
      effects.push(() => {
        previous?.cleanup?.()
        current.cleanup = effect()
      })
    },
  }
  const api = {
    async get(url, config) {
      if (url === '/api/v1/squads/me/') {
        return { data: { my_squad: {
          code: 'alpha', name: 'Первый отряд', course: 3, agents_count: 2,
          squad_rating_avg: 15, delta_week: 0, place: 1, total_squads: 1,
        } } }
      }
      if (url === '/api/v1/squads/alpha/members/') {
        const response = deferred()
        pending.push({ ...response, ordering: config.params.ordering })
        return response.promise
      }
      throw new Error(`Unexpected request: ${url}`)
    },
  }
  const cache = new Map()
  function load(file) {
    if (cache.has(file)) return cache.get(file)
    const module = { exports: {} }
    runInNewContext(sources.get(file), {
      module,
      exports: module.exports,
      require(name) {
        if (name === 'react') return react
        if (name === 'react/jsx-runtime') return jsx
        if (name === 'react-router-dom') return { useNavigate: () => () => {} }
        if (name === '../api') return { __esModule: true, default: api }
        if (name === '../useToasts') return load('useToasts.ts')
        if (name === '../lib/apiData') return load('lib/apiData.ts')
        if (name === '../lib/plural') return load('lib/plural.ts')
        if (name.startsWith('../components/')) return { __esModule: true, default: () => null }
        throw new Error(`Unexpected import: ${name}`)
      },
      setTimeout(callback, delay) {
        const timer = setTimeout(callback, delay)
        timer.unref()
        return timer
      },
    })
    cache.set(file, module.exports)
    return module.exports
  }
  const Component = load('pages/Squads.tsx').default
  const render = () => {
    cursor = 0
    return Component()
  }
  const runEffects = async () => {
    for (const effect of effects.splice(0)) effect()
    await flush()
  }
  render()
  await runEffects()
  render()
  await runEffects()
  return { render, runEffects, pending }
}

function findAll(node, predicate) {
  if (!node || typeof node !== 'object') return []
  const children = node.props?.children
  return [
    ...(predicate(node) ? [node] : []),
    ...(Array.isArray(children) ? children.flat(Infinity) : [children])
      .flatMap((child) => findAll(child, predicate)),
  ]
}

async function sortByRating(harness) {
  findAll(harness.render(), (node) => node.type === 'button' && node.props.children === 'Сортировка')[0].props.onClick()
  const dropdown = findAll(harness.render(), (node) => typeof node.props?.onSelect === 'function')[0]
  dropdown.props.onSelect('track')
  dropdown.props.onClose()
  harness.render()
  await harness.runEffects()
  assert.deepEqual(harness.pending.map((request) => request.ordering), ['alpha', 'rating'])
}

const memberNames = (harness) => findAll(harness.render(), (node) =>
  node.props?.className === 'squad-member-tag squad-member-tag--dark').map((node) => node.props.children)
const errors = (harness) => findAll(harness.render(), (node) => node.props?.className === 'toast toast--error')

test('older alphabetical response cannot overwrite the selected rating order', async () => {
  const harness = await squads()
  await sortByRating(harness)
  harness.pending[1].resolve({ data: [...alpha].reverse() })
  await flush()
  assert.deepEqual(memberNames(harness), ['Пётр', 'Иван'])

  harness.pending[0].resolve({ data: alpha })
  await flush()
  assert.deepEqual(memberNames(harness), ['Пётр', 'Иван'])
})

test('a failure from an older ordering cannot show an error over the selected order', async () => {
  const harness = await squads()
  await sortByRating(harness)
  harness.pending[1].resolve({ data: [...alpha].reverse() })
  await flush()
  harness.pending[0].reject(new Error('Older alphabetical request failed'))
  await flush()

  assert.deepEqual(memberNames(harness), ['Пётр', 'Иван'])
  assert.equal(errors(harness).length, 0)
})

test('a failure of the selected ordering still shows its error', async () => {
  const harness = await squads()
  await sortByRating(harness)
  harness.pending[0].resolve({ data: alpha })
  harness.pending[1].reject(new Error('Selected rating request failed'))
  await flush()

  assert.equal(errors(harness).length, 1)
  assert.equal(errors(harness)[0].props.children, 'Не удалось обновить список участников')
})
