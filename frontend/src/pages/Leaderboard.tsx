import { useState } from 'react';
import { useApi } from '../api/client';
import type { LeaderboardData } from '../api/types';
import { PageHeader } from '../components/PageHeader';
import { LeaderTable } from '../components/LeaderTable';
import { ErrorMsg, Loading, Tabs } from '../components/Bits';

export function Leaderboard() {
  const [tab, setTab] = useState<'learning' | 'ideas'>('learning');
  const { data, error, loading } = useApi<LeaderboardData>(`/leaderboard?tab=${tab}`);
  return (
    <>
      <PageHeader title="Learning & idea leaders" back={{ to: '/', label: 'Home' }}
                  subtitle="This quarter • Sample rankings. Learning and ideas are ranked separately." />
      <section className="card leaders leaders--full">
        <Tabs tabs={[{ id: 'learning', label: 'Learning' }, { id: 'ideas', label: 'Ideas submitted' }]} value={tab} onChange={setTab} />
        {error && <ErrorMsg text={error} />}
        {loading && !data && <Loading />}
        {data && (
          <>
            <LeaderTable data={data} markMe />
            <p className="small muted leaders__note">{data.note}</p>
          </>
        )}
      </section>
    </>
  );
}
