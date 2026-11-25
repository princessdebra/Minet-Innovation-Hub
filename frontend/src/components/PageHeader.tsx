import { Link } from 'react-router-dom';
import { ChevronLeft, Menu } from 'lucide-react';
import { useApp } from '../state/AppContext';
import { useMobileNav } from './Layout';
import { SearchBox } from './SearchBox';

export function PageHeader({ title, subtitle, back }: { title: string; subtitle?: string; back?: { to: string; label: string } }) {
  const { user } = useApp();
  const { toggle } = useMobileNav();
  return (
    <header className="topbar">
      <div className="topbar__row">
        <button type="button" className="navtoggle" aria-label="Toggle navigation" onClick={toggle}>
          <Menu size={20} />
        </button>
        <div className="topbar__title">
          {back && <Link to={back.to} className="backlink"><ChevronLeft size={14} /> {back.label}</Link>}
          <h1>{title}</h1>
          {subtitle && <p className="subtitle">{subtitle}</p>}
        </div>
      </div>
      <div className="topbar__tools">
        <SearchBox />
        <Link to="/help" className="toolbar-link">Help</Link>
        <span className="dot" aria-hidden="true" />
        <span className="toolbar-link">{user.name}</span>
      </div>
    </header>
  );
}
