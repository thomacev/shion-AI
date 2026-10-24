import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowDownToLine, ArrowRight, ArrowUp, BookOpen, FileText, MessageSquare, Plus, Sparkles } from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { workspaceApi, conversationMode, type ChatMode, type Assistant, type Conversation, type Message, type Source } from '../api/workspace'
import { errorMessage } from '../api/client'
import { Busy, Notice } from './ui'

interface Props {
  assistant: Assistant
  initialConversation?: Conversation
  readyDocuments: number
  documentsLoading: boolean
  onCreated: (conversation: Conversation) => void
  onUpdated: (conversation: Conversation) => void
  onBusyChange: (busy: boolean) => void
  onOpenDocuments: () => void
}

export function ChatPanel({ assistant, initialConversation, readyDocuments, documentsLoading, onCreated, onUpdated, onBusyChange, onOpenDocuments }: Props) {
  const [conversation, setConversation] = useState(initialConversation)
  const [mode, setMode] = useState<ChatMode>(() => conversationMode(initialConversation))
  const [changingMode, setChangingMode] = useState(false)
  const [modeError, setModeError] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(!!initialConversation)
  const [loadError, setLoadError] = useState('')
  const [error, setError] = useState('')
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [pendingQuestion, setPendingQuestion] = useState('')
  const [downloadError, setDownloadError] = useState('')
  const end = useRef<HTMLDivElement>(null)
  const composer = useRef<HTMLTextAreaElement>(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  useEffect(() => {
    if (!initialConversation) return
    const controller = new AbortController()
    workspaceApi.messages(assistant.id, initialConversation.id, controller.signal).then(data => {
      if (!controller.signal.aborted) { setMessages(data); setLoadError('') }
    }).catch(error => {
      if (!controller.signal.aborted) setLoadError(errorMessage(error))
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [assistant.id, initialConversation])

  useEffect(() => { end.current?.scrollIntoView({ block: 'end', behavior: 'instant' }) }, [messages, sending])

  async function send(event: FormEvent) {
    event.preventDefault()
    const content = draft.trim()
    if (!content || sending || loading || loadError || noEvidence || waitingForDocuments || changingMode) return
    setSending(true)
    onBusyChange(true)
    setPendingQuestion(content)
    setError('')
    try {
      let current = conversation
      if (!current) {
        current = await workspaceApi.createConversation(assistant.id, content.slice(0, 80), mode)
        if (!mounted.current) return
        setConversation(current)
        onCreated(current)
      }
      const response = await workspaceApi.send(assistant.id, current.id, content)
      if (!mounted.current) return
      const question: Message = { id: crypto.randomUUID(), conversation_id: current.id, role: 'user',
        content, sources: [], created_at: new Date().toISOString() }
      setMessages(previous => [...previous, question, response])
      setDraft('')
    } catch (error) {
      if (mounted.current) setError(errorMessage(error))
    } finally {
      if (mounted.current) {
        setSending(false)
        setPendingQuestion('')
        onBusyChange(false)
        window.setTimeout(() => composer.current?.focus(), 0)
      }
    }
  }

  async function changeMode(next: ChatMode) {
    setModeError('')
    if (!conversation) { setMode(next); return }
    setChangingMode(true)
    onBusyChange(true)
    try {
      const updated = await workspaceApi.updateConversationMode(assistant.id, conversation.id, next)
      if (!mounted.current) return
      setConversation(updated)
      setMode(conversationMode(updated))
      onUpdated(updated)
    } catch (error) { if (mounted.current) setModeError(errorMessage(error)) }
    finally { if (mounted.current) { setChangingMode(false); onBusyChange(false) } }
  }

  async function reload() {
    if (!conversation) return
    setLoading(true)
    try { setMessages(await workspaceApi.messages(assistant.id, conversation.id)); setError(''); setLoadError('') }
    catch (error) { setLoadError(errorMessage(error)) }
    finally { setLoading(false) }
  }

  async function sourceDownload(source: Source) {
    setDownloadError('')
    try { await workspaceApi.download(assistant.id, source.document_id, source.filename) }
    catch (error) { setDownloadError(errorMessage(error)) }
  }

  const hasMessages = messages.length > 0 || sending
  const waitingForDocuments = documentsLoading && mode === 'documents'
  const noEvidence = !documentsLoading && readyDocuments === 0 && mode === 'documents'
  const modeLabels = { documents: 'Documents only', hybrid: 'Documents + general knowledge', general: 'General knowledge' }
  const basisLabels = { documents: 'From your documents', general_knowledge: 'General knowledge · no web search',
    mixed: 'Documents + general knowledge · no web search', insufficient_evidence: 'No supporting document evidence' }

  return <>
    <div className="chat-heading"><div><span className="eyebrow">{conversation ? 'CONVERSATION' : 'A FRESH PERSPECTIVE'}</span><h1>{conversation?.title || 'Let’s explore.'}</h1></div>
      <span className="mode-label"><BookOpen size={14} />{mode === 'documents' ? 'Document chat' : mode === 'general' ? 'General chat' : 'Combined chat'}</span>
    </div>
    <div className="chat-scroll">
      {loading ? <div className="chat-loading"><Busy label="Opening conversation…" /></div> : loadError ?
        <div className="chat-loading"><Notice>{loadError}</Notice><button className="button secondary" onClick={() => { void reload() }}>Reload conversation</button></div> :
        !hasMessages ? <div className="chat-welcome">
          <div className="welcome-symbol"><BookOpen size={38} strokeWidth={1.3} /><Sparkles size={19} /></div>
          <span className="eyebrow">A CONVERSATION WITH YOUR KNOWLEDGE</span>
          <h2>Your documents,<br /><em>in conversation.</em></h2>
          <p>{mode !== 'documents' ? 'Ask a question with or without documents. Answers distinguish your sources from general knowledge. No web search is used.' : readyDocuments ? 'Ask a question. Your assistant will answer from your documents and show you the sources.' : 'Add your first document and wait for it to be ready, then ask a question.'}</p>
          {readyDocuments || mode !== 'documents' ? <div className="suggestions">{(readyDocuments && mode !== 'general' ? ['Summarize the key ideas', 'What are the important details?', 'Help me understand this document'] : ['Explain what an embedding is', 'How does document search work?', 'Help me learn something new']).map(prompt =>
            <button key={prompt} onClick={() => { setDraft(prompt); composer.current?.focus() }}><MessageSquare size={15} /><span>{prompt}</span><ArrowRight size={15} /></button>)}</div> :
            <button className="button secondary" onClick={onOpenDocuments}><Plus size={17} />Add your first document</button>}
        </div> :
        <div className="messages" role="log" aria-label="Messages" aria-live="polite">
          {messages.filter(message => message.role !== 'system').map(message => <article className={`message message-${message.role}`} key={message.id}>
            <div className="message-label">{message.role === 'user' ? 'YOU' : <><span className="mini-mark"><BookOpen size={13} /></span>SHION</>}</div>
            {message.role === 'assistant' && <p className="answer-basis">{message.answer_basis ? basisLabels[message.answer_basis] : 'Source information not recorded'}</p>}
            <div className="message-content"><Markdown remarkPlugins={[remarkGfm]} skipHtml components={{
              img: () => null,
              a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
            }}>{message.content}</Markdown></div>
            {message.sources?.length > 0 && <div className="sources"><span className="eyebrow">SOURCES</span>{message.sources.map(source =>
              <button className="source-card" key={source.source_id} title="Download source document"
                onClick={() => { void sourceDownload(source) }}>
                <span className="source-number">{source.source_id}</span><FileText size={15} /><span>{source.filename}{source.page_start != null && <small>Page {source.page_start}{source.page_end != null && source.page_end !== source.page_start ? `–${source.page_end}` : ''}</small>}</span><ArrowDownToLine size={14} />
              </button>)}</div>}
          </article>)}
          {sending && <><article className="message message-user"><div className="message-label">YOU</div><p className="pending-question">{pendingQuestion}</p></article><article className="message message-assistant"><div className="message-label"><span className="mini-mark"><BookOpen size={13} /></span>SHION</div><Busy label="Reading, connecting, finding your answer…" /></article></>}
        </div>}
      <div ref={end} />
    </div>
    <div className="composer-area">
      <div className="chat-mode-picker"><label htmlFor="chat-mode">Answer using</label>
        <select id="chat-mode" value={mode} disabled={sending || changingMode || loading}
          onChange={event => { void changeMode(event.target.value as ChatMode) }}>
          {Object.entries(modeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        {changingMode && <Busy label="Saving mode…" />}
      </div>
      {modeError && <Notice>{modeError}</Notice>}
      {downloadError && <Notice>{downloadError}</Notice>}
      {error && <Notice>{error}{conversation && <><br /><button className="text-button" disabled={loading} onClick={() => { void reload() }}>Reload conversation to check before resending</button></>}</Notice>}
      {noEvidence && <p className="composer-notice"><FileText size={14} />{documentsLoading ? 'Loading documents…' : 'Add a document and wait for “Ready” to ask document questions.'}</p>}
      <form className="composer" onSubmit={send}>
        <label htmlFor="message-input" className="sr-only">Your message</label>
        <textarea ref={composer} id="message-input" placeholder="What would you like to know?" value={draft} rows={2} maxLength={8000}
          disabled={sending || loading || !!loadError || changingMode}
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} />
        <div className="composer-bottom"><span><BookOpen size={13} />{mode === 'general' ? 'No documents used' : `${readyDocuments} document${readyDocuments === 1 ? '' : 's'}${mode === 'hybrid' ? ' + general knowledge' : ''}`}</span>
          <button type="submit" className="send-button" aria-label="Send message" disabled={!draft.trim() || sending || loading || !!loadError || noEvidence || waitingForDocuments || changingMode}><ArrowUp size={20} /></button></div>
      </form>
      <p className="composer-footnote">Answers are a starting point. Check the sources for the full picture.</p>
    </div>
  </>
}
