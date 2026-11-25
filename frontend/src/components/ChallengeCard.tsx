import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import type { ChallengeCardData } from '../api/types';
import { StatusPill } from './Bits';

export function ChallengeCard({ c }: { c: ChallengeCardData }) {
  return (
    <article className="card challenge">
      <div className="challenge__top">
        <StatusPill status={c.status} />
        <span className="small muted">Source: {c.source}</span>
      </div>
      <h3 className="challenge__title"><Link to={`/explore/${c.id}`}>{c.title}</Link></h3>
      <p className="challenge__hmw">{c.how_might_we}</p>
      <dl className="challenge__facts">
        <div><dt>Horizon</dt><dd>{c.horizon}</dd></div>
        <div><dt>Innovation type</dt><dd>{c.types.join(' / ')}</dd></div>
        <div><dt>Sponsor</dt><dd>{c.sponsor}</dd></div>
      </dl>
      <div className="challenge__foot">
        <span className="small muted">{c.is_illustrative ? 'Illustrative challenge' : ''}</span>
        <Link to={`/explore/${c.id}`} className="cta">Explore &amp; respond <ArrowRight size={14} /></Link>
      </div>
    </article>
  );
}
