import client from './client'

export interface Assistant {
  id: string
  name: string
  description: string | null
  system_prompt: string
}
export interface Conversation {
  id: string
  assistant_id: string
  title: string | null
  use_rag: boolean
  allow_general_knowledge?: boolean
  created_at: string
}
export interface Document {
  id: string
  assistant_id: string
  filename: string
  status: 'pending' | 'processing' | 'ready' | 'failed'
  error_message: string | null
  created_at: string
}
export interface Source {
  source_id: string
  document_id: string
  filename: string
  chunk_index: number
  page_start: number | null
  page_end: number | null
}
export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  sources: Source[]
  answer_basis?: 'documents' | 'general_knowledge' | 'mixed' | 'insufficient_evidence' | null
  created_at: string
}

export type ChatMode = 'documents' | 'hybrid' | 'general'
export const conversationMode = (conversation?: Conversation): ChatMode =>
  !conversation ? 'hybrid' : !conversation.use_rag ? 'general' : conversation.allow_general_knowledge ? 'hybrid' : 'documents'
const modeFlags = (mode: ChatMode) => ({ use_rag: mode !== 'general', allow_general_knowledge: mode === 'hybrid' })

const root = (id: string) => `/assistants/${encodeURIComponent(id)}`

// Load all pages so the backend's defaults don't silently hide older items.
async function allPages<T>(path: string, signal?: AbortSignal): Promise<T[]> {
  const result: T[] = []
  for (let offset = 0; ; offset += 100) {
    const { data } = await client.get<T[]>(path, { params: { limit: 100, offset }, signal })
    result.push(...data)
    if (data.length < 100) return result
  }
}

export const workspaceApi = {
  assistants: async (signal?: AbortSignal) => (await client.get<Assistant[]>('/assistants', { signal })).data,
  createAssistant: async (data: { name: string; description: string; system_prompt: string }) =>
    (await client.post<Assistant>('/assistants', data)).data,
  documents: (id: string, signal?: AbortSignal) => allPages<Document>(`${root(id)}/documents`, signal),
  conversations: (id: string, signal?: AbortSignal) => allPages<Conversation>(`${root(id)}/conversations`, signal),
  createConversation: async (id: string, title: string, mode: ChatMode) =>
    (await client.post<Conversation>(`${root(id)}/conversations`, { title, ...modeFlags(mode) })).data,
  updateConversationMode: async (id: string, conversation: string, mode: ChatMode) =>
    (await client.patch<Conversation>(`${root(id)}/conversations/${conversation}`, modeFlags(mode))).data,
  messages: (id: string, conversation: string, signal?: AbortSignal) =>
    allPages<Message>(`${root(id)}/conversations/${conversation}/messages`, signal),
  send: async (id: string, conversation: string, content: string) =>
    (await client.post<{ message: Message }>(`${root(id)}/conversations/${conversation}/messages`,
      { content }, { timeout: 180_000 })).data.message,
  upload: async (id: string, file: File, onProgress: (percent: number) => void) => {
    const form = new FormData()
    form.append('file', file)
    return (await client.post<Document>(`${root(id)}/documents`, form, {
      timeout: 120_000,
      onUploadProgress: event => onProgress(event.total ? Math.round(event.loaded / event.total * 100) : 0),
    })).data
  },
  retry: async (id: string, document: string) =>
    (await client.post<Document>(`${root(id)}/documents/${document}/retry`)).data,
  deleteDocument: async (id: string, document: string) => { await client.delete(`${root(id)}/documents/${document}`) },
  download: async (id: string, document: string, filename: string) => {
    const { data } = await client.get<Blob>(`${root(id)}/documents/${document}/file`, { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const link = window.document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
  },
}
