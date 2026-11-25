import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { api } from '../api/client';
import type { SearchResult } from '../api/types';

export function SearchBox() {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => {
      api.get<{ results: SearchResult[] }>(`/search?q=${encodeURIComponent(q.trim())}`)
        .then((r) => setResults(r.results)).catch(() => setResults([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const shortcut = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); inputRef.current?.focus(); }
    };
    document.addEventListener('keydown', shortcut);
    return () => document.removeEventListener('keydown', shortcut);
  }, []);

  const go = (path: string) => { setOpen(false); setQ(''); navigate(path); };

  return (
    <div className="search" ref={wrap}>
      <Search size={16} strokeWidth={1.75} />
      <input ref={inputRef} value={q} placeholder="Search Innovation Hub..." aria-label="Search Innovation Hub"
             onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
             onKeyDown={(e) => { if (e.key === 'Enter' && results[0]) go(results[0].path); }} />
      {open && q.trim().length >= 2 && (
        <div className="search__panel">
          {results.length === 0 ? <p className="search__empty">No matches for "{q.trim()}".</p> :
            results.map((r, i) => (
              <button key={i} className="search__item" onClick={() => go(r.path)}>
                <span className="search__type">{r.type}</span>
                <span className="search__title">{r.title}</span>
                <span className="search__sub">{r.subtitle}</span>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
