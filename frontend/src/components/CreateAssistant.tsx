import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowRight, X } from 'lucide-react'
import { workspaceApi, type Assistant } from '../api/workspace'
import { errorMessage } from '../api/client'
import { Busy, Notice } from './ui'

export function CreateAssistant({ onClose, onCreated }: { onClose: () => void; onCreated: (assistant: Assistant) => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { dialog.current?.showModal() }, [])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true)
    setError('')
    try {
      const assistant = await workspaceApi.createAssistant({
        name: String(data.get('name')).trim(), description: String(data.get('description')).trim(),
        system_prompt: String(data.get('instructions')).trim(),
      })
      onCreated(assistant)
    } catch (error) { setError(errorMessage(error)) }
    finally { setBusy(false) }
  }
  return <dialog ref={dialog} className="modal" aria-labelledby="assistant-title" onCancel={event => { if (busy) event.preventDefault(); else onClose() }}>
    <div className="flex items-center justify-between gap-4"><span className="eyebrow">A NEW SPACE</span><button className="icon-button" aria-label="Close assistant form" onClick={onClose} disabled={busy}><X size={20} /></button></div>
    <h2 id="assistant-title">Create an assistant</h2>
    <p className="muted">Give a project its own documents and conversations.</p>
    <form onSubmit={submit} className="form-stack">
      <label>Name<input name="name" placeholder="e.g. Research notes" required maxLength={128} autoFocus /></label>
      <label>Description <span className="optional">Optional</span><input name="description" placeholder="What will this space be for?" maxLength={512} /></label>
      <label>Instructions<textarea name="instructions" rows={3} required defaultValue="Explain answers clearly and concisely. Follow the selected answer mode and distinguish document evidence from general explanations." /></label>
      {error && <Notice>{error}</Notice>}
      <button className="button primary" disabled={busy}>{busy ? <Busy label="Creating…" /> : <>Create assistant<ArrowRight size={17} /></>}</button>
    </form>
  </dialog>
}
