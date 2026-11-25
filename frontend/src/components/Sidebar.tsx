import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, BarChart3, Book, GraduationCap, Home, Lightbulb, Search, Sparkles,
  Wand2 } from 'lucide-react';
import logo from '../assets/minet-logo.png';

const NAV = [
  { to: '/', label: 'Home', icon: Home, active: (p: string) => p === '/' || p.startsWith('/leaderboard') },
  { to: '/explore', label: 'Explore challenges', icon: Search, active: (p: string) => p.startsWith('/explore') },
  { to: '/workspace', label: 'My ideas & experiments', icon: Lightbulb,
    active: (p: string) => p.startsWith('/workspace') || p.startsWith('/ideas') },
  { to: '/learn', label: 'Learn & connect', icon: Book,
    active: (p: string) => p === '/learn' || p.startsWith('/learn/paths') },
  { to: '/learn/courses', label: 'Innovation Academy', icon: GraduationCap,
    active: (p: string) => p.startsWith('/learn/courses') || p.startsWith('/learn/lessons')
      || p.startsWith('/learn/assessments') || p.startsWith('/learn/my-learning') },
  { to: '/knowledge', label: 'Knowledge & impact', icon: BarChart3, active: (p: string) => p.startsWith('/knowledge') },
];

// Kept separate so it can move into the admin portal later without touching NAV.
const ADMIN_NAV = [
  { to: '/admin/course-studio', label: 'AI Course Studio', icon: Wand2,
    active: (p: string) => p.startsWith('/admin') },
];

export function Sidebar({ open = false, onNavigate }: { open?: boolean; onNavigate?: () => void }) {
  const { pathname } = useLocation();
  return (
    <aside className={`sidebar ${open ? 'is-open' : ''}`}>
      <div>
        <Link to="/" aria-label="Minet Innovation Hub home" onClick={onNavigate}>
          <img className="sidebar__logo" src={logo} alt="Minet, Secure Tomorrow" />
        </Link>
        <div className="sidebar__label">Innovation Hub</div>
        <nav className="nav" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, active }) => (
            <Link key={to} to={to} className={`nav__item ${active(pathname) ? 'is-active' : ''}`}
                  aria-current={active(pathname) ? 'page' : undefined} onClick={onNavigate}>
              <Icon size={18} strokeWidth={1.6} /> {label}
            </Link>
          ))}
        </nav>
        <div className="nav__section">
          <span className="nav__heading">Administration</span>
          <nav className="nav" aria-label="Administration">
            {ADMIN_NAV.map(({ to, label, icon: Icon, active }) => (
              <Link key={to} to={to} className={`nav__item ${active(pathname) ? 'is-active' : ''}`}
                    aria-current={active(pathname) ? 'page' : undefined} onClick={onNavigate}>
                <Icon size={18} strokeWidth={1.6} /> {label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
      <div className="sidebar__cta">
        <div className="sidebar__cta-head">
          <Sparkles size={15} />
          <strong>Have an idea?</strong>
        </div>
        <span>Share it. Shape what's next.</span>
        <Link to="/ideas/new" className="btn btn--dark btn--block sidebar__cta-btn" onClick={onNavigate}>
          Submit an idea <ArrowRight size={14} />
        </Link>
      </div>
    </aside>
  );
}
