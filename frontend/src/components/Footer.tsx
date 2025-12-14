import LoopsNewsletterForm from "./LoopsNewsletterForm";
import "./Footer.css";

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-newsletter">
          <h2 className="footer-newsletter-headline">
            Want bite-sized insights on a regular basis?
          </h2>

          <p className="footer-newsletter-subtitle">
            Subscribe to <span className="footer-newsletter-em">"The Point"</span> for weekly entrepreneurial observations.
          </p>

          <div className="footer-newsletter-form">
            <LoopsNewsletterForm ctaLabel="Subscribe" />
          </div>
        </div>
      </div>
    </footer>
  );
}

