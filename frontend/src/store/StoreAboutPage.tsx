import StoreLayout, { DISCLOSURE } from './StoreLayout';
import './store.css';

export default function StoreAboutPage() {
  return (
    <StoreLayout>
      <main className="store-container store-content">
        <h1>About Readar</h1>
        <p>
          Readar helps entrepreneurs find their next best book. This shelf is a small,
          hand-picked selection of reads we recommend for building, selling, and scaling a
          business — chosen for usefulness, not hype.
        </p>
        <p>
          Each pick links to Amazon, where you can read more and buy. We keep the list short
          on purpose: clarity over clutter.
        </p>

        <h2>Affiliate disclosure</h2>
        <p>{DISCLOSURE} When you buy through a link on this site, the price you pay is the
          same; Amazon pays Readar a small commission, which helps keep Readar going. We only
          recommend books we genuinely think are worth your time.</p>

        <h2>Contact</h2>
        <p>Questions or suggestions? Email us at hello@readar.ai.</p>
      </main>
    </StoreLayout>
  );
}
