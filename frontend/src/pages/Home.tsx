import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronRight } from 'lucide-react';
import homePhoto from '../assets/home-hero.jpg';
import { useApi } from '../api/client';
import type { HomeData, LeaderboardData } from '../api/types';
import { useApp } from '../state/AppContext';
import { PageHeader } from '../components/PageHeader';
import { PortfolioHorizons } from '../components/PortfolioHorizons';
import { LeaderTable } from '../components/LeaderTable';
import { CtaLink, ErrorMsg, Loading, ProgressBar, StatusPill, Tabs } from '../components/Bits';

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

export function Home() {
  const { user } = useApp();
  const home = useApi<HomeData>('/home');
  const [tab, setTab] = useState<'learning' | 'ideas'>('learning');
  const lb = useApi<LeaderboardData>(`/leaderboard?tab=${tab}&limit=3`);
  const first = user.name.split(' ')[0];

  return (
    <>
      <PageHeader title="Innovation Hub" />

      <section className="hero">
        <div className="hero__copy">
          <span className="hero__eyebrow">Innovation starts with all of us</span>
          <h2>{greeting()}, {first}. What would you like to improve today?</h2>
          <p>Improve what we do today. Explore new opportunities. Create what comes next. Discover business challenges, develop your capabilities and turn promising ideas into measurable value.</p>
          <div className="hero__actions">
            <Link to="/ideas/new" className="btn btn--primary">Submit an idea <ArrowRight size={14} /></Link>
            <Link to="/explore" className="btn btn--ghost">Browse challenges</Link>
          </div>
        </div>
        <img className="hero__photo" src={homePhoto} alt="Colleagues mapping out ideas on a whiteboard" />
      </section>

      <PortfolioHorizons />

      <div className="overview">
        <section className="card leaders">
          <div className="leaders__head">
            <h2>Learning and Idea Leaderboard</h2>
          </div>
          <Tabs tabs={[{ id: 'learning', label: 'Learning' }, { id: 'ideas', label: 'Ideas submitted' }]}
                value={tab} onChange={setTab} />
          {lb.error && <ErrorMsg text={lb.error} />}
          {lb.data && (
            <>
              <LeaderTable data={lb.data} />
              <div className="leaders__me">
                <span className="leaders__me-init">{lb.data.me.initials}</span>
                <span>Your contribution • <strong>{lb.data.me.name}</strong></span>
                <strong className="leaders__me-sum">{lb.data.me.summary}</strong>
              </div>
              <div className="leaders__foot">
                <CtaLink to="/leaderboard" caps={false}>View full leaderboard</CtaLink>
                <span className="small muted">Learning and ideas are ranked separately.</span>
              </div>
              <p className="small muted leaders__note">{lb.data.note}</p>
            </>
          )}
        </section>

        <section className="card dash">
          <div className="dash__head">
            <h2>Your personal innovation dashboard</h2>
          </div>
          {home.error && <ErrorMsg text={home.error} />}
          {home.loading && !home.data && <Loading />}
          {home.data && (
          <div className="dash__grid">
            <Link to="/workspace" className="stat">
              <span className="stat__label">My ideas</span>
              <span className="stat__num">{home.data.tiles.ideas.count}</span>
              <ul className="stat__list">
                {home.data.tiles.ideas.items.map((i, k) => (
                  <li key={k} className="stat__row"><span>{i.title}</span><StatusPill status={i.status} /></li>
                ))}
              </ul>
            </Link>
            <Link to="/workspace" className="stat">
              <span className="stat__label">My active experiments</span>
              <span className="stat__num">{home.data.tiles.experiments.count}</span>
              <ul className="stat__list">
                {home.data.tiles.experiments.items.map((e, k) => (
                  <li key={k} className="stat__row"><span>{e.title}</span><span className="muted">{e.status}</span></li>
                ))}
                {home.data.tiles.experiments.next_review && <li>Next review: <strong>{home.data.tiles.experiments.next_review}</strong></li>}
              </ul>
            </Link>
            <Link to="/learn" className="stat">
              <span className="stat__label">My learning progress</span>
              <span className="stat__num">{home.data.tiles.learning.percent}%</span>
              <ul className="stat__list">
                <li>{home.data.tiles.learning.title}</li>
                <li className="muted">{home.data.tiles.learning.in_progress_text}</li>
              </ul>
              <div className="stat__bar"><ProgressBar percent={home.data.tiles.learning.percent} /></div>
            </Link>
            <div className="stat">
              <span className="stat__label">My next actions</span>
              <span className="stat__num">{home.data.tiles.next_actions.count}</span>
              <ul className="stat__list">
                {home.data.tiles.next_actions.items.map((a, k) => <li key={k}>{a}</li>)}
              </ul>
            </div>
          </div>
          )}
        </section>
      </div>

      <div className="contrib">
        <div>
          <h2 className="h2 h2--tight">Where you can contribute</h2>
          <div className="card linklist">
            <Link to="/explore" className="linklist__item">
              <div><strong>Explore a challenge</strong>
                <span>Help solve a real customer, process or growth problem • {home.data?.challenge_count ?? 0} illustrative challenges</span></div>
              <ChevronRight size={16} />
            </Link>
            <Link to="/ideas/new" className="linklist__item">
              <div><strong>Share an idea</strong>
                <span>Suggest an improvement or a new opportunity • Develop your opportunity</span></div>
              <ChevronRight size={16} />
            </Link>
            <Link to="/learn" className="linklist__item">
              <div><strong>Learn and connect</strong>
                <span>Build practical skills and find people to collaborate with • Innovation Academy</span></div>
              <ChevronRight size={16} />
            </Link>
          </div>
        </div>

        {home.data?.featured_challenge && (
          <div>
            <h2 className="h2 h2--tight">Featured opportunity</h2>
            <div className="card card--accent featured">
              <span className="tagline">
                {home.data.featured_challenge.horizon} • {home.data.featured_challenge.types.join(' / ')} • Illustrative challenge
              </span>
              <h3>{home.data.featured_challenge.title}</h3>
              <p className="muted">{home.data.featured_challenge.how_might_we}</p>
              <CtaLink to={`/explore/${home.data.featured_challenge.id}`} caps={false}>Explore this challenge</CtaLink>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
