import { useEffect, useState } from 'react'
import { BookOpen, ChevronRight, Files, LogOut, Menu, MessageSquare, Plus, X } from 'lucide-react'
import { workspaceApi, type Assistant, type Conversation, type Document } from '../api/workspace'
import { errorMessage } from '../api/client'
import { Brand, Busy, Notice } from './ui'
import { DocumentsPanel } from './DocumentsPanel'
import { ChatPanel } from './ChatPanel'

interface Props {
  assistant: Assistant
  assistants: Assistant[]
  onSelect: (id: string) => void
  onCreate: () => void
  onLogout: () => Promise<void>
}

export function Workspace({ assistant, assistants, onSelect, onCreate, onLogout }: Props) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(true)
  const [documentsError, setDocumentsError] = useState('')
  const [documentRevision, setDocumentRevision] = useState(0)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyRevision, setHistoryRevision] = useState(0)
  const [historyError, setHistoryError] = useState('')
  const [activeId, setActiveId] = useState<string | null>(null)
  const [chat, setChat] = useState<{ key: string; conversation?: Conversation }>({ key: 'new' })
  const [chatBusy, setChatBusy] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [accountError, setAccountError] = useState('')
  const [navOpen, setNavOpen] = useState(false)
  const [panel, setPanel] = useState<'chat' | 'documents'>('chat')

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function refresh() {
      try {
        const data = await workspaceApi.documents(assistant.id, controller.signal)
        if (controller.signal.aborted) return
        setDocuments(data)
        setDocumentsError('')
        if (data.some(item => item.status === 'pending' || item.status === 'processing')) {
          timer = setTimeout(() => { void refresh() }, 2500)
        }
      } catch (error) {
        if (!controller.signal.aborted) setDocumentsError(errorMessage(error))
      } finally {
        if (!controller.signal.aborted) setDocumentsLoading(false)
      }
    }
    void refresh()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [assistant.id, documentRevision])

  useEffect(() => {
    const controller = new AbortController()
    workspaceApi.conversations(assistant.id, controller.signal).then(data => {
      if (!controller.signal.aborted) { setConversations(data); setHistoryError('') }
    }).catch(error => {
      if (!controller.signal.aborted) setHistoryError(errorMessage(error))
    }).finally(() => {
      if (!controller.signal.aborted) setHistoryLoading(false)
    })
    return () => controller.abort()
  }, [assistant.id, historyRevision])

  function newChat() {
    setChat({ key: crypto.randomUUID() })
    setActiveId(null)
    setNavOpen(false)
    setPanel('chat')
  }

  async function signOut() {
    setLoggingOut(true)
    setAccountError('')
    try { await onLogout() }
    catch (error) { setAccountError(errorMessage(error)) }
    finally { setLoggingOut(false) }
  }

  const ready = documents.filter(item => item.status === 'ready').length
  return <div className={`workspace ${navOpen ? 'nav-open' : ''} show-${panel}`}>
    {navOpen && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
    <aside className="sidebar" aria-label="Workspace navigation">
      <div className="sidebar-brand"><Brand /><button className="icon-button mobile-only" aria-label="Close navigation" onClick={() => setNavOpen(false)}><X size={20} /></button></div>
      <div className="assistant-picker">
        <label className="eyebrow" htmlFor="assistant-select">YOUR ASSISTANT</label>
        <select id="assistant-select" value={assistant.id} disabled={chatBusy} onChange={event => onSelect(event.target.value)}>
          {assistants.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <button className="text-button" onClick={onCreate} disabled={chatBusy}><Plus size={14} />New assistant</button>
      </div>
      <button className="button primary new-chat" onClick={newChat} disabled={chatBusy}><Plus size={17} />New conversation</button>
      <div className="history-heading"><span className="eyebrow">CONVERSATIONS</span><span>{conversations.length}</span></div>
      <nav className="conversation-list" aria-label="Conversations">
        {historyLoading && <Busy label="Loading conversations…" />}
        {historyError && <><Notice>{historyError}</Notice><button className="text-button" onClick={() => setHistoryRevision(value => value + 1)}>Reload conversations</button></>}
        {!historyLoading && !historyError && conversations.length === 0 && <p className="empty-history">Your conversations will<br />find a home here.</p>}
        {conversations.map(item => <button key={item.id} className={`conversation-link ${activeId === item.id ? 'active' : ''}`}
          disabled={chatBusy} aria-current={activeId === item.id ? 'page' : undefined}
          onClick={() => { setChat({ key: item.id, conversation: item }); setActiveId(item.id); setNavOpen(false); setPanel('chat') }}>
          <MessageSquare size={16} /><span>{item.title || 'Untitled conversation'}</span>
        </button>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-note"><BookOpen size={19} /><p>A little knowledge.<br /><strong>A lot of possibility.</strong></p></div>
        {accountError && <Notice>{accountError}</Notice>}
        <button className="logout-button" disabled={chatBusy || loggingOut} onClick={() => { void signOut() }}><LogOut size={16} />{loggingOut ? 'Signing out…' : 'Sign out'}</button>
      </div>
    </aside>
    <header className="workspace-header">
      <div className="breadcrumb"><button className="icon-button mobile-only" aria-label="Open navigation" onClick={() => setNavOpen(true)}><Menu size={20} /></button><span className="breadcrumb-root">Workspace</span><ChevronRight size={14} /><strong>{assistant.name}</strong></div>
      <span className="workspace-tag"><span className="status-dot" />Document workspace</span>
      <div className="workspace-tabs" aria-label="Workspace panels"><button aria-pressed={panel === 'chat'} onClick={() => setPanel('chat')}><MessageSquare size={16} />Chat</button><button aria-pressed={panel === 'documents'} onClick={() => setPanel('documents')}><Files size={16} />Documents<span>{documents.length}</span></button></div>
    </header>
    <section className="chat-area" aria-label="Conversation">
      <ChatPanel key={chat.key} assistant={assistant} initialConversation={chat.conversation}
        readyDocuments={ready} documentsLoading={documentsLoading} onBusyChange={setChatBusy}
        onOpenDocuments={() => { setPanel('documents'); document.getElementById('upload-document')?.focus() }}
        onUpdated={item => setConversations(current => current.map(existing => existing.id === item.id ? item : existing))}
        onCreated={item => { setConversations(current => [item, ...current]); setActiveId(item.id) }} />
    </section>
    <aside className="library" aria-label="Document library">
      <DocumentsPanel assistantId={assistant.id} documents={documents} loading={documentsLoading} error={documentsError}
        onChanged={() => setDocumentRevision(value => value + 1)} />
    </aside>
  </div>
}
