import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { resolve } from 'node:path'
import test from 'node:test'
import ts from 'typescript'
import axios from 'axios'
import 'react-hot-toast'

const frontend = resolve(import.meta.dirname, '../..')
const transpile = (source) => ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2023, module: ts.ModuleKind.ESNext },
}).outputText
const moduleUrl = (source) => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
const authUrl = moduleUrl(transpile(await readFile(resolve(frontend, 'src/auth.ts'), 'utf8')))
let fixtureId = 0

function deferred() {
  let resolve
  const promise = new Promise((done) => { resolve = done })
  return { promise, resolve }
}

async function fixture(t, handler) {
  const server = createServer((request, response) => {
    response.setHeader('Content-Type', 'application/json')
    void handler(request, response)
  })
  await new Promise((done) => server.listen(0, '127.0.0.1', done))
  t.after(async () => {
    server.closeAllConnections()
    await new Promise((done) => server.close(done))
  })

  const storage = new Map([
    ['access_token', 'expired-access-token'],
    ['refresh_token', 'valid-refresh-token'],
  ])
  const visibilityListeners = []
  let lockQueue = Promise.resolve()
  const globals = {
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, String(value)),
      removeItem: (key) => storage.delete(key),
    },
    document: {
      visibilityState: 'visible',
      addEventListener(event, listener) {
        if (event === 'visibilitychange') visibilityListeners.push(listener)
      },
    },
    window: { location: { pathname: '/dashboard' } },
    navigator: {
      locks: {
        request(_name, run) {
          const task = lockQueue.then(run)
          lockQueue = task.catch(() => {})
          return task
        },
      },
    },
  }
  for (const [key, value] of Object.entries(globals)) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, key)
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
    t.after(() => {
      if (previous) Object.defineProperty(globalThis, key, previous)
      else delete globalThis[key]
    })
  }

  const baseURL = `http://127.0.0.1:${server.address().port}`
  const source = (await readFile(resolve(frontend, 'src/api.ts'), 'utf8'))
    .replace("from 'axios'", `from '${import.meta.resolve('axios')}'`)
    .replace("from 'react-hot-toast'", `from '${import.meta.resolve('react-hot-toast')}'`)
    .replace("from './auth'", `from '${authUrl}'`)
    .replace('import.meta.env.VITE_API_URL', JSON.stringify(baseURL))
  const newTab = async () => {
    const { default: api } = await import(moduleUrl(`${transpile(source)}\n// fixture-${fixtureId++}`))
    return api
  }
  return {
    api: await newTab(),
    newTab,
    storage,
    visibility(state) {
      globals.document.visibilityState = state
      for (const listener of visibilityListeners) listener()
    },
  }
}

test('deduplicated 401 consumers both retry after one token refresh', { timeout: 5_000 }, async (t) => {
  const started = deferred()
  const release = deferred()
  let profileRequests = 0
  let refreshRequests = 0
  const { api, storage } = await fixture(t, async (request, response) => {
    if (request.url === '/api/v1/auth/jwt/refresh/' && request.method === 'POST') {
      refreshRequests++
      response.end('{"access":"fresh-access-token","refresh":"rotated-refresh-token"}')
      return
    }
    profileRequests++
    if (request.headers.authorization === 'Bearer fresh-access-token') {
      response.end('{"name":"student"}')
      return
    }
    started.resolve()
    await release.promise
    response.statusCode = 401
    response.end('{"detail":"Token expired"}')
  })

  const first = api.get('/profile')
  const second = api.get('/profile')
  const settled = Promise.allSettled([first, second])
  await started.promise
  release.resolve()
  const results = await settled

  assert.deepEqual(results.map((result) => result.status), ['fulfilled', 'fulfilled'])
  assert.deepEqual(results.map((result) => result.value.data), [
    { name: 'student' },
    { name: 'student' },
  ])
  assert.equal(refreshRequests, 1)
  assert.equal(profileRequests, 2)
  const session = JSON.parse(storage.get('hero-path-session'))
  assert.equal(session.access, 'fresh-access-token')
  assert.equal(session.refresh, 'rotated-refresh-token')
  assert.equal(storage.has('access_token'), false)
})

test('deduplicated HTTP failures preserve each consumer config and Axios metadata', { timeout: 5_000 }, async (t) => {
  const started = deferred()
  const release = deferred()
  let requests = 0
  const { api } = await fixture(t, async (_request, response) => {
    requests++
    started.resolve()
    await release.promise
    response.statusCode = 409
    response.end('{"detail":"Conflict"}')
  })

  const first = api.get('/conflict', { headers: { 'X-Consumer': 'first' } })
  const second = api.get('/conflict', { headers: { 'X-Consumer': 'second' } })
  const settled = Promise.allSettled([first, second])
  await started.promise
  release.resolve()
  const results = await settled

  assert.deepEqual(results.map((result) => result.status), ['rejected', 'rejected'])
  const errors = results.map((result) => result.reason)
  assert.notStrictEqual(errors[0], errors[1])
  assert.deepEqual(errors.map((error) => error.config.headers.get('X-Consumer')), ['first', 'second'])
  for (const error of errors) {
    assert.ok(axios.isAxiosError(error))
    assert.equal(error.code, 'ERR_BAD_REQUEST')
    assert.equal(error.status, 409)
    assert.equal(error.response.status, 409)
    assert.deepEqual(error.response.data, { detail: 'Conflict' })
    assert.strictEqual(error.response.config, error.config)
  }
  assert.equal(requests, 1)
})

