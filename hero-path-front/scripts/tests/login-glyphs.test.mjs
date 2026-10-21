import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import ts from 'typescript'

const frontend = resolve(import.meta.dirname, '../..')
const source = await readFile(resolve(frontend, 'src/pages/Login.tsx'), 'utf8')
const ast = ts.createSourceFile('Login.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
const declaration = ast.statements.find((node) => ts.isFunctionDeclaration(node) && node.name?.text === 'diffGlyphs')
assert.ok(declaration)
const exports = {}
runInNewContext(ts.transpileModule(`let glyphSeq = 0; ${declaration.getText(ast)}; exports.diffGlyphs = diffGlyphs`, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, { exports })
const diff = exports.diffGlyphs
const glyphs = (text) => Array.from(text, (ch, index) => ({ ch, id: index + 100 }))
const text = (values) => values.map((value) => value.ch).join('')

test('inserting after an emoji preserves the correct text and existing glyph identities', () => {
  const previous = glyphs('😀ab')
  const next = diff(previous, '😀Xab')
  assert.equal(text(next), '😀Xab')
  assert.equal(next.length, 4)
  assert.equal(next[0].id, previous[0].id)
  assert.equal(next[2].id, previous[1].id)
  assert.equal(next[3].id, previous[2].id)
  assert.ok(!previous.some((glyph) => glyph.id === next[1].id))
})

test('deleting after an emoji removes exactly the selected character', () => {
  const previous = glyphs('😀ab')
  const next = diff(previous, '😀b')
  assert.equal(text(next), '😀b')
  assert.equal(next.length, 2)
  assert.equal(next[0].id, previous[0].id)
  assert.equal(next[1].id, previous[2].id)
})

test('replacing emojis that share a UTF-16 surrogate does not produce a broken glyph', () => {
  const previous = glyphs('😀ab')
  const next = diff(previous, '😃ab')
  assert.equal(text(next), '😃ab')
  assert.equal(next.length, 3)
  assert.equal(next[1].id, previous[1].id)
  assert.equal(next[2].id, previous[2].id)
})

test('ASCII insertions preserve existing glyphs so only the inserted character animates', () => {
  const previous = glyphs('abc')
  const next = diff(previous, 'abXc')
  assert.equal(text(next), 'abXc')
  assert.equal(next[0].id, previous[0].id)
  assert.equal(next[1].id, previous[1].id)
  assert.equal(next[3].id, previous[2].id)
})

test('ASCII deletion and clearing preserve the displayed value', () => {
  const previous = glyphs('abc')
  const next = diff(previous, 'ac')
  assert.equal(text(next), 'ac')
  assert.equal(next[0].id, previous[0].id)
  assert.equal(next[1].id, previous[2].id)
  assert.equal(diff(next, '').length, 0)
})
