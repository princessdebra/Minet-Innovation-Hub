import { useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { useApp } from '../state/AppContext';
import { HORIZON_DETAILS } from '../data/horizonDetails';
import { Modal } from './Modal';

export function PortfolioHorizons() {
  const { reference } = useApp();
  const [active, setActive] = useState<number | null>(null);
  const timer = useRef<number>();
  const hoverOpen = (i: number) => { window.clearTimeout(timer.current); timer.current = window.setTimeout(() => setActive(i), 150); };
  const hoverCancel = () => window.clearTimeout(timer.current);
  const detail = active !== null ? HORIZON_DETAILS[active] : undefined;
  return (
    <section className="card portfolio">
      <div className="portfolio__head">
        <h2>Our strategic Innovation Portfolio</h2>
      </div>
      <div className="portfolio__grid">
        {reference.horizons.map((h, i) => (
          <button key={h.id} type="button" className="portfolio__item" onClick={() => setActive(i)}
                  onMouseEnter={() => hoverOpen(i)} onMouseLeave={hoverCancel}
                  title="Hover or click to learn more" aria-haspopup="dialog">
            <strong>{h.name}<ChevronRight size={14} /></strong>
            <span>{h.description.replace(/'s business/, "'s business")}</span>
          </button>
        ))}
      </div>
      <p className="small muted portfolio__note">
        These strategic horizons guide our innovation portfolio, not individual employee targets or rigid quotas. Hover over or select a horizon to learn more.
      </p>
      {detail && (
        <Modal title={detail.title} onClose={() => setActive(null)}>
          <div className="hmodal">
            <span className="hmodal__label">{detail.label}</span>
            <p className="hmodal__q">{detail.question}</p>
            <p>{detail.focus}</p>
            <h4>Purpose</h4>
            <p className="hmodal__purpose">{detail.purpose}</p>
            <h4>Strategic impact</h4>
            <p>{detail.impact}</p>
            {detail.example && (
              <>
                <h4>Example strategic initiative</h4>
                <p><strong>{detail.example.initiative}</strong></p>
                <h4>Example success measure</h4>
                <p><strong>{detail.example.measure}</strong></p>
              </>
            )}
          </div>
        </Modal>
      )}
    </section>
  );
}
