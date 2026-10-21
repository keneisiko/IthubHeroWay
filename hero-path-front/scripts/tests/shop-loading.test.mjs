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
const refs = declarations.filter((node) => ts.isCallExpression(node.initializer) && node.initializer.expression.getText(ast) === 'useRef')
const loader = declarations.find((node) => node.name.getText(ast) === 'loadShop')
assert.ok(loader, 'Shop must declare the callback under test')

const compile = (text) => ts.transpileModule(text, {
  compilerOptions: { target: ts.ScriptTarget.ES2023, module: ts.ModuleKind.ESNext },
}).outputText
const code = compile(`function makeLoadShop(activeTab: number) {
  ${refs.map((node) => `const ${node.getText(ast)}`).join('\n')}
  const ${loader.getText(ast)}
  return loadShop
}`)
const apiData = await import(`data:text/javascript;base64,${Buffer.from(compile(
  await readFile(resolve(frontend, 'src/lib/apiData.ts'), 'utf8'),
)).toString('base64')}`)
const flush = () => new Promise((done) => setImmediate(done))

function fixture() {
  const state = { products: [], purchases: [], history: [], coins: '0', loading: false, switching: false }
  const toasts = []
  const pending = []
  const savedRefs = []
  let refIndex = 0
  const sandbox = {
    ...apiData,
    useCallback: (callback) => callback,
    useRef(initial) {
      const index = refIndex++
      savedRefs[index] ??= { current: initial }
      return savedRefs[index]
    },
    api: {
      get(url, config) {
        return new Promise((resolve, reject) => pending.push({ url, config, resolve, reject }))
      },
    },
    addToast: (message, type) => toasts.push({ message, type }),
  }
  for (const name of ['Products', 'Purchases', 'PurchasedCodes', 'History', 'Coins', 'Me', 'Loading', 'Switching']) {
    sandbox[`set${name}`] = (value) => { state[name[0].toLowerCase() + name.slice(1)] = value }
  }
  runInNewContext(code, sandbox)

  return {
    state,
    toasts,
    load(tab, options) {
      refIndex = 0
      const start = pending.length
      sandbox.makeLoadShop(tab)(options)
      const requests = pending.slice(start)
      assert.equal(requests.length, 4)
      assert.equal(requests[0].config.params.item_type, ['cosmetic', 'boost', 'other', 'service'][tab])
      return {
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
