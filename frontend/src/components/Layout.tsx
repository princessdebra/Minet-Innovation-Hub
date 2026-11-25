import { createContext, useContext, useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';

const NavCtx = createContext<{ toggle: () => void } | null>(null);
export function useMobileNav() {
  const v = useContext(NavCtx);
  if (!v) throw new Error('useMobileNav must be used inside Layout');
  return v;
}

export function Layout() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  useEffect(() => { window.scrollTo(0, 0); setOpen(false); }, [pathname]);
  return (
    <NavCtx.Provider value={{ toggle: () => setOpen((v) => !v) }}>
      <div className="shell">
        <Sidebar open={open} onNavigate={() => setOpen(false)} />
        <div className={`mobile-backdrop ${open ? 'is-open' : ''}`} onClick={() => setOpen(false)} />
        <main className="main"><div className="container"><Outlet /></div></main>
      </div>
    </NavCtx.Provider>
  );
}
