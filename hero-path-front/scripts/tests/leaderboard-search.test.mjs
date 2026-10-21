import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import * as jsx from 'react/jsx-runtime'
import ts from 'typescript'

const frontend = resolve(import.meta.dirname, '../..')
const source = await readFile(resolve(frontend, 'src/pages/Leaderboard.tsx'), 'utf8')
const transpile = (text) => ts.transpileModule(text, {
  compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2023,
  },
}).outputText
const apiData = { exports: {} }
runInNewContext(transpile(await readFile(resolve(frontend, 'src/lib/apiData.ts'), 'utf8')), {
  module: apiData, exports: apiData.exports,
})

async function apiResponse(url) {
  if (url === '/api/v1/leaderboard/agents/') {
    return { data: { count: 1, results: [
      { username: 'ivanov', callsign: 'Сокол', rating_current: '400.00', level: 1 },
    ] } }
  }
  if (url === '/api/v1/squads/leaderboard/') return { data: [] }
  if (url === '/api/v1/rating/me/') return { data: { username: 'someone-else', rank: 2 } }
  throw new Error(`Unexpected API request: ${url}`)
}

async function flush() {
  for (let i = 0; i < 12; i++) await Promise.resolve()
}

const sameDeps = (previous, current) => previous && current
  && previous.length === current.length
  && current.every((value, index) => Object.is(value, previous[index]))

async function leaderboard(request = apiResponse) {
  const state = []
  const refs = []
  const callbacks = []
  const effectDeps = []
  const effects = []
  let cursor = 0
  let callbackCursor = 0
  let effectCursor = 0
  const react = {
    useState(initial) {
      const index = cursor++
      if (!(index in state)) state[index] = initial
      return [state[index], (value) => {
        state[index] = typeof value === 'function' ? value(state[index]) : value
      }]
    },
    useRef(initial) {
      const index = cursor++
      return refs[index] ??= { current: initial }
    },
    useCallback(callback, deps) {
      const index = callbackCursor++
      if (!sameDeps(callbacks[index]?.deps, deps)) callbacks[index] = { callback, deps }
      return callbacks[index].callback
    },
    useEffect(effect, deps) {
      const index = effectCursor++
      if (sameDeps(effectDeps[index], deps)) return
      effectDeps[index] = deps
      effects.push(effect)
    },
  }
  const api = { get: request }
  const LoadError = () => null
  const module = { exports: {} }
  runInNewContext(transpile(source), {
    module,
    exports: module.exports,
    require(name) {
      if (name === 'react') return react
      if (name === 'react/jsx-runtime') return jsx
      if (name === 'react-router-dom') return { useNavigate: () => () => {} }
      if (name === '../api') return { __esModule: true, default: api }
      if (name === '../lib/apiData') return apiData.exports
      if (name === '../useCountUp') return { useCountUp: (value) => value }
      if (name === '../components/Avatar') return { __esModule: true, default: () => null }
      if (name === '../components/LoadError') return { __esModule: true, default: LoadError }
      throw new Error(`Unexpected import: ${name}`)
    },
    setTimeout,
    clearTimeout,
  })
  const render = () => {
    cursor = 0
    callbackCursor = 0
    effectCursor = 0
    return module.exports.default()
  }
  const runEffects = async () => {
    for (const effect of effects.splice(0)) effect()
    await flush()
  }
  render()
  await runEffects()
  return { render, runEffects, LoadError }
}

function find(node, predicate) {
  if (!node || typeof node !== 'object') return undefined
  if (predicate(node)) return node
  const children = node.props?.children
  for (const child of Array.isArray(children) ? children.flat(Infinity) : [children]) {
    const match = find(child, predicate)
    if (match) return match
  }
  return undefined
}

for (const [label, query, visible] of [
  ['username with a different callsign', ' IVANOV ', true],
  ['callsign', 'сОкОл', true],
  ['unmatched query', 'missing-agent', false],
]) {
  test(`leaderboard search: ${label}`, async () => {
    const harness = await leaderboard()
    const search = find(harness.render(), (node) => node.type === 'input' && node.props.type === 'search')
    assert.ok(search, 'loaded leaderboard has a search input')
    search.props.onChange({ target: { value: query } })

    const row = find(harness.render(), (node) => node.props?.className?.startsWith('leaderboard-item hover-lift'))
    assert.equal(Boolean(row), visible, 'search must preserve the matching returned agent')
    if (row) {
      assert.equal(find(row, (node) => node.props?.className === 'tag tag--title')?.props.children, 'Сокол')
    }
  })
}

