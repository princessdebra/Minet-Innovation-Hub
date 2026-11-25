import { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export function ProgressBar({ percent, dark = false }: { percent: number; dark?: boolean }) {
  return (
    <div className={`progress ${dark ? 'progress--dark' : ''}`} role="progressbar"
         aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: `${percent}%` }} />
    </div>
  );
}

export function CtaLink({ to, children, caps = true }: { to: string; children: ReactNode; caps?: boolean }) {
  return (
    <Link to={to} className={`cta ${caps ? 'cta--caps' : ''}`}>
      {children} <ArrowRight size={14} strokeWidth={2} />
    </Link>
  );
}

export function Loading({ text = 'Loading...' }: { text?: string }) {
  return <p className="muted state-msg">{text}</p>;
}

export function ErrorMsg({ text }: { text: string }) {
  return <p className="state-msg state-msg--error" role="alert">{text}</p>;
}

export function Tabs<T extends string>({ tabs, value, onChange }:
  { tabs: { id: T; label: string }[]; value: T; onChange: (id: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id}
                className={`tab ${value === t.id ? 'is-active' : ''}`} onClick={() => onChange(t.id)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Avatar({ initials }: { initials: string }) {
  return <span className="avatar">{initials}</span>;
}

const STATUS_COLOR: Record<string, string> = {
  'draft': 'slate', 'not started': 'slate', 'not_started': 'slate',
  'submitted': 'sky', 'in review': 'amber', 'testing': 'sky', 'in progress': 'sky', 'in_progress': 'sky',
  'needs clarification': 'orange', 'clarify': 'orange',
  'learning captured': 'emerald', 'completed': 'emerald', 'validated': 'emerald', 'open': 'emerald',
};

export function StatusPill({ status }: { status: string }) {
  const color = STATUS_COLOR[status.toLowerCase()] ?? 'slate';
  return <span className={`status-pill status-pill--${color}`}>{status}</span>;
}
