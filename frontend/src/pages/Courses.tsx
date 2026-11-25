import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Search } from 'lucide-react';
import { useApi } from '../api/client';
import type { CatalogResponse, ProgressStatus } from '../api/lms';
import { PageHeader } from '../components/PageHeader';
import { CourseGrid } from '../components/lms/CourseCard';
import { ErrorMsg, Loading, Tabs } from '../components/Bits';

type Filter = 'all' | ProgressStatus;

const TABS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All courses' },
  { id: 'in_progress', label: 'In progress' },
  { id: 'completed', label: 'Completed' },
  { id: 'not_started', label: 'Not started' },
];

export function Courses() {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [filter, setFilter] = useState<Filter>('all');

  const params = new URLSearchParams();
  if (query.trim()) params.set('search', query.trim());
  if (category) params.set('category', category);
  if (filter !== 'all') params.set('status', filter);
  const { data, error, loading } = useApi<CatalogResponse>(`/lms/catalog?${params}`);

  return (
    <>
      <PageHeader title="Innovation Academy"
                  subtitle="Practical courses built around the challenges and initiatives you are working on."
                  back={{ to: '/learn', label: 'Learn & connect' }} />

      <section className="card finder">
        <form className="finder__search" onSubmit={(e) => { e.preventDefault(); setQuery(search); }}>
          <Search size={16} strokeWidth={1.75} />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
                 placeholder="Search courses by title or topic" aria-label="Search courses" />
          <button type="submit" className="btn btn--outline btn--compact">Search</button>
        </form>
        <div className="finder__row">
          <Tabs tabs={TABS} value={filter} onChange={setFilter} />
          {data && data.categories.length > 0 && (
            <label className="finder__select">
              <span className="small muted">Category</span>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="">All categories</option>
                {data.categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          )}
        </div>
      </section>

      {error && <ErrorMsg text={error} />}
      {loading && !data && <Loading text="Loading courses..." />}

      {data && (
        <>
          <div className="records__head">
            <h2 className="h2 h2--tight">
              {data.total} course{data.total === 1 ? '' : 's'}
              {query.trim() && <> matching &ldquo;{query.trim()}&rdquo;</>}
            </h2>
            <Link to="/learn/my-learning" className="cta">My learning <ArrowRight size={14} /></Link>
          </div>
          <CourseGrid
            courses={data.courses}
            empty={query.trim() || category || filter !== 'all'
              ? 'No courses match these filters yet.'
              : 'No courses have been published yet. Published courses will appear here.'} />
        </>
      )}
    </>
  );
}
