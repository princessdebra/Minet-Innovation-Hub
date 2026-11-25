import { useParams } from 'react-router-dom';
import { useApi } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { ErrorMsg, Loading } from '../components/Bits';

interface Lib {
  category: { slug: string; title: string; description: string };
  items: { id: number; title: string; kind: string; summary: string }[];
}

export function LibraryCategory() {
  const { slug } = useParams();
  const { data, error, loading } = useApi<Lib>(`/library/${slug}`);
  const back = { to: '/knowledge', label: 'Knowledge & impact' };
  if (error) return <><PageHeader title="Knowledge library" back={back} /><ErrorMsg text={error} /></>;
  if (loading || !data) return <><PageHeader title="Knowledge library" back={back} /><Loading /></>;
  return (
    <>
      <PageHeader title={data.category.title} subtitle={data.category.description} back={back} />
      <div className="stack">
        {data.items.map((i) => (
          <article key={i.id} className="card libitem">
            <span className="tagline tagline--plain">{i.kind.toUpperCase()}</span>
            <h3>{i.title}</h3>
            <p className="muted">{i.summary}</p>
          </article>
        ))}
      </div>
      <p className="small muted spaced">Illustrative content for the proof of concept.</p>
    </>
  );
}
