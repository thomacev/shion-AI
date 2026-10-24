import { expect, test, type Page } from '@playwright/test'
import type { Assistant, Conversation, Document, Message } from '../src/api/workspace'

const assistantId = '11111111-1111-4111-8111-111111111111'
const documentId = '22222222-2222-4222-8222-222222222222'
const assistant: Assistant = { id: assistantId, name: 'Research notes', description: 'A place to connect ideas.', system_prompt: 'Answer from documents.' }
const document: Document = { id: documentId, assistant_id: assistantId, filename: 'team-handbook.txt', status: 'ready', error_message: null, created_at: '2026-10-22T10:00:00Z' }

async function mockApi(page: Page, seeded = false) {
  const state = {
    signedIn: seeded, assistants: seeded ? [assistant] : [] as Assistant[],
    documents: seeded ? [{ ...document }] : [] as Document[],
    conversations: [] as Conversation[], messages: {} as Record<string, Message[]>,
    failMode: false, mixedAnswer: false, failUpload: false, failChat: false, failRefresh: false, expireProtected: false,
    failMessages: false, loginError: false, refreshCalls: 0, uploadCalls: 0, sendCalls: 0, polls: 0,
  }
  async function handler(route: import('@playwright/test').Route) {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()
    const respond = (data: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    if (path === '/auth/register') {
      expect(request.postDataJSON().full_name).toBe('Test Reader')
      return respond({ id: 'user', full_name: 'Test Reader', email: 'reader@example.com', is_active: true }, 201)
    }
    if (path === '/auth/login') {
      if (state.loginError) return respond({ detail: 'Invalid email or password' }, 401)
      expect(new URLSearchParams(request.postData() ?? '').get('username')).toBe('reader@example.com')
      state.signedIn = true
      return respond({ access_token: 'not-used-by-client', refresh_token: 'not-used-by-client' })
    }
    if (path === '/auth/refresh') {
      state.refreshCalls++
      await new Promise(resolve => setTimeout(resolve, 100))
      if (!state.signedIn || state.failRefresh) return respond({ detail: 'Session expired' }, 401)
      state.expireProtected = false
      return respond({ access_token: 'refreshed' })
    }
    if (!state.signedIn || state.expireProtected) return respond({ detail: 'Not authenticated' }, 401)
    if (path === '/auth/logout') { state.signedIn = false; return route.fulfill({ status: 204 }) }
    if (path === '/assistants') {
      if (method === 'POST') {
        const item = { ...assistant, ...request.postDataJSON() }
        state.assistants.push(item)
        return respond(item, 201)
      }
      return respond(state.assistants)
    }
    if (path.endsWith('/file')) return route.fulfill({ contentType: 'text/plain', body: 'Support operates Monday to Friday, 09:00 to 18:00.' })
    if (path.endsWith('/retry')) {
      state.documents[0].status = 'processing'
      state.documents[0].error_message = null
      state.polls = 0
      return respond(state.documents[0], 202)
    }
    if (path.endsWith('/documents')) {
      if (method === 'POST') {
        state.uploadCalls++
        if (state.failUpload) return respond({ detail: 'File exceeds 10MB' }, 413)
        expect(request.headers()['content-type']).toContain('multipart/form-data')
        state.documents.push({ ...document, status: 'pending' })
        state.polls = 0
        return respond(state.documents[0], 202)
      }
      state.polls++
      if (state.polls > 1) state.documents.forEach(item => {
        if (item.status === 'pending' || item.status === 'processing') item.status = 'ready'
      })
      return respond(state.documents)
    }
    if (path.endsWith('/conversations')) {
      if (method === 'POST') {
        const item: Conversation = { id: `conversation-${state.conversations.length + 1}`, assistant_id: assistantId,
          title: request.postDataJSON().title, use_rag: request.postDataJSON().use_rag,
          allow_general_knowledge: request.postDataJSON().allow_general_knowledge, created_at: new Date().toISOString() }
        state.conversations.unshift(item)
        state.messages[item.id] = []
        return respond(item, 201)
      }
      return respond(state.conversations)
    }
    if (method === 'PATCH' && path.includes('/conversations/')) {
      if (state.failMode) return respond({ detail: 'Could not save answer mode' }, 503)
      const item = state.conversations.find(item => item.id === path.split('/').at(-1))!
      Object.assign(item, request.postDataJSON())
      return respond(item)
    }
    if (path.endsWith('/messages')) {
      const id = path.split('/').at(-2)!
      if (method === 'POST') {
        state.sendCalls++
        if (state.failChat) return respond({ detail: 'Model service temporarily unavailable' }, 502)
        const content = request.postDataJSON().content
        const answer: Message = { id: `answer-${state.sendCalls}`, conversation_id: id, role: 'assistant',
          answer_basis: 'documents',
          content: '**Support hours** are Monday to Friday, 09:00–18:00. [S1]',
          sources: [{ source_id: 'S1', document_id: documentId, filename: document.filename, chunk_index: 0, page_start: 3, page_end: 3 }],
          created_at: new Date().toISOString() }
        if (!state.documents.length || !state.conversations.find(item => item.id === id)?.use_rag) {
          answer.content = '### General knowledge · no web search\n\nAn embedding represents meaning as numbers.'
          answer.answer_basis = 'general_knowledge'
          answer.sources = []
        } else if (state.mixedAnswer) {
          answer.content = '### From your documents\n\nSupport operates 09:00–18:00. [S1]\n\n### General knowledge · no web search\n\nA support window defines when a team responds.'
          answer.answer_basis = 'mixed'
        }
        state.messages[id].push({ ...answer, id: `question-${state.sendCalls}`, role: 'user', content, sources: [] }, answer)
        return respond({ message: answer, tokens_used: 30, model: 'test-model' })
      }
      if (state.failMessages) return respond({ detail: 'Could not load conversation' }, 503)
      return respond(state.messages[id] ?? [])
    }
    if (method === 'DELETE' && path.includes('/documents/')) {
      state.documents = []
      return route.fulfill({ status: 204 })
    }
    return respond({ detail: `Unmocked route: ${method} ${path}` }, 500)
  }
  await page.route('**/auth/**', handler)
  await page.route('**/assistants**', handler)
  return state
}

test('register, create assistant, upload, chat, download a source, reopen history and sign out', async ({ page }) => {
  const state = await mockApi(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await page.getByLabel('Full name').fill('Test Reader')
  await page.getByLabel('Email address').fill('reader@example.com')
  await page.getByLabel('Password', { exact: true }).fill('SamplePass123')
  await page.getByRole('button', { name: 'Create your account', exact: true }).click()
  await page.getByRole('button', { name: 'Create your first assistant' }).click()
  await page.getByLabel('Name', { exact: true }).fill('Research notes')
  await page.getByRole('button', { name: 'Create assistant', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Let’s explore.' })).toBeVisible()
  await page.getByLabel('Choose document').setInputFiles({ name: document.filename, mimeType: 'text/plain', buffer: Buffer.from('Support operates Monday to Friday, 09:00 to 18:00.') })
  await expect(page.getByText('Queued', { exact: true })).toBeVisible()
  await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 10_000 })
  await page.getByLabel('Your message').fill('When is support available?')
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.locator('.message-assistant')).toContainText('Monday to Friday')
  await expect(page.getByRole('button', { name: /S1.*team-handbook/ })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath('workspace-desktop.png'), fullPage: true })
  const downloaded = page.waitForEvent('download')
  await page.getByRole('button', { name: /S1.*team-handbook/ }).click()
  expect((await downloaded).suggestedFilename()).toBe(document.filename)
  await page.getByRole('button', { name: 'New conversation', exact: true }).click()
  await page.getByRole('navigation', { name: 'Conversations', exact: true }).getByRole('button', { name: 'When is support available?' }).click()
  await expect(page.locator('.message-assistant')).toContainText('Monday to Friday')
  await page.reload()
  await page.getByRole('navigation', { name: 'Conversations', exact: true }).getByRole('button', { name: 'When is support available?' }).click()
  await expect(page.locator('.message-assistant')).toContainText('Monday to Friday')
  expect(state.sendCalls).toBe(1)
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([])
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible()
})

