import { createContext, ReactNode, useContext } from 'react';
import { useApi } from '../api/client';
import type { Reference, User } from '../api/types';

interface AppState {
  user: User;
  reference: Reference;
  /** RBAC seam: the POC grants every permission. Replace with real checks later. */
  can: (permission: string) => boolean;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const me = useApi<User>('/me');
  const ref = useApi<Reference>('/reference');

  if (me.error || ref.error) {
    return (
      <div className="boot">
        <h1>Innovation Hub</h1>
        <p>{me.error || ref.error}</p>
        <p className="boot__hint">
          Start the backend from the <code>backend</code> folder:
          <br /><code>uvicorn app.main:app --port 8000</code>
        </p>
      </div>
    );
  }
  if (!me.data || !ref.data) return <div className="boot"><p>Loading...</p></div>;

  const perms = me.data.permissions ?? [];
  const can = (p: string) => perms.includes('*') || perms.includes(p);
  return <Ctx.Provider value={{ user: me.data, reference: ref.data, can }}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp must be used inside AppProvider');
  return v;
}