test('failed initial load keeps retry available until a later attempt succeeds', async () => {
  let online = false
  const harness = await leaderboard((url) => online
    ? apiResponse(url)
    : Promise.reject(new Error('Network unavailable')))
  const firstError = find(harness.render(), (node) => node.type === harness.LoadError)
  assert.ok(firstError, 'initial failure shows a retry action')

  firstError.props.onRetry()
  const retryInProgress = harness.render()
  await flush()
  const retryError = find(harness.render(), (node) => node.type === harness.LoadError)
  assert.ok(retryError, 'a second failure must keep the retry action visible')
  assert.ok(find(retryInProgress, (node) => node.props?.className === 'loading-spinner'))

  online = true
  retryError.props.onRetry()
  await flush()
  const loaded = harness.render()
  assert.equal(find(loaded, (node) => node.type === harness.LoadError), undefined)
  assert.ok(find(loaded, (node) => node.props?.className === 'tag tag--title'), 'retry can recover the leaderboard')
})

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function agentResponse(username, callsign) {
  return { data: { results: [{ username, callsign, rating_current: 10, level: 1 }] } }
}

async function submitSearch(harness, query) {
  find(harness.render(), (node) => node.type === 'input' && node.props.type === 'search')
    .props.onChange({ target: { value: query } })
  find(harness.render(), (node) => node.type === 'form' && node.props.role === 'search')
    .props.onSubmit({ preventDefault() {} })
  harness.render()
  await harness.runEffects()
}

async function pendingSearches() {
  const pending = new Map()
  const harness = await leaderboard((url, config) => {
    if (url === '/api/v1/leaderboard/agents/' && config?.params.search) {
      const response = deferred()
      pending.set(config.params.search, response)
      return response.promise
    }
    return apiResponse(url)
  })
  await submitSearch(harness, 'ivanov')
  await submitSearch(harness, 'petrov')
  return { harness, pending }
}

test('an older search success cannot overwrite the newer search result', async () => {
  const { harness, pending } = await pendingSearches()
  pending.get('petrov').resolve(agentResponse('petrov', 'Орёл'))
  await flush()
  assert.equal(find(harness.render(), (node) => node.props?.className === 'tag tag--title')?.props.children, 'Орёл')

  pending.get('ivanov').resolve(agentResponse('ivanov', 'Сокол'))
  await flush()
  assert.equal(find(harness.render(), (node) => node.props?.className === 'tag tag--title')?.props.children, 'Орёл')
})

for (const olderOutcome of ['success', 'failure']) {
  test(`an older search ${olderOutcome} cannot stop the newer request's loading indicator`, async () => {
    const { harness, pending } = await pendingSearches()
    if (olderOutcome === 'success') pending.get('ivanov').resolve(agentResponse('ivanov', 'Сокол'))
    else pending.get('ivanov').reject(new Error('Older request failed'))
    await flush()

    assert.equal(find(harness.render(), (node) => node.props?.['aria-busy'] !== undefined)?.props['aria-busy'], true)
    pending.get('petrov').resolve(agentResponse('petrov', 'Орёл'))
    await flush()
    const loaded = harness.render()
    assert.equal(find(loaded, (node) => node.props?.['aria-busy'] !== undefined)?.props['aria-busy'], false)
    assert.equal(find(loaded, (node) => node.props?.className === 'tag tag--title')?.props.children, 'Орёл')
  })
}

test('an older retry failure cannot leave an error over a newer successful retry', async () => {
  let initial = true
  const retries = []
  const harness = await leaderboard((url, config) => {
    if (url === '/api/v1/leaderboard/agents/' && config?.params.page_size === 20) {
      if (initial) {
        initial = false
        return Promise.reject(new Error('Initial request failed'))
      }
      const response = deferred()
      retries.push(response)
      return response.promise
    }
    return apiResponse(url)
  })
  const retry = find(harness.render(), (node) => node.type === harness.LoadError)?.props.onRetry
  assert.equal(typeof retry, 'function')
  retry()
  retry()
  assert.equal(retries.length, 2)

  retries[0].reject(new Error('Older retry failed'))
  await flush()
  assert.ok(find(harness.render(), (node) => node.props?.className === 'loading-spinner'))
  retries[1].resolve(agentResponse('ivanov', 'Сокол'))
  await flush()
  const loaded = harness.render()
  assert.equal(find(loaded, (node) => node.type === harness.LoadError), undefined)
  assert.equal(find(loaded, (node) => node.props?.className === 'tag tag--title')?.props.children, 'Сокол')
})
