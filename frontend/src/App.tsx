import { useCallback, useEffect, useState } from 'react'
import axios from 'axios'
import { ArrowRight, Plus } from 'lucide-react'
import { logout } from './api/auth'
import { errorMessage, SESSION_EXPIRED } from './api/client'
import { workspaceApi, type Assistant } from './api/workspace'
import { AuthScreen } from './components/AuthScreen'
import { CreateAssistant } from './components/CreateAssistant'
import { Workspace } from './components/Workspace'
import { Brand, Busy, Notice } from './components/ui'

export default function App() {
  const [status, setStatus] = useState<'loading' | 'anonymous' | 'ready' | 'error'>('loading')
  const [assistants, setAssistants] = useState<Assistant[]>([])
  const [selected, setSelected] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await workspaceApi.assistants(signal)
      if (signal?.aborted) return
      setAssistants(data)
      setSelected(current => data.some(item => item.id === current) ? current : data[0]?.id ?? '')
      setStatus('ready')
      setError('')
    } catch (error) {
      if (signal?.aborted) return
      if (axios.isAxiosError(error) && [401, 403].includes(error.response?.status ?? 0)) setStatus('anonymous')
      else { setError(errorMessage(error)); setStatus('error') }
    }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    workspaceApi.assistants(controller.signal).then(data => {
      if (controller.signal.aborted) return
      setAssistants(data)
      setSelected(data[0]?.id ?? '')
      setStatus('ready')
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return
      if (axios.isAxiosError(error) && [401, 403].includes(error.response?.status ?? 0)) setStatus('anonymous')
      else { setError(errorMessage(error)); setStatus('error') }
    })
    const expired = () => { setStatus('anonymous'); setAssistants([]); setSelected(''); setCreating(false) }
    window.addEventListener(SESSION_EXPIRED, expired)
    return () => { controller.abort(); window.removeEventListener(SESSION_EXPIRED, expired) }
  }, [])
  async function signOut() {
    await logout()
    setAssistants([])
    setSelected('')
    setStatus('anonymous')
  }
  const assistant = assistants.find(item => item.id === selected)

  if (status === 'anonymous') return <AuthScreen onAuthenticated={() => load()} />
  if (status === 'loading' || status === 'error') return <main className="connection-screen"><Brand />
    {status === 'loading' ? <Busy label="Opening your workspace…" /> : <div className="connection-error"><Notice>{error}</Notice><button className="button primary" onClick={() => { setStatus('loading'); void load() }}>Reconnect<ArrowRight size={17} /></button></div>}
  </main>
  return <>
    {assistant ? <Workspace key={assistant.id} assistant={assistant} assistants={assistants}
      onSelect={setSelected} onCreate={() => setCreating(true)} onLogout={signOut} /> :
      <main className="onboarding"><header><Brand /><button className="button quiet" onClick={() => { void signOut().catch(error => setError(errorMessage(error))) }}>Sign out</button></header>
        <div className="onboarding-content"><span className="eyebrow">YOUR WORKSPACE, A FRESH PAGE</span><h1>Make space for<br />your next discovery.</h1><p>Start with an assistant. Add your documents.<br />Then let your questions lead the way.</p>
          <button className="button primary" onClick={() => setCreating(true)}><Plus size={18} />Create your first assistant</button>
          {error && <Notice>{error}</Notice>}
          <div className="onboarding-steps">{['Create an assistant', 'Add your documents', 'Start a conversation'].map((item, i) => <div key={item}><span>0{i + 1}</span>{item}</div>)}</div>
        </div>
      </main>}
    {creating && <CreateAssistant onClose={() => setCreating(false)} onCreated={item => { setAssistants(current => [...current, item]); setSelected(item.id); setCreating(false) }} />}
  </>
}
