import { BookOpen, CircleAlert, LoaderCircle } from 'lucide-react'

export function Brand() {
  return <a className="brand" href="#" aria-label="Shion home">
    <span className="brand-mark"><BookOpen size={21} strokeWidth={1.8} /></span>
    <span>shion<span className="brand-dot">.</span></span>
  </a>
}

export function Busy({ label = 'Loading…' }: { label?: string }) {
  return <span className="busy" role="status"><LoaderCircle size={17} className="animate-spin" />{label}</span>
}

export function Notice({ children }: { children: React.ReactNode }) {
  return <div className="notice" role="alert"><CircleAlert size={18} /><span>{children}</span></div>
}
