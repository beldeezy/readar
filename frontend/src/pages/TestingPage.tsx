import './TestingPage.css';

/**
 * /testing — internal UX calibration sandbox (URL-only, no nav).
 * Round 2: 3D Rams is the current baseline; explore More Rams, More
 * Military, and a Hybrid. Styles are scoped (tb-*) so they never touch
 * the shipping Button.
 */
export default function TestingPage() {
  const cols: { code: string; name: string; desc: string; cls: string }[] = [
    { code: '01', name: 'Current (3D Rams)', desc: 'The winner so far — Braun hardware key with bevel, depth, and a tactile press.', cls: 'tb-rams' },
    { code: '02', name: 'More Rams', desc: 'Push the appliance feel: rounder, more sculpted bevel, deeper travel.', cls: 'tb-ramsx' },
    { code: '03', name: 'More Military', desc: 'Tactical key — knurled face, squared corners, mono label, amber indicator.', cls: 'tb-mil' },
    { code: '04', name: 'Hybrid', desc: 'Rams depth + military mono label: dimensional key with a technical voice.', cls: 'tb-hyb' },
  ];

  return (
    <div className="tb-page">
      <div className="container">
        <h1 className="tb-title">Button calibration</h1>
        <p className="tb-sub rd-tech">UX sandbox · round 2 · Rams → military</p>

        <div className="tb-grid">
          {cols.map((c) => (
            <section className="tb-col" key={c.code}>
              <div className="tb-col-head">
                <span className="tb-label rd-tech">{c.code} · {c.name}</span>
                <p className="tb-desc">{c.desc}</p>
              </div>
              <div className="tb-stack">
                <button className={`${c.cls} ${c.cls}--primary`}>Find my next book</button>
                <button className={`${c.cls} ${c.cls}--secondary`}>Browse library</button>
                <button className={`${c.cls} ${c.cls}--ghost`}>Not for me</button>
                <button className={`${c.cls} ${c.cls}--primary`} disabled>Disabled</button>
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