test('a GET started before a mutation cannot satisfy later reads or repopulate the cache', { timeout: 5_000 }, async (t) => {
  const started = deferred()
  const release = deferred()
  let value = 0
  let reads = 0
  const { api } = await fixture(t, async (request, response) => {
    if (request.method === 'POST') {
      value = 1
      response.end('{"value":1}')
      return
    }
    const snapshot = value
    reads++
    if (reads === 1) {
      started.resolve()
      await release.promise
    }
    response.end(JSON.stringify({ value: snapshot }))
  })

  const before = api.get('/value')
  await started.promise
  await api.post('/mutation')
  const after = api.get('/value')
  release.resolve()
  const [oldResponse, newResponse] = await Promise.all([before, after])

  assert.equal(oldResponse.data.value, 0)
  assert.equal(newResponse.data.value, 1)
  assert.equal((await api.get('/value')).data.value, 1)
  assert.equal(reads, 2)
})

test('successful mutations invalidate GET responses completed while the write was pending', { timeout: 5_000 }, async (t) => {
  let value = 0
  let mutationStarted
  let mutationRelease
  const { api } = await fixture(t, async (request, response) => {
    if (request.method !== 'GET') {
      mutationStarted.resolve()
      await mutationRelease.promise
      value++
    }
    response.end(JSON.stringify({ value }))
  })

  assert.equal((await api.get('/value')).data.value, 0)
  for (const [index, method] of ['post', 'patch', 'put', 'delete'].entries()) {
    mutationStarted = deferred()
    mutationRelease = deferred()
    const mutation = api[method]('/mutation')
    await mutationStarted.promise
    assert.equal((await api.get('/value')).data.value, index)
    mutationRelease.resolve()
    await mutation
    assert.equal((await api.get('/value')).data.value, index + 1, method)
  }
})

test('visibility invalidation detaches old GETs without removing the replacement in flight', { timeout: 5_000 }, async (t) => {
  const oldStarted = deferred()
  const oldRelease = deferred()
  const newRelease = deferred()
  let value = 0
  let reads = 0
  const { api, visibility } = await fixture(t, async (request, response) => {
    if (request.url === '/barrier') {
      response.end('{}')
      return
    }
    const snapshot = value
    reads++
    if (reads === 1) {
      oldStarted.resolve()
      await oldRelease.promise
    } else {
      await newRelease.promise
    }
    response.end(JSON.stringify({ value: snapshot }))
  })

  const before = api.get('/value')
  await oldStarted.promise
  value = 1
  visibility('hidden')
  visibility('visible')
  const after = api.get('/value')
  await api.get('/barrier')
  oldRelease.resolve()
  assert.equal((await before).data.value, 0)
  const follower = api.get('/value')
  newRelease.resolve()
  const responses = await Promise.all([after, follower])

  assert.deepEqual(responses.map((response) => response.data.value), [1, 1])
  assert.equal((await api.get('/value')).data.value, 1)
  assert.equal(reads, 2)
})


test('two tabs share a rotation and both retry with the new access token', { timeout: 5_000 }, async (t) => {
  const expiredRequests = deferred()
  const releaseRefresh = deferred()
  let expiredReads = 0
  let refreshRequests = 0
  const { api, newTab } = await fixture(t, async (request, response) => {
    if (request.url === '/api/v1/auth/jwt/refresh/') {
      refreshRequests++
      await releaseRefresh.promise
      response.end('{"access":"fresh-access-token","refresh":"rotated-refresh-token"}')
      return
    }
    if (request.headers.authorization === 'Bearer expired-access-token') {
      if (++expiredReads === 2) expiredRequests.resolve()
      response.statusCode = 401
      response.end('{}')
      return
    }
    response.end(JSON.stringify({ bearer: request.headers.authorization }))
  })

  const otherTab = await newTab()
  const results = Promise.all([api.get('/profile'), otherTab.get('/profile')])
  await expiredRequests.promise
  releaseRefresh.resolve()
  assert.deepEqual((await results).map(({ data }) => data.bearer), [
    'Bearer fresh-access-token',
    'Bearer fresh-access-token',
  ])
  assert.equal(refreshRequests, 1)
})

test('a delayed 401 cannot retry a mutation after an account switch', { timeout: 5_000 }, async (t) => {
  const started = deferred()
  const release = deferred()
  let requests = 0
  const { api, storage } = await fixture(t, async (_request, response) => {
    requests++
    started.resolve()
    await release.promise
    response.statusCode = 401
    response.end('{}')
  })

  const result = assert.rejects(api.post('/mutation', {}), { status: 401 })
  await started.promise
  storage.set('hero-path-session', JSON.stringify({
    id: 'other-account',
    access: 'other-access',
    refresh: 'other-refresh',
  }))
  release.resolve()
  await result
  assert.equal(requests, 1)
  assert.equal(JSON.parse(storage.get('hero-path-session')).id, 'other-account')
})
