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
const code = compile(`function makeCallbacks(activeTab: number, products, showPurchase) {
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
  const state = { products: [], purchases: [], history: [], coins: '0', loading: true, switching: false }
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
  for (const name of ['Products', 'Purchases', 'PurchasedCodes', 'History', 'Coins', 'Me', 'Loading', 'Switching', 'ApplyingId', 'Ring', 'ShowPurchase', 'ActiveTab']) {
    sandbox[`set${name}`] = (value) => {
      const key = name[0].toLowerCase() + name.slice(1)
      state[key] = typeof value === 'function' ? value(state[key]) : value
    }
  }
  runInNewContext(code, sandbox)

  function render(tab, showPurchase = null) {
    activeTab = tab
    refIndex = 0
    return sandbox.makeCallbacks(tab, state.products, showPurchase)
  }

  function batch(requests) {
    assert.equal(requests.length, 4)
    return {
      category: requests[0].config.params.item_type,
      async resolve(code, coins = 100) {
        const responses = [
          [{ id: 1, code, title: code, price_coins: 10 }],
          [{ id: 1, coins_spent: 10, created_at: '2026-10-20', item: { code, title: code, item_type: 'other' } }],
          [],
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
    mutate(kind, purchase) {
      const start = pending.length
      const callbacks = render(activeTab, kind === 'buy' ? 1 : null)
      if (kind === 'buy') callbacks.handleBuy()
      else callbacks.togglePurchase(purchase)
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
