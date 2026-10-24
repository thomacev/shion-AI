import { useRef, useState, type DragEvent } from 'react'
import { Check, CircleAlert, Download, FileText, LoaderCircle, RefreshCw, Trash2, Upload } from 'lucide-react'
import { workspaceApi, type Document } from '../api/workspace'
import { errorMessage } from '../api/client'
import { Busy, Notice } from './ui'

interface Props {
  assistantId: string
  documents: Document[]
  loading: boolean
  error: string
  onChanged: () => void
}
const statusLabels = { pending: 'Queued', processing: 'Reading document', ready: 'Ready', failed: 'Needs attention' }

export function DocumentsPanel({ assistantId, documents, loading, error, onChanged }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [actionError, setActionError] = useState('')
  const [working, setWorking] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const ready = documents.filter(item => item.status === 'ready').length

  async function upload(file?: File) {
    if (!file || uploading) return
    setActionError('')
    if (!/\.(pdf|txt)$/i.test(file.name)) { setActionError('Choose a PDF or a UTF-8 text file.'); return }
    if (!file.size) { setActionError('This file is empty. Choose a document with some content.'); return }
    setUploading(true)
    setProgress(0)
    try { await workspaceApi.upload(assistantId, file, setProgress); onChanged() }
    catch (error) { setActionError(errorMessage(error)); onChanged() }
    finally { setUploading(false); if (input.current) input.current.value = '' }
  }

  function drop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    if (event.dataTransfer.files.length > 1) { setActionError('Please add one document at a time.'); return }
    void upload(event.dataTransfer.files[0])
  }

  async function action(item: Document, kind: 'retry' | 'delete' | 'download') {
    setWorking(item.id)
    setActionError('')
    try {
      if (kind === 'retry') await workspaceApi.retry(assistantId, item.id)
      if (kind === 'delete') { await workspaceApi.deleteDocument(assistantId, item.id); setConfirmDelete(null) }
      if (kind === 'download') await workspaceApi.download(assistantId, item.id, item.filename)
      if (kind !== 'download') onChanged()
    } catch (error) { setActionError(errorMessage(error)) }
    finally { setWorking(null) }
  }

  return <>
    <div className="library-heading"><div><span className="eyebrow">THE SOURCE MATERIAL</span><h2>Documents <span>{documents.length}</span></h2></div>
      <button className="icon-button" aria-label="Refresh documents" onClick={onChanged} disabled={loading || uploading}><RefreshCw size={16} /></button>
    </div>
    <p className="library-description">The knowledge behind your answers.</p>
    <div className={`upload-zone ${dragging ? 'dragging' : ''}`}
      onDragOver={event => { event.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)} onDrop={drop}>
      <input ref={input} className="sr-only" id="document-file" type="file" accept=".pdf,.txt" aria-label="Choose document" tabIndex={-1}
        disabled={uploading} onChange={event => { void upload(event.target.files?.[0]) }} />
      <button id="upload-document" onClick={() => input.current?.click()} disabled={uploading}>
        <span className="upload-icon">{uploading ? <LoaderCircle size={22} className="animate-spin" /> : <Upload size={22} />}</span>
        <strong>{uploading ? (progress === 100 ? 'Saving your document…' : `Uploading ${progress}%`) : 'Add a document'}</strong>
        <span>{uploading ? 'This will only take a moment.' : 'Choose a file or drop it here'}</span>
        <small>PDF or TXT · one file at a time</small>
      </button>
      {uploading && <progress max={100} value={progress} aria-label="Upload progress" />}
    </div>
    {actionError && <Notice>{actionError}</Notice>}
    {error && <><Notice>{error}</Notice><button className="text-button" onClick={onChanged}>Try loading documents again</button></>}
    <div className="document-list" aria-live="polite">
      {loading && <Busy label="Loading documents…" />}
      {!loading && !error && !documents.length && <div className="empty-documents"><FileText size={30} strokeWidth={1.3} /><p>Your library starts here.</p><span>Add a document to give your<br />assistant something to work with.</span></div>}
      {documents.map(item => <article className="document-card" key={item.id}>
        <div className="document-title"><span className="file-icon"><FileText size={19} /></span><div><h3 title={item.filename}>{item.filename}</h3><span className={`document-status status-${item.status}`}>
          {item.status === 'ready' ? <Check size={12} /> : item.status === 'failed' ? <CircleAlert size={12} /> : <LoaderCircle size={12} className="animate-spin" />}
          {statusLabels[item.status]}
        </span></div></div>
        {item.error_message && <p className="document-error">{item.error_message}</p>}
        {confirmDelete === item.id ? <div className="delete-confirm"><p>Remove this document from your assistant?</p><div><button className="text-button" disabled={!!working} onClick={() => { void action(item, 'delete') }}>Remove</button><button className="text-button" disabled={!!working} onClick={() => setConfirmDelete(null)}>Keep document</button></div></div> :
          <div className="document-actions">
            <button className="text-button" aria-label={`Download ${item.filename}`} disabled={!!working} onClick={() => { void action(item, 'download') }}><Download size={13} />Download</button>
            {(item.status === 'failed' || item.status === 'ready') && <button className="icon-button small" aria-label={`Reprocess ${item.filename}`} title="Reprocess document" disabled={!!working} onClick={() => { void action(item, 'retry') }}><RefreshCw size={13} /></button>}
            <button className="icon-button small" aria-label={`Remove ${item.filename}`} title="Remove document" disabled={!!working} onClick={() => setConfirmDelete(item.id)}><Trash2 size={13} /></button>
          </div>}
        {working === item.id && <Busy label="Working…" />}
      </article>)}
    </div>
    <div className="library-footer"><span className="status-dot" /><p>{ready ? `${ready} document${ready === 1 ? '' : 's'} ready for your questions.` : 'Ready documents will be used in your conversations.'}</p></div>
  </>
}
