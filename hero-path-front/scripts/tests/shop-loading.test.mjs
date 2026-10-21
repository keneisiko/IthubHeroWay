import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import ts from 'typescript'

const frontend = resolve(import.meta.dirname, '../..')
const source = await readFile(resolve(frontend, 'src/pages/Shop.tsx'), 'utf8')
const ast = ts.createSourceFile('Shop.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
const shop = ast.statements.find((node) => ts.isFunctionDeclaration(node) && node.name?.text === 'Shop')
const declarations = shop.body.statements
  .filter(ts.isVariableStatement)
  .flatMap((statement) => [...statement.declarationList.declarations])
const callbacks = ['loadShop', 'togglePurchase', 'handleBuy']
const callbackDeclarations = declarations.filter((node) => callbacks.includes(node.name.getText(ast)) || (
  ts.isCallExpression(node.initializer) && node.initializer.expression.getText(ast) === 'useRef'
))
const loadEffect = shop.body.statements.find((node) => ts.isExpressionStatement(node)
  && ts.isCallExpression(node.expression)
  && node.expression.expression.getText(ast) === 'useEffect'
  && node.expression.arguments[1]?.getText(ast) === '[loadShop]')
assert.ok(loadEffect, 'Shop must load when its category callback changes')
let tabClick
function findTabClick(node) {
  if (ts.isJsxOpeningElement(node)) {
    const attributes = node.attributes.properties.filter(ts.isJsxAttribute)
    if (attributes.some((attribute) => attribute.name.getText(ast) === 'role' && attribute.initializer?.text === 'tab')) {
      tabClick = attributes.find((attribute) => attribute.name.getText(ast) === 'onClick')?.initializer?.expression
    }
  }
  ts.forEachChild(node, findTabClick)
}
findTabClick(shop)
assert.ok(tabClick, 'Shop tabs must expose their selection handler')

const compile = (text) => ts.transpileModule(text, {
  compilerOptions: { target: ts.ScriptTarget.ES2023, module: ts.ModuleKind.ESNext },
}).outputText
const code = compile(`function makeCallbacks(activeTab: number, products, purchases, showPurchase) {
  ${callbackDeclarations.map((node) => `const ${node.getText(ast)}`).join('\n')}
  return {
    ${callbacks.join(', ')},
    loadEffect: ${loadEffect.expression.arguments[0].getText(ast)},
    selectTab: (index: number) => (${tabClick.getText(ast)})(),
  }
}`)
const apiData = await import(`data:text/javascript;base64,${Buffer.from(compile(
  await readFile(resolve(frontend, 'src/lib/apiData.ts'), 'utf8'),
)).toString('base64')}`)
const flush = () => new Promise((done) => setImmediate(done))

function fixture() {
  const state = { products: [], purchases: [], history: [], coins: '0', loading: true, switching: false, applyingId: null, buying: false }
  const toasts = []
  const pending = []
  const savedRefs = []
  let refIndex = 0
  let activeTab = 0
  const request = (method, url, config) => new Promise((resolve, reject) => {
    pending.push({ method, url, config, resolve, reject })
  })
  const sandbox = {
    ...apiData,
    useCallback: (callback) => callback,
    useRef(initial) {
      const index = refIndex++
      savedRefs[index] ??= { current: initial }
      return savedRefs[index]
    },
    api: {
      get: (url, config) => request('GET', url, config),
      post: (url, config) => request('POST', url, config),
      delete: (url, config) => request('DELETE', url, config),
    },
    addToast: (message, type) => toasts.push({ message, type }),
    notifyBalanceChanged() {},
    celebrate() {},
  }
  for (const name of ['Products', 'Purchases', 'PurchasedCodes', 'History', 'Coins', 'Me', 'Loading', 'Switching', 'ApplyingId', 'Buying', 'Ring', 'ShowPurchase', 'ActiveTab']) {
    sandbox[`set${name}`] = (value) => {
      const key = name[0].toLowerCase() + name.slice(1)
      state[key] = typeof value === 'function' ? value(state[key]) : value
    }
  }
  runInNewContext(code, sandbox)

  function render(tab, showPurchase = null) {
    activeTab = tab
    refIndex = 0
    return sandbox.makeCallbacks(tab, state.products, state.purchases, showPurchase)
  }

  function batch(requests) {
    assert.equal(requests.length, 4)
    return {
      category: requests[0].config.params.item_type,
      async resolve(code, coins = 100, purchaseRows = [
        { id: 1, coins_spent: 10, created_at: '2026-10-20', item: { code, title: code, item_type: 'other' } },
      ], rewardRows = []) {
        const responses = [
          [{ id: 1, code, title: code, price_coins: 10 }],
          purchaseRows,
          rewardRows,
          { coins_balance: coins, username: code },
        ]
        requests.forEach((request, index) => request.resolve({ data: responses[index] }))
        await flush()
      },
      async reject() {
        requests[0].reject(new Error('Request failed'))
        await flush()
      },
    }
  }

  return {
    state,
    toasts,
    load(tab) {
      const start = pending.length
      if (tab !== activeTab) render(activeTab).selectTab(tab)
      render(tab).loadEffect()
      const result = batch(pending.slice(start))
      assert.equal(result.category, ['cosmetic', 'boost', 'other', 'service'][tab])
      return result
    },
    mutate(kind, purchase, repeat = 1) {
      const start = pending.length
      const callbacks = render(activeTab, kind === 'buy' ? 1 : null)
      for (let i = 0; i < repeat; i++) {
        if (kind === 'buy') callbacks.handleBuy()
        else callbacks.togglePurchase(purchase)
      }
      if (pending.length === start) return null
      assert.equal(pending.length, start + 1)
      const mutation = pending[start]
      assert.equal(mutation.method, kind === 'unapply' ? 'DELETE' : 'POST')
      return {
        async resolve() {
          const reloadStart = pending.length
          mutation.resolve({ data: {} })
          await flush()
          return batch(pending.slice(reloadStart))
        },
        async reject() {
          mutation.reject(new Error('Mutation failed'))
          await flush()
        },
      }
    },
  }
}

test('an older category response cannot overwrite the latest shop data', async () => {
  const { load, state } = fixture()
  const older = load(1)
  const latest = load(2)
  await latest.resolve('merch-item', 200)
  await older.resolve('boost-item', 50)

  assert.equal(state.products[0].code, 'merch-item')
  assert.equal(state.purchases[0].code, 'merch-item')
  assert.equal(state.history[0].name, 'merch-item')
  assert.equal(state.coins, '200')
  assert.equal(state.me.name, 'merch-item')
})

test('an older success keeps the latest category switching until its response arrives', async () => {
  const { load, state } = fixture()
  await load(0).resolve('cosmetic-item')
  const older = load(1)
  const latest = load(2)
  await older.resolve('boost-item')

  assert.equal(state.products[0].code, 'cosmetic-item')
  assert.equal(state.switching, true)
  await latest.resolve('merch-item')
  assert.equal(state.products[0].code, 'merch-item')
  assert.equal(state.switching, false)
})

test('an older error neither shows a toast nor finishes the latest category load', async () => {
  const { load, state, toasts } = fixture()
  const older = load(1)
  const latest = load(2)
  await older.reject()

  assert.deepEqual(toasts, [])
  assert.equal(state.loading, true)
  await latest.resolve('merch-item')
  assert.equal(state.products[0].code, 'merch-item')
  assert.equal(state.loading, false)
})

test('the current request still reports a failure and finishes loading', async () => {
  const { load, state, toasts } = fixture()
  await load(0).reject()

  assert.deepEqual(toasts, [{ message: 'Не удалось загрузить магазин', type: 'error' }])
  assert.equal(state.loading, false)
  assert.equal(state.switching, false)
})

for (const kind of ['apply', 'unapply', 'buy']) {
  test(`${kind} completion reloads the currently selected category`, async () => {
    const { load, mutate, state } = fixture()
    await load(0).resolve('cosmetic-item')
    const mutation = mutate(kind, { ...state.purchases[0], isApplied: kind === 'unapply' })
    await load(2).resolve('merch-item')
    const reload = await mutation.resolve()

    assert.equal(reload.category, 'other')
    await reload.resolve('merch-updated')
    assert.equal(state.products[0].code, 'merch-updated')
    assert.equal(state.switching, false)
  })
}

const owned = () => [
  { id: 1, code: 'frame-first', title: 'First frame', type: 'cosmetic', isApplied: true },
  { id: 2, code: 'frame-second', title: 'Second frame', type: 'cosmetic', isApplied: false },
  { id: 3, code: 'boost', title: 'Boost', type: 'boost', isApplied: true },
]
const applied = (state) => state.purchases.map((purchase) => [purchase.id, purchase.isApplied])

test('same-tick repeated apply sends one mutation', async () => {
  const { load, mutate, state } = fixture()
  await load(0).resolve('cosmetic-item')
  state.purchases = owned()
  const mutation = mutate('apply', state.purchases[1], 2)

  assert.equal(state.applyingId, 2)
  await mutation.reject()
})

test('a conflicting toggle cannot replace the current pending operation', async () => {
  const { load, mutate, state } = fixture()
  await load(0).resolve('cosmetic-item')
  state.purchases = owned()
  const mutation = mutate('apply', state.purchases[1])
  const conflicting = mutate('unapply', state.purchases[0])

  assert.equal(conflicting, null)
  assert.equal(state.applyingId, 2)
  await mutation.reject()
})

test('optimistic apply keeps one active purchase per type and restores its snapshot on error', async () => {
  const { load, mutate, state, toasts } = fixture()
  await load(0).resolve('cosmetic-item')
  state.purchases = owned()
  const mutation = mutate('apply', state.purchases[1])

  assert.deepEqual(applied(state), [[1, false], [2, true], [3, true]])
  await mutation.reject()
  assert.deepEqual(applied(state), [[1, true], [2, false], [3, true]])
  assert.equal(state.applyingId, null)
  assert.deepEqual(toasts, [{ message: 'Не удалось изменить покупку', type: 'error' }])
  assert.notEqual(mutate('unapply', state.purchases[0]), null)
})

test('optimistic unapply restores the active purchase when the request fails', async () => {
  const { load, mutate, state } = fixture()
  await load(0).resolve('cosmetic-item')
  state.purchases = owned()
  const mutation = mutate('unapply', state.purchases[0])

  assert.deepEqual(applied(state), [[1, false], [2, false], [3, true]])
  await mutation.reject()
  assert.deepEqual(applied(state), [[1, true], [2, false], [3, true]])
  assert.equal(state.applyingId, null)
})

test('the apply lock lasts through server reconciliation and then permits the next toggle', async () => {
  const { load, mutate, state } = fixture()
  await load(0).resolve('cosmetic-item')
  state.purchases = owned()
  const mutation = mutate('apply', state.purchases[1])
  const reload = await mutation.resolve()

  assert.equal(state.applyingId, 2)
  assert.equal(mutate('unapply', state.purchases[1]), null)
  await reload.resolve('cosmetic-item', 100, owned().map((purchase) => ({
    id: purchase.id,
    coins_spent: 10,
    created_at: '2026-10-20',
    is_applied: purchase.id === 2,
    item: { code: purchase.code, title: purchase.title, item_type: purchase.type },
  })))
  assert.deepEqual(applied(state), [[1, false], [2, true], [3, false]])
  assert.equal(state.applyingId, null)
  assert.notEqual(mutate('unapply', state.purchases[1]), null)
})

test('same-tick repeated buy sends one purchase request', async () => {
  const { load, mutate, state } = fixture()
  await load(0).resolve('cosmetic-item')
  const mutation = mutate('buy', undefined, 2)

  assert.equal(state.buying, true)
  await mutation.reject()
})

test('a buy cannot overlap an apply snapshot that might roll back', async () => {
  const { load, mutate, state } = fixture()
  await load(0).resolve('cosmetic-item')
  state.purchases = owned()
  const mutation = mutate('apply', state.purchases[1])

  assert.equal(mutate('buy'), null)
  await mutation.reject()
  assert.deepEqual(applied(state), [[1, true], [2, false], [3, true]])
  assert.notEqual(mutate('buy'), null)
})

test('a buy prevents apply until reconciliation and a later rollback preserves the new purchase', async () => {
  const { load, mutate, state } = fixture()
  await load(0).resolve('cosmetic-item')
  state.purchases = owned()
  const mutation = mutate('buy')

  assert.equal(mutate('apply', state.purchases[1]), null)
  const reload = await mutation.resolve()
  assert.equal(state.buying, true)
  assert.equal(mutate('apply', state.purchases[1]), null)
  await reload.resolve('cosmetic-item', 80, [...owned(), {
    id: 4, code: 'new-purchase', title: 'New purchase', type: 'other', isApplied: false,
  }].map((purchase) => ({
    id: purchase.id, coins_spent: 10, created_at: '2026-10-20', is_applied: purchase.isApplied,
    item: { code: purchase.code, title: purchase.title, item_type: purchase.type },
  })))
  assert.equal(state.buying, false)
  assert.equal(state.showPurchase, null)
  const apply = mutate('apply', state.purchases[1])
  await apply.reject()
  assert.deepEqual(applied(state), [[1, true], [2, false], [3, true], [4, false]])
})

test('a failed buy releases its lock and allows retry', async () => {
  const { load, mutate, state, toasts } = fixture()
  await load(0).resolve('cosmetic-item')
  await mutate('buy').reject()

  assert.equal(state.buying, false)
  assert.equal(state.showPurchase, null)
  assert.deepEqual(toasts, [{ message: 'Не удалось оформить покупку', type: 'error' }])
  assert.notEqual(mutate('buy'), null)
})

test('history combines purchases and rewards by their ISO timestamps while preserving Russian date labels', async () => {
  const { load, state } = fixture()
  await load(0).resolve('cosmetic-item', 100, [
    { id: 1, coins_spent: 10, created_at: '2026-10-19T10:00:00Z', item: { title: 'Old purchase' } },
    { id: 2, coins_spent: 30, created_at: '2026-10-21T08:00:00Z', item: { title: 'Morning purchase' } },
  ], [
    { quest_title: 'Evening reward', coins_delta: 5, granted_at: '2026-10-21T18:00:00Z' },
    { quest_title: 'Middle reward', coins_delta: 7, granted_at: '2026-10-20T12:00:00Z' },
  ])

  assert.deepEqual(Array.from(state.history, (row) => row.name), [
    'Evening reward', 'Morning purchase', 'Middle reward', 'Old purchase',
  ])
  assert.deepEqual(Array.from(state.history, (row) => row.date), [
    '21 октября 2026 г.', '21 октября 2026 г.', '20 октября 2026 г.', '19 октября 2026 г.',
  ])
  assert.deepEqual(Array.from(state.history, (row) => row.amount), ['+5', '-30', '+7', '-10'])
})
