import { useState, type FormEvent } from 'react'
import { ArrowRight, FileText, Quote } from 'lucide-react'
import { login, register } from '../api/auth'
import { errorMessage } from '../api/client'
import { Brand, Busy, Notice } from './ui'

export function AuthScreen({ onAuthenticated }: { onAuthenticated: () => Promise<void> }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const email = String(data.get('email')).trim()
    const password = String(data.get('password'))
    setBusy(true)
    setError('')
    setNote('')
    try {
      if (mode === 'register') {
        if (!/[a-z]/i.test(password) || !/\d/.test(password)) throw new Error('Use at least one letter and one number in your password.')
        await register(String(data.get('name')).trim(), email, password)
        setMode('login')
        setNote('Your account is ready. Sign in if you aren’t connected automatically.')
      }
      await login(email, password)
      await onAuthenticated()
    } catch (error) { setError(errorMessage(error)) }
    finally { setBusy(false) }
  }

  return <main className="auth-layout">
    <section className="auth-story">
      <Brand />
      <div className="auth-story-content">
        <span className="eyebrow">A LITTLE LESS SEARCHING</span>
        <h1>Your documents.<br />A clearer picture.</h1>
        <p>A quiet workspace to bring your files together,<br className="desktop-break" /> ask questions, and find answers with sources.</p>
        <div className="story-card" aria-hidden="true">
          <span className="story-file"><FileText size={18} /> A place for your knowledge</span>
          <Quote size={28} className="story-quote" />
          <p>Good questions deserve<br />answers you can trace.</p>
          <div className="story-rule" /><span className="story-source">FROM YOUR DOCUMENTS</span>
        </div>
      </div>
      <span className="auth-footer">Read less. Understand more.</span>
    </section>
    <section className="auth-form-area">
      <div className="auth-form-wrap">
        <div className="mode-tabs" aria-label="Account options">
          <button className={mode === 'login' ? 'selected' : ''} onClick={() => { setMode('login'); setError(''); setNote('') }} disabled={busy}>Sign in</button>
          <button className={mode === 'register' ? 'selected' : ''} onClick={() => { setMode('register'); setError(''); setNote('') }} disabled={busy}>Create account</button>
        </div>
        <h2>{mode === 'login' ? 'Welcome back.' : 'Make room for clarity.'}</h2>
        <p className="muted">{mode === 'login' ? 'Your documents and conversations are waiting.' : 'Create your account to start your first workspace.'}</p>
        <form className="form-stack" onSubmit={submit}>
          {mode === 'register' && <label>Full name<input name="name" autoComplete="name" placeholder="Your name" required maxLength={64} /></label>}
          <label>Email address<input name="email" type="email" autoComplete="email" placeholder="you@example.com" required /></label>
          <label>Password<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} placeholder="Enter your password" minLength={mode === 'register' ? 8 : undefined} required /></label>
          {mode === 'register' && <p className="field-hint">At least 8 characters, including a letter and a number.</p>}
          {note && <p className="field-hint" role="status">{note}</p>}
          {error && <Notice>{error}</Notice>}
          <button className="button primary auth-submit" disabled={busy}>
            {busy ? <Busy label="Connecting…" /> : <>{mode === 'login' ? 'Sign in to Shion' : 'Create your account'}<ArrowRight size={18} /></>}
          </button>
        </form>
        <p className="auth-bottom">Your next answer starts with a document.</p>
      </div>
    </section>
  </main>
}