test('login errors do not attempt a refresh loop', async ({ page }) => {
  const state = await mockApi(page)
  state.loginError = true
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath('sign-in.png'), fullPage: true })
  const before = state.refreshCalls
  await page.getByLabel('Email address').fill('reader@example.com')
  await page.getByLabel('Password', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: 'Sign in to Shion' }).click()
  await expect(page.getByRole('alert')).toContainText('Invalid email or password')
  expect(state.refreshCalls).toBe(before)
})

test('failed uploads, reprocessing, and confirmed removal are recoverable', async ({ page }) => {
  const state = await mockApi(page, true)
  state.documents[0].status = 'failed'
  state.documents[0].error_message = 'Model service temporarily unavailable'
  await page.goto('/')
  await expect(page.getByText('Needs attention', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: `Reprocess ${document.filename}` }).click()
  await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 10_000 })
  state.failUpload = true
  await page.getByLabel('Choose document').setInputFiles({ name: 'large.txt', mimeType: 'text/plain', buffer: Buffer.from('sample') })
  await expect(page.getByRole('alert')).toContainText('File exceeds 10MB')
  await expect(page.getByRole('button', { name: /Add a document/ })).toBeEnabled()
  await page.getByRole('button', { name: `Remove ${document.filename}` }).click()
  await expect(page.getByText('Remove this document from your assistant?')).toBeVisible()
  await page.getByRole('button', { name: 'Keep document' }).click()
  expect(state.documents).toHaveLength(1)
  await page.getByRole('button', { name: `Remove ${document.filename}` }).click()
  await page.getByRole('button', { name: 'Remove', exact: true }).click()
  await expect(page.getByText('Your library starts here.')).toBeVisible()
})

