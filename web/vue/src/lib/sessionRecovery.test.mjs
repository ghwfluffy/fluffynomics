import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { runInNewContext } from 'node:vm'
import ts from 'typescript'

test('expired sessions share OAuth recovery and retry once', async () => {
  const source = ts.transpile(readFileSync(new URL('./sessionRecovery.ts', import.meta.url), 'utf8'), { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 })
  const exports = {}
  let calls = 0
  runInNewContext(source, { exports, URL, AbortSignal, window: { location: { href: 'https://example.test/app/', origin: 'https://example.test' } }, fetch: async () => { calls++ } })
  const recover = exports.createSessionRecovery(() => '/api/auth/oauth/login')
  let attempts = 0
  const result = await recover(async () => ({ status: ++attempts === 1 ? 401 : 200 }))
  assert.equal(result.status, 200)
  assert.equal(attempts, 2)
  assert.equal(calls, 1)
  await recover(async () => ({ status: 403 }))
  await recover(async () => ({ status: 401 }), false)
  assert.equal(calls, 1)
})
