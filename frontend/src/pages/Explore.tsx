import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronDown, Search } from 'lucide-react';
import { useApi } from '../api/client';
import type { ChallengeCardData } from '../api/types';
import { useApp } from '../state/AppContext';
import { PageHeader } from '../components/PageHeader';
import { ChallengeCard } from '../components/ChallengeCard';
import { ErrorMsg, Loading } from '../components/Bits';

const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
const summary = (list: string[], emptyLabel = 'Any') =>
  (list.length === 0 ? emptyLabel : list.length === 1 ? list[0] : `${list.length} selected`);

function FilterDropdown({ label, options, selected, onChange, emptyLabel }:
  { label: string; options: string[]; selected: string[]; onChange: (v: string[]) => void; emptyLabel?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);
  return (
    <div className="finder__dd" ref={ref}>
      <button type="button" className={`finder__box ${open ? 'is-open' : ''}`} aria-expanded={open} aria-haspopup="listbox"
              onClick={() => setOpen((o) => !o)}>
        <span>{label}</span>{summary(selected, emptyLabel)}
        <ChevronDown size={14} className="finder__chevron" />
      </button>
      {open && (
        <div className="finder__panel" role="listbox" aria-label={label}>
          {options.map((o) => (
            <label key={o} className="check finder__option">
              <input type="checkbox" checked={selected.includes(o)} onChange={() => onChange(toggle(selected, o))} />
              <span className="check__box" aria-hidden="true" />
              <span>{o}</span>
            </label>
          ))}
          {selected.length > 0 && <button type="button" className="linkbtn finder__panel-clear" onClick={() => onChange([])}>Clear</button>}
        </div>
      )}
    </div>
  );
}

export function Explore() {
  const { reference } = useApp();
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [sources, setSources] = useState<string[]>([]);
  const [horizons, setHorizons] = useState<string[]>([]);
  const [types, setTypes] = useState<string[]>([]);

  useEffect(() => { const t = setTimeout(() => setDebounced(search), 250); return () => clearTimeout(t); }, [search]);

  const qs = new URLSearchParams();
  if (debounced.trim()) qs.set('search', debounced.trim());
  sources.forEach((s) => qs.append('source', s));
  horizons.forEach((h) => qs.append('horizon', h));
  types.forEach((t) => qs.append('type', t));
  const result = useApi<{ items: ChallengeCardData[]; total: number }>(`/challenges?${qs.toString()}`);
  const active = sources.length + horizons.length + types.length + (search.trim() ? 1 : 0);
  const clear = () => { setSearch(''); setSources([]); setHorizons([]); setTypes([]); };

  return (
    <>
      <PageHeader title="Explore challenges"
                  subtitle="Start with a business problem. Find context, join a team and propose a testable response." />

      <h2 className="h2">Challenge-led discovery</h2>
      <p className="muted lead">
        Browse by business problem, horizon and innovation type. Each challenge shows one primary strategic horizon
        and the types of innovation most relevant to the opportunity.
      </p>

      <section className="card finder">
        <div className="finder__head">
          <h3>Find a challenge</h3>
          <span className="small muted">Illustrative challenges, sponsors and statuses</span>
        </div>
        <div className="finder__bar">
          <label className="finder__search">
            <Search size={16} />
            <input value={search} onChange={(e) => setSearch(e.target.value)}
                   placeholder="Search by customer journey, business priority, process or capability" aria-label="Search challenges" />
          </label>
          <FilterDropdown label="Source" options={reference.sources} selected={sources} onChange={setSources} />
          <FilterDropdown label="Horizon" options={reference.horizons.map((h) => h.name)} selected={horizons} onChange={setHorizons} />
          <FilterDropdown label="Innovation type" options={reference.innovation_types.map((t) => t.name)} selected={types}
                          onChange={setTypes} emptyLabel="10 Doblin types" />
        </div>
        <div className="finder__foot small">
          <span className="muted" aria-live="polite">{result.data ? `${result.data.total} of 5 challenges shown` : ''}</span>
          {active > 0 && <button className="linkbtn" onClick={clear}>Clear filters</button>}
        </div>
      </section>

      {result.error && <ErrorMsg text={result.error} />}
      {result.loading && !result.data && <Loading />}
      {result.data && result.data.items.length === 0 && (
        <div className="card empty"><strong>No challenges match these filters.</strong>
          <p className="muted">Try removing a filter, or submit an idea if you do not see the right challenge.</p></div>
      )}
      {result.data && result.data.items.length > 0 && (
        <div className="grid-2 challenges">
          {result.data.items.map((c) => <ChallengeCard key={c.id} c={c} />)}
        </div>
      )}

      <section className="card support">
        <div>
          <span className="support__eyebrow">Open submission</span>
          <h3>Not seeing the right challenge?</h3>
          <p>You can still submit an idea. The Innovation team will help route it to the right owner and align it with the most relevant business sponsor.</p>
        </div>
        <Link to="/ideas/new" className="btn btn--primary">Submit an idea <ArrowRight size={14} /></Link>
      </section>
    </>
  );
}
