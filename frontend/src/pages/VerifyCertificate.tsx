import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { BadgeCheck, Search, ShieldAlert } from 'lucide-react';
import { useApi } from '../api/client';
import { formatDate, type VerifyResponse } from '../api/lms';
import { PageHeader } from '../components/PageHeader';
import { ErrorMsg, Loading } from '../components/Bits';

export function VerifyCertificate() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [entered, setEntered] = useState(code ?? '');
  const { data, error, loading } = useApi<VerifyResponse>(
    code ? `/lms/certificates/verify/${encodeURIComponent(code)}` : null);

  return (
    <>
      <PageHeader title="Verify a certificate"
                  subtitle="Check that a Minet Innovation Hub certificate is genuine." />

      <section className="card verify">
        <form className="verify__form" onSubmit={(e) => {
          e.preventDefault();
          if (entered.trim()) navigate(`/verify/${entered.trim().toUpperCase()}`);
        }}>
          <div className="field">
            <label htmlFor="code">Certificate verification code</label>
            <div className="verify__row">
              <input id="code" value={entered} autoComplete="off"
                     onChange={(e) => setEntered(e.target.value.toUpperCase())}
                     placeholder="e.g. H4K9QM2XPT7R" maxLength={16} />
              <button type="submit" className="btn btn--primary">
                <Search size={15} /> Verify
              </button>
            </div>
            <p className="field__hint">The 12-character code printed on the certificate.</p>
          </div>
        </form>

        {error && <ErrorMsg text={error} />}
        {loading && code && <Loading text="Checking..." />}

        {data && data.valid && (
          <div className="verify__result is-valid">
            <BadgeCheck size={30} />
            <div>
              <h2>Valid certificate</h2>
              <dl className="kv">
                <div><dt>Awarded to</dt><dd>{data.recipient_name}</dd></div>
                <div><dt>Course</dt><dd>{data.course_title}</dd></div>
                <div><dt>Certificate number</dt><dd>{data.certificate_number}</dd></div>
                <div><dt>Type</dt><dd>
                  {data.certificate_type === 'assessed_competency'
                    ? 'Assessed competency' : 'Course completion'}
                </dd></div>
                <div><dt>Issued</dt><dd>{formatDate(data.issued_at)}</dd></div>
                <div><dt>Issued by</dt><dd>{data.organisation}</dd></div>
              </dl>
              {data.note && <p className="small muted verify__note">{data.note}</p>}
            </div>
          </div>
        )}

        {data && !data.valid && (
          <div className="verify__result is-invalid">
            <ShieldAlert size={30} />
            <div>
              <h2>Not verified</h2>
              <p className="muted">{data.reason}</p>
              {data.revoked_at && (
                <p className="small muted">Revoked on {formatDate(data.revoked_at)}.</p>
              )}
            </div>
          </div>
        )}
      </section>
    </>
  );
}
