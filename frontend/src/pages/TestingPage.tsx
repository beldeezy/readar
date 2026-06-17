import Button from '../components/Button';
import './TestingPage.css';

/**
 * /testing — internal UX calibration sandbox.
 * Four button treatments across the flat <-> 3D spectrum so we can pick a taste.
 * Not linked in nav; reach it by URL.
 */
export default function TestingPage() {
  return (
    <div className="tb-page">
      <div className="container">
        <h1 className="tb-title">Button calibration</h1>
        <p className="tb-sub rd-tech">UX sandbox · four treatments · flat → 3D</p>

        <div className="tb-grid">
          {/* 1. CURRENT */}
          <section className="tb-col">
            <div className="tb-col-head">
              <span className="tb-label rd-tech">01 · Current</span>
              <p className="tb-desc">What ships today — flat fill, thin border, rounded-rect, brightness hover.</p>
            </div>
            <div className="tb-stack">
              <Button variant="primary">Find my next book</Button>
              <Button variant="secondary">Browse library</Button>
              <Button variant="ghost">Not for me</Button>
              <Button variant="primary" disabled>Disabled</Button>
            </div>
          </section>

          {/* 2. EXTREME — 2D FLAT */}
          <section className="tb-col">
            <div className="tb-col-head">
              <span className="tb-label rd-tech">02 · 2D Flat (extreme)</span>
              <p className="tb-desc">Pure flat — solid block, square-ish corners, no depth at all.</p>
            </div>
            <div className="tb-stack">
              <button className="tb-flat tb-flat--primary">Find my next book</button>
              <button className="tb-flat tb-flat--secondary">Browse library</button>
              <button className="tb-flat tb-flat--ghost">Not for me</button>
              <button className="tb-flat tb-flat--primary" disabled>Disabled</button>
            </div>
          </section>

          {/* 3. EXTREME — 3D DIETER RAMS */}
          <section className="tb-col">
            <div className="tb-col-head">
              <span className="tb-label rd-tech">03 · 3D Rams (extreme)</span>
              <p className="tb-desc">Braun hardware key — bevel, depth, and a tactile press.</p>
            </div>
            <div className="tb-stack">
              <button className="tb-rams tb-rams--primary">Find my next book</button>
              <button className="tb-rams tb-rams--secondary">Browse library</button>
              <button className="tb-rams tb-rams--ghost">Not for me</button>
              <button className="tb-rams tb-rams--primary" disabled>Disabled</button>
            </div>
          </section>

          {/* 4. HYBRID */}
          <section className="tb-col">
            <div className="tb-col-head">
              <span className="tb-label rd-tech">04 · Hybrid</span>
              <p className="tb-desc">Flat fill with a subtle top highlight + soft shadow and a gentle press.</p>
            </div>
            <div className="tb-stack">
              <button className="tb-hybrid tb-hybrid--primary">Find my next book</button>
              <button className="tb-hybrid tb-hybrid--secondary">Browse library</button>
              <button className="tb-hybrid tb-hybrid--ghost">Not for me</button>
              <button className="tb-hybrid tb-hybrid--primary" disabled>Disabled</button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
