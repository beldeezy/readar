import StoreLayout, { DISCLOSURE } from './StoreLayout';
import './store.css';

export default function StorePrivacyPage() {
  return (
    <StoreLayout>
      <main className="store-container store-content">
        <h1>Privacy Policy</h1>
        <p>
          Readar respects your privacy. This page explains what we collect on this site and how
          it's used.
        </p>

        <h2>What we collect</h2>
        <p>
          We collect basic, anonymous usage analytics (such as which links are clicked) to
          understand what's useful. We do not require an account to browse this site, and we do
          not collect your name, email, or payment details here.
        </p>

        <h2>Amazon links</h2>
        <p>
          {DISCLOSURE} When you click a link to Amazon, your purchase happens on Amazon under
          Amazon's own privacy policy and terms. We never see your Amazon account or payment
          information.
        </p>

        <h2>Cookies</h2>
        <p>
          Amazon may set cookies to attribute a purchase to Readar as an affiliate. You can
          control cookies through your browser settings.
        </p>

        <h2>Contact</h2>
        <p>Questions about privacy? Email hello@readar.ai.</p>
      </main>
    </StoreLayout>
  );
}
