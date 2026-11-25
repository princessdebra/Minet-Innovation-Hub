import { ReactNode, useEffect } from 'react';
import { X } from 'lucide-react';

export function Modal({ title, onClose, children, wide = false }:
  { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className={`modal card ${wide ? 'modal--wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}
           onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