test('failed answers preserve the draft and do not fabricate a saved response', async ({ page }) => {
  const state = await mockApi(page, true)
  state.failChat = true
  await page.goto('/')
  await expect(page.getByText('Ready', { exact: true })).toBeVisible()
  await page.getByLabel('Your message').fill('When is support available?')
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.getByRole('alert')).toContainText('Model service temporarily unavailable')
  await expect(page.getByLabel('Your message')).toHaveValue('When is support available?')
  await expect(page.locator('.message-assistant')).toHaveCount(0)
  expect(state.sendCalls).toBe(1)
  state.failMessages = true
  await page.getByRole('button', { name: 'Reload conversation to check before resending' }).click()
  await expect(page.getByText('Could not load conversation', { exact: true })).toBeVisible()
  state.failMessages = false
  await page.getByRole('button', { name: 'Reload conversation', exact: true }).click()
  await expect(page.getByLabel('Your message')).toBeEnabled()
  state.failChat = false
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.locator('.message-assistant')).toContainText('Monday to Friday')
  expect(state.conversations).toHaveLength(1)
})

test('parallel unauthorized requests share a refresh and failed refresh returns to sign-in', async ({ page }) => {
  const state = await mockApi(page, true)
  // Initial assistant list succeeds; both workspace requests then receive 401.
  await page.route('**/assistants', async route => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(state.assistants) })
    state.expireProtected = true
  })
  await page.goto('/')
  await expect(page.getByText('Ready', { exact: true })).toBeVisible()
  expect(state.refreshCalls).toBe(1)
  state.expireProtected = true
  state.failRefresh = true
  await page.getByRole('button', { name: 'Refresh documents' }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible()
})

