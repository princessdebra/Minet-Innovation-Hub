import { useApp } from '../state/AppContext';

export function StageGate({ active }: { active?: string }) {
  const { reference } = useApp();
  return (
    <section className="stagegate">
      <div className="stagegate__head">
        <div>
          <h2>Strategy execution model</h2>
          <p>Gated decision-making for ideas and experiments. Not every idea automatically becomes an experiment or pilot.</p>
        </div>
        <span className="small">Stage-gate decisions</span>
      </div>
      <div className="stagegate__grid">
        {reference.stages.map((s, i) => (
          <div key={s.id} className={`stagegate__item ${active === s.name ? 'is-active' : ''}`}>
            <div className="stagegate__title"><span className="stagegate__num">{i + 1}</span>{s.name.toUpperCase()}</div>
            <p>{s.description}</p>
          </div>
        ))}
      </div>
      <p className="small stagegate__note">
        Portfolio-level oversight reviews strategic alignment, customer value, feasibility, risk and compliance before funding or scaling.
      </p>
    </section>
  );
}
