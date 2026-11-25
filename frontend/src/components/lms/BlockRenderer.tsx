import { AlertTriangle, ExternalLink, FileText, Lightbulb, StickyNote } from 'lucide-react';
import type { ContentBlock } from '../../api/lms';

/** Content is sanitised on the server at import time; this is the second layer. */
function Html({ html }: { html: string }) {
  return <div className="block__html" dangerouslySetInnerHTML={{ __html: html }} />;
}

function str(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function strList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];
}

export function BlockRenderer({ block }: { block: ContentBlock }) {
  const data = block.data || {};
  const src = str(data.src);
  const text = str(data.text);
  const html = str(data.html);

  switch (block.block_type) {
    case 'rich_text':
    case 'slide':
      return (
        <div className="block">
          {block.title && <h3 className="block__title">{block.title}</h3>}
          {html ? <Html html={html} /> : <p>{text}</p>}
        </div>
      );

    case 'image':
    case 'diagram':
      return (
        <figure className="block block--media">
          {src
            ? <img src={src} alt={str(data.alt) || block.title || ''} loading="lazy" />
            : <p className="muted small">This image is not available.</p>}
          {(str(data.caption) || block.title) && (
            <figcaption>{str(data.caption) || block.title}</figcaption>
          )}
        </figure>
      );

    case 'audio':
      return (
        <div className="block block--media">
          {block.title && <h3 className="block__title">{block.title}</h3>}
          {src ? <audio controls preload="none" src={src} />
            : <p className="muted small">This audio clip is not available.</p>}
        </div>
      );

    case 'video':
      return (
        <div className="block block--media">
          {block.title && <h3 className="block__title">{block.title}</h3>}
          {src ? <video controls preload="metadata" src={src} playsInline />
            : <p className="muted small">This video is not available.</p>}
        </div>
      );

    case 'document':
      return (
        <div className="block">
          <a className="block__file" href={src || '#'} target="_blank" rel="noreferrer">
            <FileText size={18} />
            <span>{block.title || 'Attached document'}</span>
            <ExternalLink size={14} />
          </a>
        </div>
      );

    case 'key_takeaways': {
      const items = strList(data.items);
      if (!items.length) return null;
      return (
        <div className="block block--takeaways">
          <h3 className="block__title"><Lightbulb size={16} /> {block.title || 'Key takeaways'}</h3>
          <ul>{items.map((item, i) => <li key={i}>{item}</li>)}</ul>
        </div>
      );
    }

    case 'notes':
      return (
        <aside className="block block--notes">
          <h3 className="block__title"><StickyNote size={16} /> {block.title || 'Notes'}</h3>
          {html ? <Html html={html} /> : <p>{text}</p>}
        </aside>
      );

    case 'external_reference':
      return (
        <div className="block">
          <a className="block__file" href={str(data.url) || str(data.external_url) || '#'}
             target="_blank" rel="noreferrer noopener">
            <ExternalLink size={16} />
            <span>{block.title || str(data.url) || 'External reference'}</span>
          </a>
        </div>
      );

    case 'html_fallback':
      // Imported markup that could not be decomposed. Sanitised on import and
      // rendered in an isolated frame so it cannot act on Minet's origin.
      return (
        <div className="block">
          {block.title && <h3 className="block__title">{block.title}</h3>}
          <iframe
            className="block__frame"
            title={block.title || 'Imported lesson content'}
            sandbox=""
            srcDoc={`<!doctype html><meta charset="utf-8">
              <meta http-equiv="Content-Security-Policy"
                    content="default-src 'none'; img-src 'none'; style-src 'unsafe-inline';">
              <style>body{font:14px/1.6 system-ui,sans-serif;color:#111827;margin:0;padding:4px}
              img{max-width:100%;height:auto}</style>${html}`}
          />
        </div>
      );

    case 'knowledge_check':
    case 'unsupported':
      return (
        <div className="block block--unsupported">
          <h3 className="block__title"><AlertTriangle size={16} /> {block.title || 'Interactive activity'}</h3>
          <p className="muted">
            {text || 'This activity could not be converted into a Minet lesson block.'}
          </p>
        </div>
      );

    default:
      return html ? <div className="block"><Html html={html} /></div> : null;
  }
}

/** Admin-only wrapper that surfaces import notes beside the rendered block. */
export function ReviewableBlock({ block }: { block: ContentBlock }) {
  return (
    <div className={`reviewblock ${block.needs_review ? 'is-flagged' : ''}`}>
      <div className="reviewblock__head">
        <span className="kind-tag">{block.block_type.replace(/_/g, ' ')}</span>
        {block.needs_review && <span className="status-pill status-pill--amber">Needs review</span>}
      </div>
      <BlockRenderer block={block} />
      {block.import_note && (
        <p className="reviewblock__note"><AlertTriangle size={13} /> {block.import_note}</p>
      )}
    </div>
  );
}