test('mobile navigation, document panel, and composer fit the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page, true)
  await page.goto('/')
  await page.getByRole('button', { name: /Documents/ }).click()
  await expect(page.getByRole('button', { name: /Add a document/ })).toBeVisible()
  await page.getByRole('button', { name: 'Chat', exact: true }).click()
  await expect(page.getByLabel('Your message')).toBeVisible()
  await page.screenshot({ path: test.info().outputPath('workspace-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: 'Open navigation' }).click()
  await expect(page.getByLabel('YOUR ASSISTANT')).toBeVisible()
  await page.getByRole('button', { name: 'Close navigation' }).last().click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('questions remain disabled until a document is ready, including Enter submission', async ({ page }) => {
  const state = await mockApi(page, true)
  state.documents = []
  await page.goto('/')
  await page.getByLabel('Answer using').selectOption('documents')
  await page.getByLabel('Your message').fill('Can you read my files?')
  await expect(page.getByRole('button', { name: 'Send message' })).toBeDisabled()
  await page.getByLabel('Your message').press('Enter')
  expect(state.sendCalls).toBe(0)
  expect(state.conversations).toHaveLength(0)
})

test('Markdown answers cannot load remote images or run raw HTML', async ({ page }) => {
  const state = await mockApi(page, true)
  const conversation: Conversation = { id: 'existing', assistant_id: assistantId, title: 'Saved conversation', use_rag: true, created_at: '' }
  state.conversations.push(conversation)
  state.messages.existing = [{ id: 'unsafe', conversation_id: 'existing', role: 'assistant',
    content: '![tracking](https://tracking.invalid/pixel)\n<script>window.alert("bad")</script>\n**Safe text**',
    sources: [], created_at: '' }]
  let externalRequests = 0
  await page.route('https://tracking.invalid/**', route => { externalRequests++; return route.abort() })
  await page.goto('/')
  await page.getByRole('button', { name: 'Saved conversation' }).click()
  await expect(page.locator('.message-content')).toContainText('Safe text')
  await expect(page.locator('.message-content img, .message-content script')).toHaveCount(0)
  expect(externalRequests).toBe(0)
})

test('combined mode answers without documents and keeps source labels after reload and mode changes', async ({ page }) => {
  const state = await mockApi(page, true)
  state.documents = []
  await page.goto('/')
  await expect(page.getByLabel('Answer using')).toHaveValue('hybrid')
  await page.getByLabel('Your message').fill('What is an embedding?')
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.locator('.answer-basis')).toHaveText('General knowledge · no web search')
  expect(state.conversations[0].allow_general_knowledge).toBe(true)
  await expect(page.locator('.source-card')).toHaveCount(0)
  await page.getByLabel('Answer using').selectOption('documents')
  await expect(page.getByLabel('Answer using')).toHaveValue('documents')
  expect(state.conversations[0].allow_general_knowledge).toBe(false)
  await expect(page.locator('.answer-basis')).toHaveText('General knowledge · no web search')
  await page.reload()
  await page.getByRole('button', { name: 'What is an embedding?', exact: true }).click()
  await expect(page.getByLabel('Answer using')).toHaveValue('documents')
  await expect(page.locator('.answer-basis')).toHaveText('General knowledge · no web search')
  await page.getByLabel('Your message').fill('Another question')
  await expect(page.getByRole('button', { name: 'Send message' })).toBeDisabled()
  state.failMode = true
  await page.getByLabel('Answer using').selectOption('hybrid')
  await expect(page.getByRole('alert')).toContainText('Could not save answer mode')
  await expect(page.getByLabel('Answer using')).toHaveValue('documents')
  state.failMode = false
  await page.getByLabel('Answer using').selectOption('general')
  await expect(page.getByRole('button', { name: 'Send message' })).toBeEnabled()
  expect(state.conversations[0].use_rag).toBe(false)
})

test('mixed answers show document citations and distinguish general explanations on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await mockApi(page, true)
  state.mixedAnswer = true
  await page.goto('/')
  await page.getByLabel('Your message').fill('Explain our support hours')
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.locator('.answer-basis')).toHaveText('Documents + general knowledge · no web search')
  await expect(page.getByRole('heading', { name: 'From your documents', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'General knowledge · no web search', exact: true })).toBeVisible()
  await expect(page.locator('.source-card')).toHaveCount(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: test.info().outputPath('combined-mobile.png'), fullPage: true })
})

test('legacy messages are not assigned a source label from the current conversation mode', async ({ page }) => {
  const state = await mockApi(page, true)
  state.conversations.push({ id: 'legacy', assistant_id: assistantId, title: 'Legacy chat', use_rag: true, created_at: '' })
  state.messages.legacy = [{ id: 'old', conversation_id: 'legacy', role: 'assistant', content: 'An old answer.', sources: [], created_at: '' }]
  await page.goto('/')
  await page.getByRole('button', { name: 'Legacy chat' }).click()
  await expect(page.getByLabel('Answer using')).toHaveValue('documents')
  await expect(page.locator('.answer-basis')).toHaveText('Source information not recorded')
})
