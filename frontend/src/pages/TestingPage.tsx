import type { ReactNode } from 'react';
import './TestingPage.css';

/**
 * /testing — internal UX calibration sandbox (URL-only, no nav).
 * Round 3: buttons (3D Rams baseline + Anduril/Palantir takes) plus other
 * UX components (panels, inputs, tags) shown across the same axes.
 * All styles scoped (tb-*) so they never touch shipping components.
 */
function Reticle({ children }: { children: ReactNode }) {
  return (
    <div className="tb-panel tb-panel--reticle">
      <span className="tb-rt tb-rt--tl" /><span className="tb-rt tb-rt--tr" />
      <span className="tb-rt tb-rt--bl" /><span className="tb-rt tb-rt--br" />
      {children}
    </div>
  );
}

export default function TestingPage() {
  return (
    <div className="tb-page">
      <div className="container">
        <h1 className="tb-title">UX calibration</h1>
        <p className="tb-sub rd-tech">Sandbox · round 3 · Rams ↔ Anduril / Palantir</p>

        {/* ============ BUTTONS ============ */}
        <h2 className="tb-section-title">Buttons</h2>
        <div className="tb-grid">
          {[
            { code: '01', name: 'Current (3D Rams)', desc: 'Winner — Braun hardware key.', cls: 'tb-rams' },
            { code: '02', name: 'Anduril (bracketed)', desc: 'Flat tactical: mono, sharp, accent edge.', cls: 'tb-and' },
            { code: '03', name: 'Palantir (tool)', desc: 'Understated flat hairline control.', cls: 'tb-pal' },
            { code: '04', name: 'Hybrid', desc: 'Rams depth + mono technical label.', cls: 'tb-hyb' },
          ].map((c) => (
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

        {/* ============ PANELS ============ */}
        <h2 className="tb-section-title">Panels / cards</h2>
        <div className="tb-grid">
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">01 · Current (flat)</span></div>
            <div className="tb-panel tb-panel--flat">
              <h3 className="tb-panel-h">The Mom Test</h3>
              <p className="tb-panel-p">Best next read for customer interviews.</p>
            </div>
          </section>
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">02 · Anduril (reticle)</span></div>
            <Reticle>
              <div className="tb-panel-bar rd-tech">SIGNAL · 94% FIT</div>
              <h3 className="tb-panel-h">The Mom Test</h3>
              <p className="tb-panel-p">Best next read for customer interviews.</p>
            </Reticle>
          </section>
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">03 · Palantir (classified)</span></div>
            <div className="tb-panel tb-panel--class">
              <div className="tb-panel-class-bar rd-tech">SECTOR / PRODUCT</div>
              <div className="tb-panel-class-body">
                <h3 className="tb-panel-h">The Mom Test</h3>
                <p className="tb-panel-p">Best next read for customer interviews.</p>
              </div>
            </div>
          </section>
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">04 · Hybrid</span></div>
            <div className="tb-panel tb-panel--hyb">
              <div className="tb-panel-bar rd-tech">SECTOR / PRODUCT · 94% FIT</div>
              <h3 className="tb-panel-h">The Mom Test</h3>
              <p className="tb-panel-p">Best next read for customer interviews.</p>
            </div>
          </section>
        </div>

        {/* ============ INPUTS ============ */}
        <h2 className="tb-section-title">Inputs</h2>
        <div className="tb-grid">
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">01 · Current</span></div>
            <input className="tb-inp tb-inp--current" placeholder="Scan the catalog…" />
          </section>
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">02 · Anduril (terminal)</span></div>
            <div className="tb-inp-term">
              <span className="tb-inp-term-prompt">&gt;</span>
              <input className="tb-inp-term-field" placeholder="SCAN…" />
            </div>
          </section>
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">03 · Palantir (hairline)</span></div>
            <input className="tb-inp tb-inp--pal" placeholder="Scan the catalog…" />
          </section>
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">04 · Hybrid</span></div>
            <input className="tb-inp tb-inp--hyb" placeholder="SCAN THE CATALOG…" />
          </section>
        </div>

        {/* ============ TAGS / STATUS ============ */}
        <h2 className="tb-section-title">Tags / status</h2>
        <div className="tb-grid">
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">01 · Current (signal)</span></div>
            <div className="tb-tagrow"><span className="tb-tag tb-tag--signal">High fit</span></div>
          </section>
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">02 · Anduril (status)</span></div>
            <div className="tb-tagrow">
              <span className="tb-tag tb-tag--status">● ACTIVE</span>
              <span className="tb-tag tb-tag--status tb-tag--warn">● CAUTION</span>
            </div>
          </section>
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">03 · Palantir (bracket)</span></div>
            <div className="tb-tagrow"><span className="tb-tag tb-tag--bracket">SECTOR / STRATEGY</span></div>
          </section>
          <section className="tb-col">
            <div className="tb-col-head"><span className="tb-label rd-tech">04 · Hybrid</span></div>
            <div className="tb-tagrow"><span className="tb-tag tb-tag--hyb">● HIGH FIT</span></div>
          </section>
        </div>
      </div>
    </div>
  );
}
