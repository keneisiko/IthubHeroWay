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

async function leaderboard(request = apiResponse) {
  const state = []
  const refs = []
  const effects = []
  let cursor = 0
  let firstRender = true
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
    useCallback: (callback) => callback,
    useEffect(effect) {
      if (firstRender) effects.push(effect)
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
    const tree = module.exports.default()
    firstRender = false
    return tree
  }
  render()
  for (const effect of effects) effect()
  await flush()
  return { render, LoadError }
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
