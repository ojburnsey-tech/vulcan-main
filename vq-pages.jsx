// vq-pages.jsx — all page components
const { useState, useEffect, useRef } = React;
const { BoQMockup, AppSidebar, VQParticleField } = window;

// ─── LANDING ────────────────────────────────────────────────────────────────────────
function LandingPage({ go, tweaks = {}, toast }) {
  const [openFaq, setOpenFaq] = useState(null);
  const videoRef      = useRef(null);
  const taglineRef    = useRef(null);
  const scrollHintRef = useRef(null);

  // ── GSAP: fixed-video scroll-scrub across 5× viewport height ─────────────────
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const isMobile = window.matchMedia?.('(max-width: 768px)').matches;
    if (reduceMotion || isMobile) {
      video.setAttribute('preload', 'metadata');
      return;
    }

    let triggers = [];
    let timeline = null;
    let metaHandler = null;
    let primeHandler = null;
    let onLoad = null;

    const init = () => {
      const { gsap, ScrollTrigger } = window;
      if (!gsap || !ScrollTrigger) return;
      gsap.registerPlugin(ScrollTrigger);

      const dur = video.duration || 8;

      // Scrub video across 5 viewport-heights of total scroll distance.
      const st = ScrollTrigger.create({
        trigger: document.documentElement,
        start: 'top top',
        end: () => `+=${window.innerHeight * 5}`,
        scrub: 1,
        onUpdate: (self) => {
          if (video.readyState >= 1 && !video.seeking) {
            video.currentTime = self.progress * dur;
          }
        },
      });
      triggers.push(st);

      // Tagline: visible at scroll-0, holds, fades out in the first viewport's scroll.
      timeline = gsap.timeline({
        scrollTrigger: {
          trigger: document.documentElement,
          start: 'top top',
          end: () => `+=${window.innerHeight * 0.85}`,
          scrub: 1.5,
        },
      });
      if (timeline.scrollTrigger) triggers.push(timeline.scrollTrigger);

      timeline.to(taglineRef.current, { opacity: 0, y: -18, duration: 0.35 }, 0.55);
      timeline.to(scrollHintRef.current, { opacity: 0, duration: 0.12 }, 0.05);

      ScrollTrigger.refresh();
      onLoad = () => ScrollTrigger.refresh();
      window.addEventListener('load', onLoad);
    };

    // iOS Safari won't paint seeks until the video has played once.
    primeHandler = () => {
      const p = video.play();
      if (p?.then) p.then(() => video.pause()).catch(() => {});
      else { try { video.pause(); } catch (e) {} }
    };
    window.addEventListener('touchstart', primeHandler, { once: true, passive: true });
    window.addEventListener('pointerdown', primeHandler, { once: true });

    const timer = setTimeout(() => {
      if (video.readyState >= 1) {
        init();
      } else {
        metaHandler = init;
        video.addEventListener('loadedmetadata', metaHandler, { once: true });
      }
    }, 80);

    return () => {
      clearTimeout(timer);
      if (metaHandler) video.removeEventListener('loadedmetadata', metaHandler);
      if (onLoad) window.removeEventListener('load', onLoad);
      window.removeEventListener('touchstart', primeHandler);
      window.removeEventListener('pointerdown', primeHandler);
      triggers.forEach(t => t?.kill());
      if (timeline) timeline.kill();
      if (window.gsap) {
        window.gsap.killTweensOf([taglineRef.current, scrollHintRef.current]);
      }
    };
  }, []);

  const faqs = [
    { q: 'How accurate is Vulcan Quanta?',
      a: 'Our AI is trained on thousands of professional BoQs and UK drawings. Accuracy is 94% on standard projects. Every item is confidence-scored so you know exactly where to focus your review.' },
    { q: 'What drawing formats does it accept?',
      a: 'Currently PDF — raster and vector, single or multi-page. JPG and PNG support is planned.' },
    { q: 'Is my data secure?',
      a: 'Drawings are encrypted in transit and at rest, deleted after 30 days, and never used for model training. GDPR-compliant, UK-hosted.' },
    { q: 'Do I still need a qualified quantity surveyor?',
      a: 'Vulcan removes the measurement and rate-application work — typically 5–8 hours per job. A human QS still reviews every output for fitness for purpose and professional liability. You save time; you keep control.' },
    { q: 'Can I customise rate tables and output branding?',
      a: 'Pro plan includes custom branding, logo and trade breakdowns. Studio adds custom rate tables, regional overrides and up to 5 team seats.' },
  ];

  const plans = [
    { name: 'Free', price: '£0', period: 'forever', rec: false,
      feats: [
        { on: true,  t: '2 projects per month' },
        { on: true,  t: 'Watermarked output' },
        { on: true,  t: 'PDF export' },
        { on: false, t: 'Excel export' },
        { on: false, t: 'Custom branding' },
        { on: false, t: 'Priority support' },
      ],
      cta: 'Get started', action: () => go('signup') },
    { name: 'Pro', price: '£39', period: 'per month', rec: true,
      feats: [
        { on: true,  t: 'Unlimited projects' },
        { on: true,  t: 'No watermark' },
        { on: true,  t: 'PDF & Excel export' },
        { on: true,  t: 'Your branding & logo' },
        { on: true,  t: 'Custom trade sections' },
        { on: false, t: 'Team seats (up to 5)' },
      ],
      cta: 'Start free trial', action: () => go('signup') },
    { name: 'Studio', price: '£99', period: 'per month', rec: false,
      feats: [
        { on: true, t: 'Everything in Pro' },
        { on: true, t: 'Up to 5 team seats' },
        { on: true, t: 'White-label output' },
        { on: true, t: 'Custom rates & rules' },
        { on: true, t: 'Variation order templates' },
        { on: true, t: 'Priority support' },
      ],
      cta: 'Contact sales', action: () => toast('Get in touch: hello@vulcanquanta.com', 'info') },
  ];

  return (
    <>
      {/* ── FIXED VIDEO BACKGROUND — sits behind the entire page at z-index 0 ── */}
      <div className="cin-video-bg" aria-hidden="true">
        <video
          ref={videoRef}
          className="cin-video"
          src="hero.mp4"
          muted
          playsInline
          preload="auto"
          aria-hidden="true"
          tabIndex={-1}
        />
        <div className="cin-overlay" />
      </div>

      {/* ── FIXED TAGLINE OVERLAY — z-index 5, fades out as user scrolls ────── */}
      <div className="cin-phase-wrap">
        <div ref={taglineRef}>
          <p className="cin-eyebrow">Vulcan Quanta</p>
          <h1 className="cin-h1">
            Cost plans that used<br />to take days.<br />Now they don't.
          </h1>
          <button
            className="btn btn-amber btn-pill"
            style={{ padding: '14px 28px', fontSize: '15px', fontWeight: 600 }}
            onClick={() => go('signup')}
          >
            Start free
          </button>
          <p className="cin-hero-note">
            No credit card required · UK quantity surveying · AI-powered
          </p>
        </div>
        <div ref={scrollHintRef} className="cin-scroll-hint" aria-hidden="true">
          <div className="cin-scroll-line" />
          <span>Scroll</span>
        </div>
      </div>

      {/* ── TRANSPARENT SPACER — creates 100vh of scroll room for the video ─── */}
      <div className="cin-hero-spacer" />

      {/* ── 2. EDITORIAL STATEMENT ───────────────────────────────────────────── */}
      <section className="cin-statement">
        <div className="inner">
          <p className="cin-section-label">The work</p>
          <p className="cin-statement-text">
            Vulcan reads your drawings. Every wall, every span, every height.
            Priced to BCIS. Structured to NRM2. Ready to issue.
          </p>
        </div>
      </section>

      {/* ── 3. THREE-STEP PROCESS ────────────────────────────────────────────── */}
      <section className="cin-process">
        <div className="inner">
          <p className="cin-section-label">Three steps</p>
          <h2 className="cin-section-h">From drawing to priced BoQ.</h2>
          <div className="cin-process-grid">
            {[
              { n: '01', title: 'Upload your drawing',
                desc: 'Drag a PDF — single or multi-page, raster or vector. Takes seconds.' },
              { n: '02', title: 'Vulcan measures and prices',
                desc: 'AI reads every element, applies current BCIS rates, and produces a fully itemised BoQ. Under 2 minutes.' },
              { n: '03', title: 'Review, edit, export',
                desc: 'Edit any item inline. Export as PDF or Excel, ready to issue under your own branding.' },
            ].map((s, i) => (
              <div key={i} className="cin-process-item">
                <p className="cin-process-num">{s.n}</p>
                <p className="cin-process-title">{s.title}</p>
                <p className="cin-process-desc">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 4. PRODUCT SPLIT — BoQ MOCKUP ────────────────────────────────────── */}
      <section className="cin-split">
        <div className="cin-split-inner">
          <div>
            <p className="cin-section-label-dk">Output</p>
            <h2 className="cin-section-h-lt">A professional BoQ, ready to issue.</h2>
            <p className="cin-split-sub">
              Every element measured. Every item priced to BCIS Q2 2026 rates.
              Confidence-scored. Structured to NRM2.
            </p>
            <button
              className="btn btn-amber btn-pill"
              style={{ marginTop: '32px', padding: '14px 28px', fontSize: '15px', fontWeight: 600 }}
              onClick={() => go('results', { sample: true })}
            >
              See a sample BoQ →
            </button>
          </div>
          <div>
            <BoQMockup />
          </div>
        </div>
      </section>

      {/* ── 5. CAPABILITY GRID ───────────────────────────────────────────────── */}
      <section className="cin-features">
        <div className="inner">
          <p className="cin-section-label-dk">Capabilities</p>
          <h2 className="cin-section-h-lt">Built for professional work.</h2>
          <div className="cin-feat-grid">
            {[
              { name: 'Automated measurement',
                desc: 'Reads every wall, opening, span and height directly from your PDF. No manual scaling.' },
              { name: 'Current UK rates',
                desc: 'BCIS Q2 2026 labour and material rates, with regional variations included.' },
              { name: 'Confidence scoring',
                desc: 'Every item flagged for confidence level. Low-confidence items highlighted for review.' },
              { name: 'Professional export',
                desc: 'PDF and Excel output. Your branding on Pro and Studio plans. Ready to issue.' },
              { name: 'Variation orders',
                desc: 'Duplicate, edit and track additions with a timestamped audit trail.' },
              { name: 'Your branding',
                desc: 'Add your logo, address and colours to every output on Pro and Studio plans.' },
            ].map((f, i) => (
              <div key={i} className="cin-feat-item">
                <p className="cin-feat-name">{f.name}</p>
                <p className="cin-feat-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 6. PROOF — REAL CLAIMS ONLY ──────────────────────────────────────── */}
      <section className="cin-proof">
        <div className="inner">
          <p className="cin-section-label">What you can rely on</p>
          <h2 className="cin-section-h">Methodology and data.</h2>
          <div className="cin-proof-grid">
            {[
              { label: 'Accuracy',
                claim: '94% accuracy on standard UK construction projects.',
                note: 'Trained on thousands of professional BoQs and UK drawings. Every item is confidence-scored.' },
              { label: 'Rates',
                claim: 'BCIS Q2 2026 labour and material rates.',
                note: 'National schedule with regional variations. Updated quarterly to reflect current market costs.' },
              { label: 'Data',
                claim: 'GDPR-compliant. UK-hosted. Deleted after 30 days.',
                note: 'Encrypted in transit and at rest. Your drawings are never used for model training.' },
              { label: 'Standard',
                claim: 'Output structured to NRM2.',
                note: 'Aligned with the RICS standard method of measurement. Professional QS review always recommended.' },
              { label: 'Control',
                claim: 'Human approval is always required.',
                note: 'Every output is a reviewable draft. Vulcan removes the measurement work — not the professional.' },
              { label: 'Status',
                claim: 'Private beta. Built with QS practices.',
                note: 'We are working with a select group of UK builders and QS firms before full public launch.' },
            ].map((p, i) => (
              <div key={i} className="cin-proof-item">
                <p className="cin-proof-label">{p.label}</p>
                <p className="cin-proof-claim">{p.claim}</p>
                <p className="cin-proof-note">{p.note}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 7. PRICING ───────────────────────────────────────────────────────── */}
      <section className="cin-pricing">
        <div className="inner">
          <p className="cin-section-label-dk">Pricing</p>
          <h2 className="cin-section-h-lt">Simple pricing. No surprises.</h2>
          <p className="cin-pricing-sub">Start free. Scale as you grow. No long-term contracts.</p>
          <div className="pricing-grid" style={{ marginTop: '64px' }}>
            {plans.map((plan, i) => (
              <div key={i} className={`pricing-card ${plan.rec ? 'rec' : ''}`}>
                {plan.rec && <p className="pricing-badge">Most popular</p>}
                <p className="pricing-name">{plan.name}</p>
                <p className="pricing-price">{plan.price}</p>
                <p className="pricing-period">{plan.period}</p>
                <ul className="pricing-feats">
                  {plan.feats.map((f, j) =>
                    <li key={j} className={f.on ? 'on' : 'off'}>{f.t}</li>
                  )}
                </ul>
                <button
                  className={`btn btn-pill ${plan.rec ? 'btn-amber' : 'btn-outline'}`}
                  style={{ width: '100%' }}
                  onClick={plan.action}
                >{plan.cta}</button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 8. FAQ ───────────────────────────────────────────────────────────── */}
      <section className="cin-faq">
        <div className="inner">
          <p className="cin-section-label-dk">Questions</p>
          <h2 className="cin-section-h-lt" style={{ marginBottom: '56px' }}>Frequently asked.</h2>
          <div className="acc-wrap">
            {faqs.map((item, i) => (
              <div key={i} className="acc-item">
                <button
                  type="button"
                  className="acc-hd"
                  style={{ width: '100%', textAlign: 'left' }}
                  aria-expanded={openFaq === i}
                  aria-controls={`faq-body-${i}`}
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                >
                  <span className="acc-q">{item.q}</span>
                  <svg
                    className={`acc-chevron ${openFaq === i ? 'open' : ''}`}
                    viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" strokeWidth="2"
                    strokeLinecap="round" strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
                <div id={`faq-body-${i}`} className={`acc-body ${openFaq === i ? 'open' : ''}`}>
                  <p>{item.a}</p>
                </div>
              </div>
            ))}
          </div>
          <p style={{ marginTop: '48px', fontSize: '14px', color: 'var(--c-400)' }}>
            Anything else? <a href="mailto:hello@vulcanquanta.com" style={{ color: 'var(--amber)', fontWeight: 600 }}>hello@vulcanquanta.com</a>
          </p>
        </div>
      </section>

      {/* ── 9. FINAL CTA ─────────────────────────────────────────────────────── */}
      <section className="cin-cta">
        <div className="inner" style={{ textAlign: 'center' }}>
          <p className="cin-eyebrow" style={{ color: 'rgba(255,255,255,0.28)', marginBottom: '28px' }}>Vulcan Quanta</p>
          <h2 className="cin-cta-h">Cost plans that used<br />to take days.</h2>
          <p className="cin-cta-sub">Now they don't.</p>
          <div className="cin-cta-actions">
            <button className="btn btn-amber btn-pill btn-lg" onClick={() => go('signup')}>
              Start free
            </button>
            <button className="btn-ghost-lt" onClick={() => go('results', { sample: true })}>
              See a sample BoQ →
            </button>
          </div>
          <p style={{ marginTop: '28px', fontSize: '13px', color: 'rgba(255,255,255,0.22)' }}>
            No credit card required · Cancel anytime
          </p>
        </div>
      </section>

      {/* Security strip */}
      <div className="sec-strip">
        <div className="inner">
          <div className="sec-items">
            {[
              { icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>, text: 'GDPR compliant' },
              { icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>, text: 'Encrypted at rest' },
              { icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 010 20M12 2a15.3 15.3 0 000 20"/></svg>, text: 'UK-hosted' },
              { icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>, text: 'Human review built in' },
              {
                icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>,
                text: 'GDPR compliant'
              },
              {
                icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
                text: 'Encrypted at rest'
              },
              {
                icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 010 20M12 2a15.3 15.3 0 000 20"/></svg>,
                text: 'UK-hosted'
              },
              {
                icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
                text: 'Human review built in'
              },
            ].map((s, i) => (
              <div key={i} className="sec-item"><span>{s.icon}</span><span>{s.text}</span></div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ─── BOQ NORMALISER ─────────────────────────────────────────────────────────────────
// Claude may return several JSON shapes. This converts all of them to a flat array of
// items with the same fields used by ResultsPage, regardless of what Claude produced.
function normaliseBoq(raw) {
  // Guard: null, primitives, and arrays-of-primitives are not valid BoQ objects
  if (!raw || typeof raw !== 'object') return [];

  // Resolve the array of trade groups from whichever shape Claude returned:
  //   [{trade, items}]  |  {bill_of_quantities:[...]}  |  {trades:[...]}
  //   {groundworks:[...], brickwork:[...]}  (trade name → items array)
  let groups;
  if (Array.isArray(raw)) {
    groups = raw;
  } else if (Array.isArray(raw.bill_of_quantities)) {
    groups = raw.bill_of_quantities;
  } else if (Array.isArray(raw.trades)) {
    groups = raw.trades;
  } else {
    // Keys are trade names; only include entries whose value is an array
    groups = Object.entries(raw)
      .filter(([, v]) => Array.isArray(v))
      .map(([trade, items]) => ({ trade, items }));
  }

  // Final safety net: if groups is still not an array, return empty
  if (!Array.isArray(groups)) return [];

  let id = 0;
  // flatMap is like SelectMany in C# LINQ — it flattens one level of nesting
  return groups.flatMap(g => {
    if (!g || typeof g !== 'object' || Array.isArray(g)) return [];
    const trade = g.trade || g.name || 'General';
    const items = Array.isArray(g.items) ? g.items
                : Array.isArray(g.line_items) ? g.line_items
                : [];
    return items
      .filter(it => it && typeof it === 'object')
      .map(it => ({
        id:   ++id,
        trade,
        desc: it.description || it.desc || '',
        qty:  parseFloat(it.quantity ?? it.qty ?? 0),
        unit: it.unit || '',
        rate: parseFloat(it.rate ?? 0),
        flag: false,
      }));
  });
}

// ─── RESULTS ───────────────────────────────────────────────────────────────────────
// boqData is the raw JSON object returned by POST /process (null when demo mode)
// demo=true renders the restricted public preview: exports disabled, no grand summary
// sample=true renders the built-in mock BoQ (landing page "See a sample BoQ")
// projectId is set when arriving from a project row, so the no-BoQ empty state
// can link straight back to that project's workspace
function ResultsPage({ go, toast, boqData, embedded, demo, sample, projectId }) {
  const [pdfState, setPdfState] = useState('idle');
  const [excelState, setExcelState] = useState('idle');
  const [contingency, setContingency] = useState(10);

  // Demo items shown when no real upload has been processed yet
  const mockItems = [
    { id: 1, trade: 'Groundworks', desc: 'Excavation to reduced level', qty: 250, unit: 'm²', rate: 8.50, flag: false },
    { id: 2, trade: 'Groundworks', desc: 'Concrete strip foundations', qty: 85, unit: 'm³', rate: 95.00, flag: false },
    { id: 3, trade: 'Brickwork', desc: 'Common brickwork, stretcher bond', qty: 2400, unit: 'No', rate: 0.65, flag: true },
    { id: 4, trade: 'Brickwork', desc: 'Blockwork (common)', qty: 1850, unit: 'No', rate: 0.45, flag: false },
    { id: 5, trade: 'Carpentry', desc: 'Timber joists 4×2"', qty: 450, unit: 'lm', rate: 2.20, flag: false },
    { id: 6, trade: 'Roofing', desc: 'Clay tile roof covering', qty: 320, unit: 'm²', rate: 38.50, flag: true },
    { id: 7, trade: 'Plastering', desc: 'Internal plaster (float & set)', qty: 980, unit: 'm²', rate: 7.50, flag: false },
    { id: 8, trade: 'Electrical', desc: 'Cable & conduit first fix', qty: 1200, unit: 'lm', rate: 3.20, flag: false },
    { id: 9, trade: 'Plumbing', desc: 'Water pipes (15mm copper)', qty: 450, unit: 'lm', rate: 5.50, flag: false },
    { id: 10, trade: 'Finishes', desc: 'Emulsion paint (2 coats)', qty: 1420, unit: 'm²', rate: 2.10, flag: false },
  ];
  // If the API returned data normalise it; otherwise fall back to demo items
  const baseItems = boqData ? normaliseBoq(boqData) : mockItems;

  // qtys holds the editable quantity for each line, keyed by item id
  // useState lazy initialiser (the arrow function) only runs once on mount,
  // at which point boqData is already resolved — equivalent to a C# field initialiser
  const [qtys, setQtys] = useState(() => Object.fromEntries(baseItems.map(i => [i.id, i.qty])));
  const fmt = n => `£${n.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const calc = (id, rate) => (qtys[id] || 0) * rate;
  // Derive trade list from the actual items in order of first appearance, deduped with Set
  const trades = [...new Set(baseItems.map(i => i.trade))];
  const subtotal = baseItems.reduce((s, i) => s + calc(i.id, i.rate), 0);
  const contAmt = subtotal * (contingency / 100);
  const grandTotal = subtotal + contAmt;
  const flagCount = baseItems.filter(i => i.flag).length;
  let rowIdx = 0;

  // Build the JSON payload for POST /download.
  // Real mode: boqData is the enriched JSON from /process — send it as-is.
  // Demo mode: boqData is null, so we convert the current baseItems (with editable qtys).
  const buildPayload = () => {
    if (boqData) return boqData;                   // real upload — all fields already present
    const byTrade = {};                            // group mock items by trade name
    baseItems.forEach(item => {
      if (!byTrade[item.trade]) byTrade[item.trade] = [];
      byTrade[item.trade].push({
        description:   item.desc,
        quantity:      qtys[item.id] ?? item.qty,  // use editable qty if available
        unit:          item.unit,
        material_rate: +(item.rate * 0.40).toFixed(2),   // split combined rate ~40/60 mat/lab
        labour_rate:   +(item.rate * 0.60).toFixed(2),
        line_total:    +((qtys[item.id] ?? item.qty) * item.rate).toFixed(2),
      });
    });
    // Convert to [{trade, items}] — the shape _normalise_boq in export_pdf.py expects
    return Object.entries(byTrade).map(([trade, items]) => ({ trade, items }));
  };

  const handleDownload = async () => {
    if (pdfState !== 'idle') return;
    setPdfState('generating');
    toast('Generating PDF…', 'info');

    try {
      const { data: { session: vqSession } } = window.VQAuth
        ? await window.VQAuth.getSession()
        : { data: { session: null } };
      const token = vqSession?.access_token || '';

      // POST the BoQ JSON to the server; Flask calls generate_boq_pdf() and streams the result back.
      const res = await fetch('https://vulcan-production-d039.up.railway.app/download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(buildPayload()),
        credentials: 'include',
      });

      if (!res.ok) {
        // Try to read a JSON error body from Flask; fall back to the HTTP status text
        const err = await res.json().catch(() => ({ error: res.statusText }));
        toast(err.error || 'PDF generation failed — please try again.', 'error');
        setPdfState('idle');
        return;
      }

      // Convert the HTTP response body to a Blob (binary large object).
      // There is no direct filesystem API in the browser, so we:
      //   1. Create a temporary object URL pointing to the Blob in memory
      //   2. Programmatically click a hidden <a> element with that URL as href
      //   3. Revoke the URL immediately after to free memory
      // This is the standard cross-browser pattern for downloading fetch() responses as files.
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);    // like a temporary in-memory file path
      const a    = document.createElement('a');  // create an invisible anchor element
      a.href     = url;
      a.download = 'bill-of-quantities.pdf';     // suggested filename shown in the Save dialog
      document.body.appendChild(a);             // must be in the DOM for Firefox to trigger the download
      a.click();                                 // fires the download
      document.body.removeChild(a);             // clean up immediately
      URL.revokeObjectURL(url);                  // release the Blob from memory

      setPdfState('done');
      toast('PDF downloaded.', 'success');
      setTimeout(() => setPdfState('idle'), 3000);

    } catch (err) {
      // fetch() only throws on network failure (DNS error, no connection, etc.)
      // HTTP 4xx/5xx responses do NOT throw — they are handled by the !res.ok branch above
      toast('Network error — could not reach the server.', 'error');
      setPdfState('idle');
    }
  };

  const handleExcelDownload = async () => {
    if (excelState !== 'idle') return;
    setExcelState('generating');
    toast('Generating Excel…', 'info');

    try {
      const { data: { session: vqSession } } = window.VQAuth
        ? await window.VQAuth.getSession()
        : { data: { session: null } };
      const token = vqSession?.access_token || '';

      const res = await fetch('https://vulcan-production-d039.up.railway.app/export-excel', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(buildPayload()),
        credentials: 'include',
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        toast(err.error || 'Excel generation failed — please try again.', 'error');
        setExcelState('idle');
        return;
      }

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = 'bill-of-quantities.xlsx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setExcelState('done');
      toast('Excel downloaded.', 'success');
      setTimeout(() => setExcelState('idle'), 3000);

    } catch (err) {
      toast('Network error — could not reach the server.', 'error');
      setExcelState('idle');
    }
  };

  // A real project with no generated BoQ: say so plainly instead of showing
  // the mock data, which is only meant for the demo / sample views.
  if (!boqData && !demo && !sample) {
    const empty = (
      <div className="res-wrap" style={embedded ? { minHeight: 'auto' } : undefined}>
        <div className="res-pad" style={embedded ? { padding: '8px 0' } : undefined}>
          {!embedded && <span className="res-back" onClick={() => go('dashboard')}>← Back to dashboard</span>}
          <h1 className="res-title">Bill of Quantities</h1>
          <div className="vd-empty" style={{ padding: '72px 24px' }}>
            <p className="vd-empty-p">No BoQ has been generated for this project yet.</p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
              {projectId && (
                <button className="btn btn-amber btn-pill" onClick={() => go('workspace', { projectId })}>Generate a BoQ →</button>
              )}
              <button className="btn btn-outline btn-pill" onClick={() => go('projects')}>Back to projects</button>
            </div>
          </div>
        </div>
      </div>
    );
    if (embedded) return empty;
    return (
      <div className="app-wrap">
        <AppSidebar currentPage="results" go={go} toast={toast} />
        <div className="app-main">{empty}</div>
      </div>
    );
  }

  const inner = (
      <div className="res-wrap" style={embedded ? { minHeight: 'auto' } : undefined}>
      <div className="res-pad" style={embedded ? { padding: '8px 0' } : undefined}>
        {!embedded && <span className="res-back" onClick={() => go('dashboard')}>← Back to dashboard</span>}
        <h1 className="res-title">Bill of Quantities</h1>
        <div className="res-meta">
          <span><strong>Drawing:</strong> Commercial Unit — Main Floor Plan</span>
          <span><strong>Processed:</strong> 4 Jun 2026</span>
          <span><strong>Rates:</strong> BCIS Q2 2026</span>
        </div>
        <div className="conf-row">
          <span className="conf-lbl">Confidence:</span>
          <div className="conf-track"><div className="conf-fill" style={{ width: '92%' }} /></div>
          <span className="conf-pct">92%</span>
          {flagCount > 0 && <span className="conf-note">— {flagCount} item{flagCount !== 1 ? 's' : ''} flagged for review</span>}
        </div>
        <p className="res-disclaimer">AI-generated draft — professional review required before issue to client. Edit inline, then export.</p>
        <div className="res-controls">
          {demo ? (
            <>
              <button className="btn btn-amber btn-pill" disabled title="Create a free account to export" style={{ opacity: 0.45, cursor: 'not-allowed' }}>🔒 Download PDF</button>
              <button className="btn btn-outline btn-pill" disabled title="Create a free account to export" style={{ opacity: 0.45, cursor: 'not-allowed' }}>🔒 Excel</button>
              <span style={{ alignSelf: 'center', fontSize: '12px', color: 'rgba(255,255,255,0.4)' }}>Exports are unavailable in the demo.</span>
            </>
          ) : (
            <>
          <button className="btn btn-amber btn-pill" onClick={handleDownload} disabled={pdfState !== 'idle'}>
            {pdfState === 'idle'       && '↓ Download PDF'}
            {pdfState === 'generating' && '⏳ Generating PDF…'}
            {pdfState === 'done'       && '✓ Downloaded'}
          </button>
<button className="btn btn-outline btn-pill" onClick={handleExcelDownload} disabled={excelState !== 'idle'}>
  {excelState === 'idle'       && 'Excel'}
  {excelState === 'generating' && '⏳ Generating…'}
  {excelState === 'done'       && '✓ Downloaded'}
</button>          <button className="btn btn-outline btn-pill" onClick={() => { navigator.clipboard?.writeText?.(window.location.href); toast('Share link copied to clipboard!', 'success'); }}>🔗 Share</button>
            </>
          )}
        </div>

        <table className="rboq">
          <thead>
            <tr>
              <th>Description</th>
              <th className="r">Qty</th>
              <th className="r">Unit</th>
              <th className="r">Unit rate</th>
              <th className="r">Line total</th>
            </tr>
          </thead>
          <tbody>
            {trades.map(trade => {
              const tItems = baseItems.filter(i => i.trade === trade);
              const tTotal = tItems.reduce((s, i) => s + calc(i.id, i.rate), 0);
              return (
                <React.Fragment key={trade}>
                  <tr className="rboq-trade"><td colSpan="5">{trade}</td></tr>
                  {tItems.map(item => {
                    rowIdx++;
                    return (
                      <tr key={item.id} className={`rboq-item${rowIdx % 2 === 0 ? ' alt' : ''}${item.flag ? ' flagged' : ''}`}>
                        <td>{item.desc}{item.flag && <span className="flag-chip">⚠ Verify</span>}</td>
                        <td className="r">
                          <input className="edit-inp" type="number"
                            value={qtys[item.id]}
                            onChange={e => setQtys(p => ({ ...p, [item.id]: parseFloat(e.target.value) || 0 }))} />
                        </td>
                        <td className="r">{item.unit}</td>
                        <td className="r">{fmt(item.rate)}</td>
                        <td className="r fw">{fmt(calc(item.id, item.rate))}</td>
                      </tr>
                    );
                  })}
                  <tr className="rboq-sub">
                    <td colSpan="4" style={{ textAlign: 'right' }}>Subtotal — {trade}</td>
                    <td className="r">{fmt(tTotal)}</td>
                  </tr>
                </React.Fragment>
              );
            })}
            {!demo && (
              <>
            <tr className="rboq-sub rboq-sub-main">
              <td colSpan="4" style={{ textAlign: 'right' }}>Works subtotal</td>
              <td className="r">{fmt(subtotal)}</td>
            </tr>
            <tr className="rboq-item">
              <td>Contingency / risk allowance</td>
              <td className="r" colSpan="2">
                <input className="edit-inp" type="number" value={contingency}
                  onChange={e => setContingency(parseFloat(e.target.value) || 0)}
                  style={{ width: '48px' }} /> %
              </td>
              <td></td>
              <td className="r fw">{fmt(contAmt)}</td>
            </tr>
            <tr className="rboq-total">
              <td colSpan="4" style={{ textAlign: 'right' }}>Grand Total (ex. VAT)</td>
              <td className="r">{fmt(grandTotal)}</td>
            </tr>
              </>
            )}
          </tbody>
        </table>
        <p style={{ marginTop: '20px', fontSize: '12px', color: 'rgba(255,255,255,0.32)', fontStyle: 'italic' }}>
          AI-estimated using BCIS Q2 2026 rates. Subject to market variation and supplier pricing. Professional QS review recommended before tender or client issue.
        </p>
      </div>
      </div>
  );

  if (embedded) return inner;

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="results" go={go} toast={toast} />
      <div className="app-main">{inner}</div>
    </div>
  );
}

// ─── DASHBOARD ───────────────────────────────────────────────────────────────────────
// Base URL for the Railway backend — same host used by /process, /download, /projects.
const VQ_API = 'https://vulcan-production-d039.up.railway.app';

// ─── Upload resilience (shared by every /process + /demo-process caller) ──────────────
// The backend's gunicorn worker timeout is 360s. We abort the client fetch a bit
// before that so a hung backend gives the user feedback instead of an endless fake
// progress bar. 280s leaves room for the server to return its own clean 504 from the
// 240s Claude timeout first; only a truly stuck backend trips this.
const VQ_UPLOAD_TIMEOUT_MS = 280000;

// Map a fetch() REJECTION to a specific, debuggable message. fetch() only rejects on
// (a) an AbortController abort, or (b) a true network/CORS failure (TypeError) — HTTP
// 4xx/5xx do NOT reject and are handled via res.ok at each call site. Centralising this
// keeps the three near-duplicate upload blocks from drifting apart on wording.
function vqUploadErrorMessage(err) {
  if (err && err.name === 'AbortError') {
    return 'The server is taking longer than expected — your file may still be processing. Please check back in a minute or try a smaller PDF.';
  }
  if (err instanceof TypeError) {
    // Classic opaque failure: connection reset, DNS, or a response missing CORS
    // headers (e.g. a killed worker). Distinct wording so it's separable in support.
    return 'Network error — could not reach the server. Check your connection and try again.';
  }
  return (err && err.message) ? err.message : 'Something went wrong. Please try again.';
}

// Start a fetch abort timer; returns { signal, clear } — call clear() once the
// response (or error) has arrived so the timer can't fire late.
function vqAbortTimer(ms = VQ_UPLOAD_TIMEOUT_MS) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, clear: () => clearTimeout(id) };
}

// Resolve the current Supabase access token (empty string when not signed in / configured).
async function vqToken() {
  const { data: { session } } = window.VQAuth
    ? await window.VQAuth.getSession()
    : { data: { session: null } };
  return session?.access_token || '';
}

// Human-readable "time since" from an ISO timestamp — "just now", "2 hours ago",
// "yesterday", "3 days ago", etc. Returns '' for missing/invalid input.
function vqTimeAgo(iso) {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (isNaN(then)) return '';
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (s < 45) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} minute${m !== 1 ? 's' : ''} ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} hour${h !== 1 ? 's' : ''} ago`;
  const d = Math.floor(h / 24);
  if (d === 1) return 'yesterday';
  if (d < 7) return `${d} days ago`;
  if (d < 30) { const w = Math.floor(d / 7); return `${w} week${w !== 1 ? 's' : ''} ago`; }
  if (d < 365) { const mo = Math.floor(d / 30); return `${mo} month${mo !== 1 ? 's' : ''} ago`; }
  const y = Math.floor(d / 365);
  return `${y} year${y !== 1 ? 's' : ''} ago`;
}

// Format a £ value: £X.XM over a million, £XXXk over a thousand, else £X.
function vqMoney(v) {
  const n = Number(v) || 0;
  if (n >= 1e6) return `£${(n / 1e6).toFixed(1)}M`;
  if (n >= 1000) return `£${Math.round(n / 1000)}k`;
  return `£${Math.round(n)}`;
}

// Map a project status to its coloured pill.
function vqBadge(status) {
  if (status === 'completed')  return { cls: 'vd-badge-green', label: 'Completed' };
  if (status === 'processing') return { cls: 'vd-badge-amber', label: 'Processing' };
  return { cls: 'vd-badge-grey', label: 'Preparing' };
}

// Flat-circle stat-card icons (20px white line art on a solid colour fill).
const VQ_STAT_ICONS = {
  folder: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  ),
  doc: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" />
    </svg>
  ),
  check: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 11 12 14 22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  ),
  pound: <span style={{ fontSize: '18px', fontWeight: 700, lineHeight: 1 }}>£</span>,
};

// Animate a number from 0 to target with an ease-out curve. Skipped entirely for
// reduced-motion users (value snaps to target).
function useCountUp(target, duration = 900) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    const n = Number(target) || 0;
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { setVal(n); return; }
    let raf;
    const t0 = performance.now();
    const tick = now => {
      const p = Math.min(1, (now - t0) / duration);
      setVal(n * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return val;
}

// Fetch + cache the signed-in user's project list. Shared by Dashboard, Projects,
// Reports, Exports and History so they all read the same real data.
function useProjects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading]   = useState(true);

  const reload = async () => {
    try {
      const token = await vqToken();
      const res = await fetch(`${VQ_API}/projects`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) throw new Error('request failed');
      const data = await res.json();
      setProjects(Array.isArray(data) ? data : []);
    } catch {
      setProjects([]);   // on failure show empty state — never fabricate data
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); }, []);
  return { projects, loading, reload };
}

// Derive a chronological activity feed from real project rows — one event per
// project creation, plus a completion event for projects with a generated BoQ.
function vqProjectEvents(projects) {
  const events = [];
  projects.forEach(p => {
    events.push({
      key: `${p.id}-created`, kind: 'created', at: p.created_at,
      title: 'Project created', sub: p.name || 'Untitled project', projectId: p.id,
    });
    if (p.status === 'completed') {
      events.push({
        key: `${p.id}-boq`, kind: 'completed', at: p.created_at,
        title: 'BoQ generated', sub: p.name || 'Untitled project', projectId: p.id,
      });
    }
  });
  return events.sort((a, b) => new Date(b.at) - new Date(a.at));
}

// Download a server-generated file (PDF / Excel) for a project's BoQ data.
async function vqExportBoq(boqData, kind, toast) {
  const route = kind === 'excel' ? '/export-excel' : '/download';
  const fname = kind === 'excel' ? 'bill-of-quantities.xlsx' : 'bill-of-quantities.pdf';
  const token = await vqToken();
  const res = await fetch(`${VQ_API}${route}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify(boqData),
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Export failed');
  }
  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = fname;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Animated stat value — counts up from zero on mount.
function VDStatValue({ value, money }) {
  const v = useCountUp(value);
  return <div className="vd-stat-value">{money ? vqMoney(v) : Math.round(v)}</div>;
}

function DashboardPage({ go, toast, user, onBoqReady }) {
  const { projects, loading, reload } = useProjects();
  const [openMenu, setOpenMenu] = useState(null);   // id of the row whose ⋯ menu is open
  const [chartsIn, setChartsIn] = useState(false);  // triggers chart entrance transitions
  const importRef = useRef(null);

  const [healthStatus, setHealthStatus] = useState(null); // null = checking

  useEffect(() => {
    const t = setTimeout(() => setChartsIn(true), 180);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const fetchHealth = async () => {
      try {
        const token = await vqToken();
        const res = await fetch(`${VQ_API}/api/health`, {
          headers: { 'Authorization': `Bearer ${token}` },
          credentials: 'include',
        });
        if (!res.ok) throw new Error('health fetch failed');
        const data = await res.json();
        if (!cancelled) setHealthStatus({ ok: true, ...data });
      } catch {
        if (!cancelled) setHealthStatus({ ok: false });
      }
    };
    fetchHealth();
    const id = setInterval(fetchHealth, 60_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Close the row menu on any outside click.
  useEffect(() => {
    if (openMenu === null) return;
    const close = () => setOpenMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [openMenu]);

  // ── Row actions ──────────────────────────────────────────────────────────────
  const handleViewBoq = async (p) => {
    setOpenMenu(null);
    // The list endpoint omits boq_data — fetch the full project row for the real BoQ.
    try {
      const token = await vqToken();
      const res = await fetch(`${VQ_API}/projects/${p.id}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });
      const data = res.ok ? await res.json() : null;
      if (onBoqReady) onBoqReady(data?.boq_data || null);
    } catch {
      if (onBoqReady) onBoqReady(null);
    }
    go('results', { projectId: p.id });
  };

  const handleDelete = async (id) => {
    setOpenMenu(null);
    try {
      const token = await vqToken();
      const res = await fetch(`${VQ_API}/projects/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });
      if (res.ok || res.status === 204) {
        toast('Project deleted.', 'success');
        reload();
      } else {
        toast('Could not delete project. Please try again.', 'error');
      }
    } catch (err) {
      toast('Network error — could not delete project.', 'error');
    }
  };

  // ── Quick actions ────────────────────────────────────────────────────────────
  // Demo project: ResultsPage renders its built-in sample BoQ in sample mode.
  const handleDemo = () => {
    if (onBoqReady) onBoqReady(null);
    go('results', { sample: true });
  };

  // Import an existing BoQ from a JSON export and open it in the results view.
  const handleImportFile = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        if (!normaliseBoq(data).length) {
          toast('No BoQ line items found in that file.', 'error');
          return;
        }
        if (onBoqReady) onBoqReady(data);
        toast('BoQ imported.', 'success');
        go('results');
      } catch {
        toast('Invalid file — expected a BoQ JSON export.', 'error');
      }
    };
    reader.readAsText(file);
  };

  // ── Derived figures (all client-side from the real response) ─────────────────
  const totalProjects = projects.length;
  const activeCount   = projects.filter(p => p.status !== 'completed').length;
  const totalDrawings = projects.reduce((s, p) => s + (Number(p.page_count) || 0), 0);
  const boqsGenerated = projects.filter(p => p.status === 'completed').length;
  const totalValue    = projects.reduce((s, p) => s + (Number(p.estimated_value) || 0), 0);

  const recent    = projects.slice(0, 5);
  const completed = projects.filter(p => p.status === 'completed');
  const events    = vqProjectEvents(projects);

  // Status breakdown for the donut.
  const cCompleted  = boqsGenerated;
  const cProcessing = projects.filter(p => p.status === 'processing').length;
  const cPreparing  = totalProjects - cCompleted - cProcessing;
  const statusTotal = totalProjects;

  // Welcome name — first name from the email's local part, capitalised.
  const email = user?.email || '';
  const localPart = email ? email.split('@')[0].split(/[._-]/)[0] : '';
  const welcomeName = localPart ? localPart.charAt(0).toUpperCase() + localPart.slice(1) : 'there';

  // ── Processing-volume line chart (completed BoQs per day, current month) ──────
  const now = new Date();
  const year = now.getFullYear(), month = now.getMonth();

  // Real "this month" figures for the stat-card subtitles — no canned strings.
  const isThisMonth = iso => {
    const d = new Date(iso);
    return !isNaN(d) && d.getFullYear() === year && d.getMonth() === month;
  };
  const drawingsThisMonth = projects.filter(p => isThisMonth(p.created_at))
    .reduce((s, p) => s + (Number(p.page_count) || 0), 0);
  const boqsThisMonth = completed.filter(p => isThisMonth(p.created_at)).length;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const perDay = new Array(daysInMonth + 1).fill(0);   // 1-indexed by day
  completed.forEach(p => {
    const d = new Date(p.created_at);
    if (!isNaN(d) && d.getFullYear() === year && d.getMonth() === month) perDay[d.getDate()]++;
  });
  const maxCount = Math.max(1, ...perDay.slice(1));
  const CW = 600, CH = 190, padL = 30, padR = 14, padT = 14, padB = 26;
  const plotW = CW - padL - padR, plotH = CH - padT - padB;
  const xFor = day => padL + (daysInMonth > 1 ? plotW * (day - 1) / (daysInMonth - 1) : 0);
  const yFor = c => padT + plotH - plotH * (c / maxCount);
  const pts = [];
  for (let day = 1; day <= daysInMonth; day++) pts.push({ x: xFor(day), y: yFor(perDay[day]) });
  const lineStr = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const baseY = (padT + plotH).toFixed(1);
  const areaStr = `${pts[0].x.toFixed(1)},${baseY} ${lineStr} ${pts[pts.length - 1].x.toFixed(1)},${baseY}`;
  const dayLabels = [1, 8, 15, 22, 29].filter(d => d <= daysInMonth);

  // ── Donut geometry ───────────────────────────────────────────────────────────
  const R = 62, DC = 2 * Math.PI * R;
  const segs = statusTotal > 0 ? [
    { v: cCompleted,  color: '#1ea672' },
    { v: cProcessing, color: '#f0a020' },
    { v: cPreparing,  color: '#2f6fed' },
  ].filter(s => s.v > 0) : [];
  let acc = 0;
  const pct = v => statusTotal > 0 ? Math.round(v / statusTotal * 100) : 0;

  const monthName = now.toLocaleDateString('en-GB', { month: 'short' });

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="dashboard" go={go} user={user} toast={toast} />
      <main className="app-main vd-main">
        <VQParticleField />
        {/* ── Top bar ── */}
        <div className="vd-top vd-rise">
          <div>
            <h1 className="vd-h1">Welcome back, {welcomeName}</h1>
            <p className="vd-subtitle">Create and manage a draft AI generated Bill of Quantities</p>
          </div>
          <button className="btn btn-amber btn-pill" onClick={() => go('projectsetup')}>+ New Project</button>
        </div>

        {/* ── Four stat cards ── */}
        <div className="vd-stats">
          {[
            { icon: 'folder', bg: '#d77555', label: 'Projects',        value: totalProjects, money: false,
              sub: totalProjects === 0 ? 'None yet' : `${activeCount} active` },
            { icon: 'doc',    bg: '#3b82f6', label: 'Drawings',        value: totalDrawings, money: false,
              sub: totalDrawings === 0 ? 'None uploaded' : `${drawingsThisMonth} this month` },
            { icon: 'check',  bg: '#22c55e', label: 'BOQs Generated',  value: boqsGenerated, money: false,
              sub: boqsGenerated === 0 ? 'None completed' : `${boqsThisMonth} this month` },
            { icon: 'pound',  bg: '#8b5cf6', label: 'Estimated Value', value: totalValue, money: true,
              sub: totalValue === 0 ? 'No estimates yet' : 'Across all projects' },
          ].map((c, i) => (
            <div key={i} className="vd-card vd-stat vd-rise" style={{ animationDelay: `${0.06 * (i + 1)}s` }}>
              <div className="vd-stat-ico" style={{ background: c.bg }}>{VQ_STAT_ICONS[c.icon]}</div>
              <div style={{ minWidth: 0 }}>
                <div className="vd-stat-label">{c.label}</div>
                <VDStatValue value={c.value} money={c.money} />
                <div className="vd-stat-sub">{c.sub}</div>
              </div>
            </div>
          ))}
        </div>

        {/* ── Recent projects + right rail ── */}
        <div className="vd-grid">
          {/* Left column: recent projects + hero banner */}
          <div className="vd-col">
            <div className="vd-card vd-panel vd-rise" style={{ animationDelay: '0.18s' }}>
              <div className="vd-section-hd">
                <span className="vd-section-title">Recent Projects</span>
                <span className="vd-link" onClick={() => go('projects')}>View all projects →</span>
              </div>

              {loading ? (
                <p className="vd-muted">Loading projects…</p>
              ) : recent.length === 0 ? (
                <div className="vd-empty">
                  <p className="vd-empty-p">No projects yet — upload your first drawing</p>
                  <button className="btn btn-amber btn-pill" onClick={() => go('upload')}>↑ Upload Drawing</button>
                </div>
              ) : (
                recent.map(p => {
                  const badge = vqBadge(p.status);
                  return (
                    <div key={p.id} className="vd-proj-row clickable" onClick={() => go('workspace', { projectId: p.id })}>
                      <div className="vd-thumb" />
                      <div className="vd-proj-main">
                        <div className="vd-proj-name">{p.name || 'Untitled project'}</div>
                        <div className="vd-proj-time">{vqTimeAgo(p.created_at) || 'Recently'}</div>
                      </div>
                      <div className="vd-proj-right">
                        <span className={`vd-badge ${badge.cls}`}>{badge.label}</span>
                        {p.page_count != null && (
                          <span className="vd-proj-meta">{p.page_count} page{p.page_count !== 1 ? 's' : ''}</span>
                        )}
                        {p.estimated_value != null && Number(p.estimated_value) > 0 && (
                          <span className="vd-proj-meta">{vqMoney(p.estimated_value)} estimate</span>
                        )}
                        <div style={{ position: 'relative' }}>
                          <button
                            className="vd-dots"
                            onClick={(e) => { e.stopPropagation(); setOpenMenu(openMenu === p.id ? null : p.id); }}
                          >⋯</button>
                          {openMenu === p.id && (
                            <div className="vd-menu" onClick={(e) => e.stopPropagation()}>
                              <div className="vd-menu-item" onClick={() => go('workspace', { projectId: p.id })}>Open project</div>
                              <div className="vd-menu-item" onClick={() => handleViewBoq(p)}>View BoQ</div>
                              <div className="vd-menu-item danger" onClick={() => handleDelete(p.id)}>Delete</div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Hero banner — animated wireframe skyline */}
            <div className="vd-banner vd-rise" style={{ animationDelay: '0.26s' }}>
              <svg className="vd-banner-art" viewBox="0 0 600 170" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                <defs>
                  <linearGradient id="vdScanGrad" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#D9855B" stopOpacity="0" />
                    <stop offset="50%" stopColor="#D9855B" stopOpacity="0.06" />
                    <stop offset="100%" stopColor="#D9855B" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <g fill="none" stroke="#D9855B" strokeWidth="1">
                  {/* wireframe skyline, drawn in as the panel appears */}
                  <path className="vd-draw" pathLength="1" strokeOpacity="0.16"
                    d="M0,150 L40,150 L40,96 L86,96 L86,150 L120,150 L120,70 L150,52 L180,70 L180,150 L228,150 L228,108 L270,108 L270,150" />
                  <path className="vd-draw" pathLength="1" strokeOpacity="0.16" style={{ animationDelay: '0.45s' }}
                    d="M270,150 L300,150 L300,40 L348,40 L348,150 L392,150 L392,84 L436,84 L436,150 L600,150" />
                  {/* isometric block */}
                  <path className="vd-draw" pathLength="1" strokeOpacity="0.2" style={{ animationDelay: '0.9s' }}
                    d="M470,150 L470,92 L510,72 L550,92 L550,150 M470,92 L510,112 L550,92 M510,112 L510,150" />
                  {/* floor lines */}
                  <path strokeOpacity="0.07" d="M300,60 L348,60 M300,80 L348,80 M300,100 L348,100 M300,120 L348,120" />
                  <path strokeOpacity="0.07" d="M120,90 L180,90 M120,110 L180,110 M120,130 L180,130" />
                </g>
                <rect className="vd-scan" x="0" y="0" width="220" height="170" fill="url(#vdScanGrad)" />
              </svg>
              <div className="vd-banner-inner">
                <p className="vd-banner-h">Construction Intelligence Ready</p>
                <p className="vd-banner-p">Upload a drawing to begin automated measurement and BoQ generation.</p>
                <button className="btn btn-amber btn-pill" onClick={() => go('upload')}>↑ Upload Drawing</button>
              </div>
            </div>
          </div>

          {/* Right rail */}
          <div className="vd-col">
            {/* Quick actions */}
            <div className="vd-card vd-panel vd-rise" style={{ animationDelay: '0.22s' }}>
              <div className="vd-section-hd"><span className="vd-section-title">Quick Actions</span></div>
              <div className="vd-qa">
                <button className="vd-qa-btn vd-qa-primary" onClick={() => go('upload')}>↑ Upload Drawing</button>
                <button className="vd-qa-btn vd-qa-dark" onClick={handleDemo}>View Demo Project</button>
                <button className="vd-qa-btn vd-qa-dark" onClick={() => importRef.current?.click()}>Import Existing BOQ</button>
                <button className="vd-qa-btn vd-qa-dark" onClick={() => go('projectsetup')}>＋ Create Project</button>
                <input ref={importRef} type="file" accept=".json,application/json" style={{ display: 'none' }}
                  onChange={e => { handleImportFile(e.target.files[0]); e.target.value = ''; }} />
              </div>
            </div>

            {/* Recent activity */}
            <div className="vd-card vd-panel vd-rise" style={{ animationDelay: '0.3s' }}>
              <div className="vd-section-hd">
                <span className="vd-section-title">Recent Activity</span>
                <span className="vd-link" onClick={() => go('history')}>View all activity →</span>
              </div>
              {loading ? (
                <p className="vd-muted">Loading…</p>
              ) : events.length === 0 ? (
                <p className="vd-muted">No recent activity.</p>
              ) : (
                events.slice(0, 5).map(ev => (
                  <div key={ev.key} className="vd-act">
                    <div className="vd-act-dot" style={ev.kind === 'created'
                      ? { background: 'rgba(47,111,237,0.16)', color: '#6f9bf5' } : undefined}>
                      {ev.kind === 'created' ? '+' : '✓'}
                    </div>
                    <div className="vd-act-body">
                      <div className="vd-act-title">{ev.title}</div>
                      <div className="vd-act-sub">{ev.sub}</div>
                    </div>
                    <span className="vd-act-time">{vqTimeAgo(ev.at)}</span>
                  </div>
                ))
              )}
            </div>

            {/* System status */}
            <div className="vd-card vd-panel vd-rise" style={{ animationDelay: '0.38s' }}>
              <div className="vd-section-hd"><span className="vd-section-title">System Status</span></div>
              <div className="vd-status-row">
                <span className="vd-status-label">AI Engine</span>
                {healthStatus === null ? (
                  <span className="vd-status-val" style={{ color: '#8b92a0' }}>Checking…</span>
                ) : healthStatus.ok && healthStatus.ai_engine === 'online' ? (
                  <span className="vd-status-online"><span className="vd-dot-green" /> Online</span>
                ) : (
                  <span className="vd-status-offline"><span className="vd-dot-red" /> Offline</span>
                )}
              </div>
              <div className="vd-status-row">
                <span className="vd-status-label">NRM2 Database</span>
                <span className="vd-status-val">
                  {healthStatus === null ? (
                    <span style={{ color: '#8b92a0' }}>Checking…</span>
                  ) : healthStatus.ok ? 'Loaded' : '—'}
                </span>
              </div>
              <div className="vd-status-row">
                <span className="vd-status-label">Average Processing Time</span>
                <span className="vd-status-val">
                  {healthStatus === null ? (
                    <span style={{ color: '#8b92a0' }}>Checking…</span>
                  ) : healthStatus.ok && healthStatus.avg_processing_seconds != null
                    ? `${healthStatus.avg_processing_seconds}s`
                    : '—'}
                </span>
              </div>
              <div className="vd-status-row">
                <span className="vd-status-label">System Uptime</span>
                <span className="vd-status-val">
                  {healthStatus === null ? (
                    <span style={{ color: '#8b92a0' }}>Checking…</span>
                  ) : healthStatus.ok && healthStatus.uptime_seconds != null
                    ? `${Math.floor(healthStatus.uptime_seconds / 3600)}h ${Math.floor((healthStatus.uptime_seconds % 3600) / 60)}m`
                    : '—'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Charts row ── */}
        <div className="vd-charts">
          {/* Processing volume */}
          <div className="vd-card vd-panel vd-rise" style={{ animationDelay: '0.34s' }}>
            <div className="vd-section-hd">
              <span className="vd-section-title">Processing Volume <span style={{ fontSize: '13px', color: '#8b92a0', fontWeight: 400 }}>(This Month)</span></span>
              <span className="vd-chart-pill">{boqsThisMonth} BoQ{boqsThisMonth !== 1 ? 's' : ''} this month</span>
            </div>
            <svg viewBox={`0 0 ${CW} ${CH}`} width="100%" style={{ display: 'block', height: 'auto' }}>
              <defs>
                <linearGradient id="vdAreaFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#d77555" stopOpacity="0.28" />
                  <stop offset="100%" stopColor="#d77555" stopOpacity="0" />
                </linearGradient>
              </defs>
              {/* horizontal gridlines + y labels (0 and max) */}
              {[0, 0.5, 1].map((f, i) => {
                const y = padT + plotH - plotH * f;
                return <line key={i} x1={padL} y1={y} x2={CW - padR} y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />;
              })}
              <text x={padL - 8} y={padT + 4} fill="#6b7280" fontSize="11" textAnchor="end">{maxCount}</text>
              <text x={padL - 8} y={padT + plotH + 4} fill="#6b7280" fontSize="11" textAnchor="end">0</text>
              {/* area + line — line draws itself in, area fades up behind it */}
              <polygon points={areaStr} fill="url(#vdAreaFill)"
                style={{ opacity: chartsIn ? 1 : 0, transition: 'opacity 1.2s ease 0.5s' }} />
              <polyline className="vd-draw" pathLength="1" points={lineStr} fill="none"
                stroke="#d77555" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
              {/* x labels */}
              {dayLabels.map(d => (
                <text key={d} x={xFor(d)} y={CH - 6} fill="#6b7280" fontSize="11" textAnchor="middle">{d} {monthName}</text>
              ))}
            </svg>
          </div>

          {/* Projects by status donut */}
          <div className="vd-card vd-panel vd-rise" style={{ animationDelay: '0.4s' }}>
            <div className="vd-section-hd"><span className="vd-section-title">Projects by Status</span></div>
            <div className="vd-donut-wrap">
              <div className="vd-donut">
                <svg viewBox="0 0 150 150" width="150" height="150">
                  <circle cx="75" cy="75" r={R} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="16" />
                  {segs.map((s, i) => {
                    const len = DC * (s.v / statusTotal);
                    const el = (
                      <circle key={i} cx="75" cy="75" r={R} fill="none" stroke={s.color} strokeWidth="16"
                        strokeDasharray={chartsIn ? `${len.toFixed(2)} ${(DC - len).toFixed(2)}` : `0 ${DC.toFixed(2)}`}
                        strokeDashoffset={(-acc).toFixed(2)}
                        style={{ transition: `stroke-dasharray 0.9s cubic-bezier(0.22,1,0.36,1) ${0.3 + i * 0.15}s` }}
                        transform="rotate(-90 75 75)" />
                    );
                    acc += len;
                    return el;
                  })}
                </svg>
                <div className="vd-donut-center">
                  <span className="vd-donut-total">{statusTotal}</span>
                  <span className="vd-donut-lbl">Total</span>
                </div>
              </div>
              <div className="vd-legend">
                {[
                  { name: 'Completed',   v: cCompleted,  color: '#1ea672' },
                  { name: 'In Progress', v: cProcessing, color: '#f0a020' },
                  { name: 'Preparing',   v: cPreparing,  color: '#2f6fed' },
                ].map((l, i) => (
                  <div key={i} className="vd-legend-row">
                    <span className="vd-legend-dot" style={{ background: l.color }} />
                    <span className="vd-legend-name">{l.name}</span>
                    <span className="vd-legend-val">{l.v} ({pct(l.v)}%)</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

// ─── PROJECTS ──────────────────────────────────────────────────────────────────────
// Full project list — every project is viewable and selectable from here.
// Normalise a raw status into the three buckets the UI shows.
function vqStatusKey(status) {
  if (status === 'completed')  return 'completed';
  if (status === 'processing') return 'processing';
  return 'preparing';
}

function ProjectsPage({ go, toast, onBoqReady }) {
  const { projects, loading, reload } = useProjects();
  const [openMenu, setOpenMenu] = useState(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('newest');
  const [duplicating, setDuplicating] = useState(null);
  const searchRef = React.useRef(null);

  useEffect(() => {
    if (openMenu === null) return;
    const close = () => setOpenMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [openMenu]);

  // Press "/" anywhere on the page to jump to search.
  useEffect(() => {
    const onKey = (e) => {
      const tag = document.activeElement?.tagName || '';
      if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(tag)) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const handleViewBoq = async (p) => {
    setOpenMenu(null);
    try {
      const token = await vqToken();
      const res = await fetch(`${VQ_API}/projects/${p.id}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });
      const data = res.ok ? await res.json() : null;
      if (onBoqReady) onBoqReady(data?.boq_data || null);
    } catch {
      if (onBoqReady) onBoqReady(null);
    }
    go('results', { projectId: p.id });
  };

  const handleDelete = async (p) => {
    setOpenMenu(null);
    if (!window.confirm(`Delete "${p.name || 'Untitled project'}"? This permanently removes its drawings, BoQ and chat history.`)) return;
    try {
      const token = await vqToken();
      const res = await fetch(`${VQ_API}/projects/${p.id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });
      if (res.ok || res.status === 204) { toast('Project deleted.', 'success'); reload(); }
      else toast('Could not delete project. Please try again.', 'error');
    } catch {
      toast('Network error — could not delete project.', 'error');
    }
  };

  // Duplicate a project's setup (client, contract, AI instructions…) as a fresh
  // draft — handy for repeat clients or phased works on the same site.
  const handleDuplicate = async (p) => {
    setOpenMenu(null);
    setDuplicating(p.id);
    try {
      const token = await vqToken();
      // The list payload can omit setup fields, so fetch the full row first.
      const fullRes = await fetch(`${VQ_API}/projects/${p.id}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });
      const full = fullRes.ok ? await fullRes.json() : p;
      const res = await fetch(`${VQ_API}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        credentials: 'include',
        body: JSON.stringify({
          name: `${full.name || 'Untitled project'} (copy)`,
          description: full.description,
          client_name: full.client_name,
          contract_type: full.contract_type,
          location_factor: full.location_factor,
          notes_for_ai: full.notes_for_ai,
          auto_delete_days: full.auto_delete_days,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || 'Could not duplicate project.');
      }
      toast('Project duplicated.', 'success');
      reload();
    } catch (e) {
      toast(e.message || 'Could not duplicate project.', 'error');
    } finally {
      setDuplicating(null);
    }
  };

  // Search, status filter and sort applied client-side over the loaded list.
  const q = query.trim().toLowerCase();
  const counts = { all: projects.length, preparing: 0, processing: 0, completed: 0 };
  projects.forEach(p => { counts[vqStatusKey(p.status)] += 1; });
  const visible = projects
    .filter(p => statusFilter === 'all' || vqStatusKey(p.status) === statusFilter)
    .filter(p => !q
      || (p.name || '').toLowerCase().includes(q)
      || (p.client_name || '').toLowerCase().includes(q))
    .sort((a, b) => {
      if (sortBy === 'oldest') return new Date(a.created_at || 0) - new Date(b.created_at || 0);
      if (sortBy === 'name')   return (a.name || '').localeCompare(b.name || '');
      if (sortBy === 'value')  return (Number(b.estimated_value) || 0) - (Number(a.estimated_value) || 0);
      return new Date(b.created_at || 0) - new Date(a.created_at || 0);   // newest
    });

  const FILTERS = [
    { key: 'all',        label: 'All' },
    { key: 'preparing',  label: 'Preparing' },
    { key: 'processing', label: 'Processing' },
    { key: 'completed',  label: 'Completed' },
  ];

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="projects" go={go} toast={toast} />
      <main className="app-main vd-main">
        <VQParticleField />
        <div className="vd-top vd-rise">
          <div>
            <h1 className="vd-h1">Projects</h1>
            <p className="vd-subtitle">
              {loading ? 'Loading…'
                : projects.length === 0 ? 'No projects yet'
                : `${projects.length} project${projects.length !== 1 ? 's' : ''}`}
            </p>
          </div>
          <button className="btn btn-amber btn-pill" onClick={() => go('projectsetup')}>+ New Project</button>
        </div>

        {!loading && projects.length > 0 && (
          <div className="vd-toolbar vd-rise" style={{ animationDelay: '0.05s' }}>
            <div className="vd-search">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.5" y2="16.5" />
              </svg>
              <input ref={searchRef} value={query} placeholder="Search by project or client…"
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => { if (e.key === 'Escape') { setQuery(''); e.target.blur(); } }} />
              <kbd>/</kbd>
            </div>
            {FILTERS.map(f => (
              <button key={f.key} className={`vd-chip${statusFilter === f.key ? ' active' : ''}`}
                onClick={() => setStatusFilter(f.key)}>
                {f.label}<span className="n">{counts[f.key]}</span>
              </button>
            ))}
            <select className="vd-sort" value={sortBy} onChange={e => setSortBy(e.target.value)} title="Sort projects">
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="name">Name A–Z</option>
              <option value="value">Highest estimate</option>
            </select>
          </div>
        )}

        <div className="vd-card vd-rise" style={{ animationDelay: '0.1s' }}>
          {loading ? (
            <p className="vd-muted" style={{ padding: '18px' }}>Loading projects…</p>
          ) : projects.length === 0 ? (
            <div className="vd-empty">
              <p className="vd-empty-p">No projects yet — create your first project to get started.</p>
              <button className="btn btn-amber btn-pill" onClick={() => go('projectsetup')}>＋ Create Project</button>
            </div>
          ) : visible.length === 0 ? (
            <div className="vd-empty">
              <p className="vd-empty-p">No projects match your search.</p>
              <button className="btn btn-outline btn-pill btn-sm" onClick={() => { setQuery(''); setStatusFilter('all'); }}>Clear filters</button>
            </div>
          ) : (
            visible.map(p => {
              const badge = vqBadge(p.status);
              return (
                <div key={p.id} className="vq-list-row clickable" onClick={() => go('workspace', { projectId: p.id })}>
                  <div className="vd-thumb" />
                  <div className="vd-proj-main">
                    <div className="vd-proj-name">{p.name || 'Untitled project'}</div>
                    <div className="vd-proj-time">
                      {p.client_name ? `${p.client_name} · ` : ''}{vqTimeAgo(p.created_at) || 'Recently'}
                    </div>
                  </div>
                  <div className="vd-proj-right">
                    <span className={`vd-badge ${badge.cls}`}>{badge.label}</span>
                    {p.page_count != null && (
                      <span className="vd-proj-meta">{p.page_count} page{p.page_count !== 1 ? 's' : ''}</span>
                    )}
                    {p.estimated_value != null && Number(p.estimated_value) > 0 && (
                      <span className="vd-proj-meta">{vqMoney(p.estimated_value)} estimate</span>
                    )}
                    <div style={{ position: 'relative' }}>
                      <button className="vd-dots"
                        onClick={(e) => { e.stopPropagation(); setOpenMenu(openMenu === p.id ? null : p.id); }}>⋯</button>
                      {openMenu === p.id && (
                        <div className="vd-menu" onClick={(e) => e.stopPropagation()}>
                          <div className="vd-menu-item" onClick={() => go('workspace', { projectId: p.id })}>Open project</div>
                          <div className="vd-menu-item" onClick={() => handleViewBoq(p)}>View BoQ</div>
                          <div className="vd-menu-item" onClick={() => handleDuplicate(p)}>
                            {duplicating === p.id ? 'Duplicating…' : 'Duplicate'}
                          </div>
                          <div className="vd-menu-item" onClick={() => go('projectsettings', { projectId: p.id })}>Settings</div>
                          <div className="vd-menu-item danger" onClick={() => handleDelete(p)}>Delete</div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </main>
    </div>
  );
}

// ─── REPORTS ───────────────────────────────────────────────────────────────────────
// Portfolio summary computed entirely from the user's real project data.
function ReportsPage({ go, toast }) {
  const { projects, loading } = useProjects();
  const [barsIn, setBarsIn] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setBarsIn(true), 250);
    return () => clearTimeout(t);
  }, []);

  const total      = projects.length;
  const completed  = projects.filter(p => p.status === 'completed').length;
  const processing = projects.filter(p => p.status === 'processing').length;
  const preparing  = total - completed - processing;
  const totalValue = projects.reduce((s, p) => s + (Number(p.estimated_value) || 0), 0);
  const valued     = projects.filter(p => Number(p.estimated_value) > 0);
  const avgValue   = valued.length ? totalValue / valued.length : 0;

  const rows = [
    { name: 'Completed',   v: completed,  color: '#1ea672' },
    { name: 'In Progress', v: processing, color: '#f0a020' },
    { name: 'Preparing',   v: preparing,  color: '#2f6fed' },
  ];

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="reports" go={go} toast={toast} />
      <main className="app-main vd-main">
        <VQParticleField />
        <div className="vd-top vd-rise">
          <div>
            <h1 className="vd-h1">Reports</h1>
            <p className="vd-subtitle">Portfolio summary across all your projects</p>
          </div>
        </div>

        <div className="vd-stats">
          {[
            { icon: 'folder', bg: '#d77555', label: 'Total Projects',  value: total, money: false,
              sub: total === 0 ? 'None yet' : 'All time' },
            { icon: 'check',  bg: '#22c55e', label: 'Completed BoQs',  value: completed, money: false,
              sub: completed === 0 ? 'None completed' : `${Math.round(completed / Math.max(1, total) * 100)}% of projects` },
            { icon: 'pound',  bg: '#8b5cf6', label: 'Total Estimated', value: totalValue, money: true,
              sub: totalValue === 0 ? 'No estimates yet' : 'Across all projects' },
            { icon: 'doc',    bg: '#3b82f6', label: 'Average Estimate', value: avgValue, money: true,
              sub: valued.length === 0 ? 'No priced projects yet' : `Across ${valued.length} priced project${valued.length !== 1 ? 's' : ''}` },
          ].map((c, i) => (
            <div key={i} className="vd-card vd-stat vd-rise" style={{ animationDelay: `${0.06 * (i + 1)}s` }}>
              <div className="vd-stat-ico" style={{ background: c.bg }}>{VQ_STAT_ICONS[c.icon]}</div>
              <div style={{ minWidth: 0 }}>
                <div className="vd-stat-label">{c.label}</div>
                <VDStatValue value={c.value} money={c.money} />
                <div className="vd-stat-sub">{c.sub}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="vd-card vd-panel vd-rise" style={{ animationDelay: '0.24s', marginBottom: '24px' }}>
          <div className="vd-section-hd"><span className="vd-section-title">Status Breakdown</span></div>
          {loading ? (
            <p className="vd-muted">Loading…</p>
          ) : total === 0 ? (
            <p className="vd-muted">No projects to report on yet.</p>
          ) : (
            rows.map((r, i) => (
              <div key={r.name} style={{ display: 'flex', alignItems: 'center', gap: '14px', padding: '9px 0' }}>
                <span style={{ width: '92px', fontSize: '13px', color: 'rgba(255,255,255,0.78)', flexShrink: 0 }}>{r.name}</span>
                <div className="vq-bar-track">
                  <div className="vq-bar-fill" style={{
                    background: r.color,
                    width: barsIn ? `${(r.v / total) * 100}%` : 0,
                    transitionDelay: `${i * 0.12}s`,
                  }} />
                </div>
                <span style={{ width: '70px', textAlign: 'right', fontSize: '13px', color: '#8b92a0', flexShrink: 0 }}>
                  {r.v} ({Math.round(r.v / total * 100)}%)
                </span>
              </div>
            ))
          )}
        </div>

        <div className="vd-card vd-panel vd-rise" style={{ animationDelay: '0.32s' }}>
          <div className="vd-section-hd"><span className="vd-section-title">Project Values</span></div>
          {loading ? (
            <p className="vd-muted">Loading…</p>
          ) : valued.length === 0 ? (
            <p className="vd-muted">No priced projects yet — generate a BoQ to see estimated values here.</p>
          ) : (
            valued.map(p => {
              const maxVal = Math.max(...valued.map(x => Number(x.estimated_value) || 0), 1);
              return (
                <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: '14px', padding: '9px 0' }}>
                  <span style={{ width: '180px', fontSize: '13px', color: 'rgba(255,255,255,0.78)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flexShrink: 0 }}>
                    {p.name || 'Untitled project'}
                  </span>
                  <div className="vq-bar-track">
                    <div className="vq-bar-fill" style={{
                      background: '#d77555',
                      width: barsIn ? `${(Number(p.estimated_value) / maxVal) * 100}%` : 0,
                    }} />
                  </div>
                  <span style={{ width: '80px', textAlign: 'right', fontSize: '13px', color: '#8b92a0', flexShrink: 0 }}>
                    {vqMoney(p.estimated_value)}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </main>
    </div>
  );
}

// ─── EXPORTS ───────────────────────────────────────────────────────────────────────
// Download any completed BoQ as PDF or Excel via the existing export endpoints.
function ExportsPage({ go, toast }) {
  const { projects, loading } = useProjects();
  const [busy, setBusy] = useState(null);   // `${projectId}-${kind}` while generating

  const completed = projects.filter(p => p.status === 'completed');

  const handleExport = async (p, kind) => {
    const key = `${p.id}-${kind}`;
    if (busy) return;
    setBusy(key);
    toast(`Generating ${kind === 'excel' ? 'Excel' : 'PDF'}…`, 'info');
    try {
      const token = await vqToken();
      const res = await fetch(`${VQ_API}/projects/${p.id}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Could not load project BoQ.');
      const data = await res.json();
      if (!data.boq_data) throw new Error('This project has no BoQ data yet.');
      await vqExportBoq(data.boq_data, kind, toast);
      toast(`${kind === 'excel' ? 'Excel' : 'PDF'} downloaded.`, 'success');
    } catch (e) {
      toast(e.message || 'Export failed — please try again.', 'error');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="exports" go={go} toast={toast} />
      <main className="app-main vd-main">
        <VQParticleField />
        <div className="vd-top vd-rise">
          <div>
            <h1 className="vd-h1">Exports</h1>
            <p className="vd-subtitle">Download completed BoQs as PDF or Excel</p>
          </div>
        </div>

        <div className="vd-card vd-rise" style={{ animationDelay: '0.1s' }}>
          {loading ? (
            <p className="vd-muted" style={{ padding: '18px' }}>Loading…</p>
          ) : completed.length === 0 ? (
            <div className="vd-empty">
              <p className="vd-empty-p">No completed BoQs to export yet — upload a drawing to generate one.</p>
              <button className="btn btn-amber btn-pill" onClick={() => go('upload')}>↑ Upload Drawing</button>
            </div>
          ) : (
            completed.map(p => (
              <div key={p.id} className="vq-list-row">
                <div className="vd-thumb" />
                <div className="vd-proj-main">
                  <div className="vd-proj-name">{p.name || 'Untitled project'}</div>
                  <div className="vd-proj-time">
                    {vqTimeAgo(p.created_at)}
                    {Number(p.estimated_value) > 0 && ` · ${vqMoney(p.estimated_value)} estimate`}
                  </div>
                </div>
                <div className="vd-proj-right">
                  <button className="btn btn-outline btn-pill btn-sm"
                    style={{ borderColor: 'rgba(255,255,255,0.18)', color: 'rgba(255,255,255,0.75)' }}
                    disabled={busy !== null}
                    onClick={() => handleExport(p, 'pdf')}>
                    {busy === `${p.id}-pdf` ? 'Generating…' : '↓ PDF'}
                  </button>
                  <button className="btn btn-outline btn-pill btn-sm"
                    style={{ borderColor: 'rgba(255,255,255,0.18)', color: 'rgba(255,255,255,0.75)' }}
                    disabled={busy !== null}
                    onClick={() => handleExport(p, 'excel')}>
                    {busy === `${p.id}-excel` ? 'Generating…' : '↓ Excel'}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}

// ─── HISTORY ───────────────────────────────────────────────────────────────────────
// Chronological activity timeline derived from real project data.
function HistoryPage({ go, toast }) {
  const { projects, loading } = useProjects();
  const events = vqProjectEvents(projects);

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="history" go={go} toast={toast} />
      <main className="app-main vd-main">
        <VQParticleField />
        <div className="vd-top vd-rise">
          <div>
            <h1 className="vd-h1">History</h1>
            <p className="vd-subtitle">
              {loading ? 'Loading…'
                : events.length === 0 ? 'No activity yet'
                : `${events.length} event${events.length !== 1 ? 's' : ''}`}
            </p>
          </div>
        </div>

        <div className="vd-card vd-panel vd-rise" style={{ animationDelay: '0.1s' }}>
          {loading ? (
            <p className="vd-muted">Loading…</p>
          ) : events.length === 0 ? (
            <p className="vd-muted">No activity yet — your project events will appear here.</p>
          ) : (
            <div className="vq-timeline">
              {events.map((ev, i) => (
                <div key={ev.key} className="vq-tl-item vd-rise" style={{ animationDelay: `${Math.min(i * 0.05, 0.6)}s` }}>
                  <span className="vq-tl-dot" style={{ background: ev.kind === 'completed' ? '#2bd496' : '#6f9bf5' }} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'baseline' }}>
                    <div>
                      <div className="vd-act-title">{ev.title}</div>
                      <div className="vd-act-sub" style={{ cursor: 'pointer' }}
                        onClick={() => go('workspace', { projectId: ev.projectId })}>
                        {ev.sub} →
                      </div>
                    </div>
                    <span className="vd-act-time">{vqTimeAgo(ev.at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// ─── UPLOAD ─────────────────────────────────────────────────────────────────────────
// onBoqReady is a callback that stores the Claude JSON in App-level state so
// ResultsPage can read it — equivalent to raising a C# event to a parent component
function UploadPage({ go, toast, onBoqReady }) {
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('idle');

  // processFile accepts the real File object (not just its name)
  // It is declared async so we can use await inside — like an async Task method in C#
  const processFile = async file => {
    setFileName(file.name);         // display the filename immediately in the UI
    setStatus('uploading');         // switch the progress bar to the uploading state
    setProgress(0);                 // reset progress to 0

    // Animate the bar to ~90% while the fetch is in flight so the user sees activity.
    // We cap at 90 so there is always a visible jump to 100 when the response arrives.
    let p = 0;
    const iv = setInterval(() => {
      p = Math.min(p + Math.random() * 8 + 4, 90);   // increment randomly, never exceed 90
      setProgress(p);
    }, 300);

    // Abort the request if the backend hangs past VQ_UPLOAD_TIMEOUT_MS so the user
    // gets a clear message instead of a fake progress bar that never completes.
    const timer = vqAbortTimer();
    try {
      // FormData is the browser's equivalent of a multipart/form-data body — like
      // MultipartFormDataContent in C# HttpClient
      const formData = new FormData();
      formData.append('file', file);   // 'file' must match the field name in Flask's request.files["file"]

      const { data: { session: vqSession } } = window.VQAuth
        ? await window.VQAuth.getSession()
        : { data: { session: null } };
      const token = vqSession?.access_token || '';

      // fetch() sends the HTTP request and returns a Promise — like HttpClient.PostAsync in C#.
      // No Content-Type header needed; the browser sets multipart/form-data + boundary automatically.
      // Use the shared VQ_API base URL (was a hardcoded literal, which risked drifting
      // from the other upload blocks). signal wires up the abort timer above.
      const res = await fetch(`${VQ_API}/process`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
        credentials: 'include',
        signal: timer.signal,
      });
      timer.clear();       // response arrived — cancel the abort timer
      clearInterval(iv);   // stop the fake progress animation now that the server has responded

      if (!res.ok) {
        // A clean 401 means the session expired (or the token was rejected) — send
        // the user to sign-in rather than showing a confusing "upload failed" toast.
        if (res.status === 401) {
          toast('Your session expired. Please sign in again.', 'error');
          setStatus('idle'); setFileName(null); setProgress(0);
          setTimeout(() => go('signin'), 1200);
          return;
        }
        // Try to read a JSON error body from Flask, fall back to the HTTP status text
        const err = await res.json().catch(() => ({ error: res.statusText }));
        const msg = err.error || 'Upload failed. Please try again.';
        if (res.status === 429 || res.status === 403) {
          toast(msg + ' See Pricing to upgrade.', 'error');
          // Navigate to pricing after a short delay so the user reads the message
          setTimeout(() => go('pricing'), 3500);
        } else {
          toast(msg, 'error');
        }
        setStatus('idle');     // reset the UI so the user can try again
        setFileName(null);
        setProgress(0);
        return;   // early return — like 'return' after a guard clause in C#
      }

      // res.json() parses the JSON response body — like JsonSerializer.Deserialize in C#
      const data = await res.json();

      setProgress(100);           // snap the bar to 100% to signal completion
      setStatus('processing');    // show the "AI reading" message briefly
      onBoqReady(data);           // store the BoQ JSON in App-level state for ResultsPage

      // Brief pause for visual satisfaction, then navigate to the results page
      setTimeout(() => { setStatus('done'); setTimeout(() => go('results'), 700); }, 1200);

    } catch (err) {
      // fetch() only REJECTS on an abort (AbortError) or a true network/CORS failure
      // (TypeError); HTTP 4xx/5xx are handled by the !res.ok check above. Log the real
      // error object so this is diagnosable from the browser console without Railway logs.
      timer.clear();
      clearInterval(iv);
      console.error('[VQ] /process upload failed:', err);
      toast(vqUploadErrorMessage(err), 'error');
      setStatus('idle');
      setFileName(null);
      setProgress(0);
    }
  };

  const statusMsg = { uploading: 'Uploading drawing…', processing: 'AI reading your drawing…', done: '✓ Ready! Opening your BoQ…' };
  const barColor = status === 'done' ? 'var(--green)' : status === 'processing' ? 'var(--amber)' : 'var(--blue)';

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="upload" go={go} toast={toast} />
      <div className="app-main upload-page">
        <VQParticleField />
        <div className="upload-wrap">
          <div style={{ textAlign: 'center', marginBottom: '40px', paddingTop: '40px' }}>
            <h2 className="display-md" style={{ marginBottom: '8px', color: 'white' }}>Upload a drawing</h2>
            <p style={{ color: 'rgba(255,255,255,0.42)', fontSize: '15px' }}>PDF, single or multi-page. Raster or vector. Up to 50 MB.</p>
          </div>
          <div
            className={`upload-zone${dragOver ? ' drag' : ''}`}
            onDrop={e => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files[0]) processFile(e.dataTransfer.files[0]); }}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onClick={() => document.getElementById('vq-file-input').click()}
          >
            <p className="upload-icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{color:'var(--c-300)'}}><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg></p>
            <p className="upload-icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{color:'var(--c-300)'}}><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg></p>
            <p className="upload-h">Drop your drawing here</p>
            <p className="upload-sub">or click to select a file</p>
            {status === 'idle' && (
              <button className="btn btn-outline btn-pill" onClick={e => { e.stopPropagation(); document.getElementById('vq-file-input').click(); }}>
                Select PDF
              </button>
            )}
            <input id="vq-file-input" type="file" accept=".pdf" style={{ display: 'none' }}
              onChange={e => { if (e.target.files[0]) processFile(e.target.files[0]); }} />
          </div>
          {fileName && (
            <div className="upload-status">
              <p style={{ fontWeight: 600, fontSize: '14px', color: 'white', marginBottom: '6px' }}>{fileName}</p>
              <p style={{ fontSize: '13px', color: status === 'done' ? 'var(--green)' : 'rgba(255,255,255,0.5)', marginBottom: '12px' }}>{statusMsg[status]}</p>
              <div className="upload-track">
                <div className="upload-bar" style={{ width: `${progress}%`, background: barColor }} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── SETTINGS ───────────────────────────────────────────────────────────────────────
const VQ_RATE_TRADES = [
  ['Brickwork (stretcher bond)', '£0.65/No'],
  ['Blockwork (common)', '£0.45/No'],
  ['Clay tile roof covering', '£38.50/m²'],
  ['Internal plaster', '£7.50/m²'],
  ['Emulsion paint (2 coats)', '£2.10/m²'],
];
const VQ_REGIONS = ['North West England','London','South East','Yorkshire','East Midlands','West Midlands','Scotland','Wales','Northern Ireland'];

function SettingsPage({ go, toast, user: userProp }) {
  const [tab, setTab] = useState('account');
  const [user, setUser] = useState(userProp || null);

  // Resolve the session user when the prop isn't supplied.
  useEffect(() => {
    if (userProp) { setUser(userProp); return; }
    let active = true;
    if (window.VQAuth) {
      window.VQAuth.getSession()
        .then(({ data }) => { if (active && data && data.session) setUser(data.session.user); })
        .catch(() => {});
    }
    return () => { active = false; };
  }, [userProp]);

  const meta = user?.user_metadata || {};

  // ── Account — initialised from the real signed-in user, saved to Supabase ──────
  const [acct, setAcct] = useState({ first: '', last: '', email: '', phone: '' });
  const [acctSaving, setAcctSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    const m = user.user_metadata || {};
    const parts = (m.full_name || '').trim().split(/\s+/).filter(Boolean);
    setAcct({
      first: m.first_name || parts[0] || '',
      last:  m.last_name  || parts.slice(1).join(' ') || '',
      email: user.email || '',
      phone: m.phone || '',
    });
  }, [user]);

  const setA = (k, v) => setAcct(f => ({ ...f, [k]: v }));

  const saveAccount = async () => {
    if (!window.VQAuth || !user) { toast('You need to be signed in.', 'error'); return; }
    if (!acct.first.trim()) { toast('First name is required.', 'error'); return; }
    setAcctSaving(true);
    try {
      const fullName = `${acct.first.trim()} ${acct.last.trim()}`.trim();
      const { error } = await window.VQAuth.updateUserMeta({
        first_name: acct.first.trim(),
        last_name:  acct.last.trim(),
        full_name:  fullName,
        phone:      acct.phone.trim(),
      });
      if (error) throw error;
      // Mirror to the profiles table — best-effort, the metadata is canonical.
      try { await window.VQAuth.updateProfile(user.id, { full_name: fullName }); } catch (e) {}

      const newEmail = acct.email.trim();
      if (newEmail && newEmail.toLowerCase() !== (user.email || '').toLowerCase()) {
        const { error: emailErr } = await window.VQAuth.updateEmail(newEmail);
        if (emailErr) throw emailErr;
        toast('Profile saved — check your new email for a confirmation link.', 'success');
      } else {
        toast('Profile saved.', 'success');
      }
    } catch (e) {
      toast(e.message || 'Could not save profile.', 'error');
    } finally {
      setAcctSaving(false);
    }
  };

  // ── Password change — verifies the current password before updating ────────────
  const [pw, setPw] = useState({ current: '', next: '' });
  const [pwSaving, setPwSaving] = useState(false);

  const changePassword = async () => {
    if (!window.VQAuth || !user) { toast('You need to be signed in.', 'error'); return; }
    if (!pw.current) { toast('Enter your current password.', 'error'); return; }
    if (pw.next.length < 8) { toast('New password must be at least 8 characters.', 'error'); return; }
    setPwSaving(true);
    try {
      const { error: authErr } = await window.VQAuth.signIn(user.email, pw.current);
      if (authErr) throw new Error('Current password is incorrect.');
      const { error } = await window.VQAuth.updatePassword(pw.next);
      if (error) throw error;
      setPw({ current: '', next: '' });
      toast('Password updated.', 'success');
    } catch (e) {
      toast(e.message || 'Could not update password.', 'error');
    } finally {
      setPwSaving(false);
    }
  };

  // ── Danger zone ─────────────────────────────────────────────────────────────────
  const [confirmDelete, setConfirmDelete] = useState(false);
  const handleDeleteAccount = () => {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    // Account deletion requires a server-side check — open a pre-filled request.
    window.location.href = 'mailto:hello@vulcanquanta.com'
      + '?subject=' + encodeURIComponent('Account deletion request')
      + '&body=' + encodeURIComponent(`Please permanently delete my Vulcan Quanta account: ${user?.email || ''}`);
    setConfirmDelete(false);
  };

  // ── Branding — one row per user in the Supabase `branding` table ────────────────
  const [brand, setBrand] = useState({ company_name: '', company_address: '', company_phone: '', company_email: '' });
  const [brandSaving, setBrandSaving] = useState(false);
  const [logoPreview, setLogoPreview] = useState('');
  const logoRef = useRef(null);

  useEffect(() => {
    if (!user) return;
    let active = true;
    (async () => {
      let row = null;
      if (window.VQAuth?.getBranding) {
        try {
          const { data } = await window.VQAuth.getBranding(user.id);
          row = data;
        } catch (e) {}
      }
      if (!active) return;
      // Fall back to the legacy user-metadata copy so accounts that saved
      // branding before the table existed keep their values pre-filled.
      const legacy = (user.user_metadata || {}).branding || {};
      setBrand({
        company_name:    row?.company_name    ?? legacy.company ?? '',
        company_address: row?.company_address ?? legacy.address ?? '',
        company_phone:   row?.company_phone   ?? '',
        company_email:   row?.company_email   ?? '',
      });
      let legacyLogo = '';
      try { legacyLogo = localStorage.getItem('vq_brand_logo') || ''; } catch (e) {}
      setLogoPreview(row?.logo || legacyLogo);
    })();
    return () => { active = false; };
  }, [user]);

  const setB = (k, v) => setBrand(f => ({ ...f, [k]: v }));

  const saveBranding = async () => {
    if (!window.VQAuth || !user) { toast('You need to be signed in.', 'error'); return; }
    if (!brand.company_name.trim()) { toast('Company name is required.', 'error'); return; }
    const companyEmail = brand.company_email.trim();
    if (companyEmail && !/^\S+@\S+\.\S+$/.test(companyEmail)) { toast('Enter a valid company email.', 'error'); return; }
    setBrandSaving(true);
    try {
      const { error } = await window.VQAuth.saveBranding(user.id, {
        company_name:    brand.company_name.trim(),
        company_address: brand.company_address.trim(),
        company_phone:   brand.company_phone.trim(),
        company_email:   companyEmail,
        logo:            logoPreview || null,
      });
      if (error) throw error;
      toast('Branding saved.', 'success');
    } catch (e) {
      // A missing column means the live database predates this feature —
      // point at the fix instead of echoing the raw PostgREST message.
      if (/schema cache|column/i.test(e.message || '')) {
        toast('Database needs updating — run supabase_schema.sql in the Supabase SQL Editor (see SUPABASE_SETUP.md), then save again.', 'error');
      } else {
        toast(e.message || 'Could not save branding.', 'error');
      }
    } finally {
      setBrandSaving(false);
    }
  };

  const handleLogoFile = (file) => {
    if (!file) return;
    // PNG/JPG only: the PDF and Excel pipelines rasterise the logo with PIL,
    // which cannot read SVG — accepting one would silently vanish on export.
    if (!/^image\/(png|jpe?g)$/.test(file.type)) { toast('Logo must be a PNG or JPG image.', 'error'); return; }
    if (file.size > 2 * 1024 * 1024) { toast('Logo must be under 2 MB.', 'error'); return; }
    const reader = new FileReader();
    reader.onload = () => {
      setLogoPreview(reader.result);
      toast('Logo added — click Save Branding to store it.', 'info');
    };
    reader.readAsDataURL(file);
  };

  // ── Rates — region, uplift and per-trade overrides persisted in metadata ────────
  const [rates, setRates] = useState({ region: VQ_REGIONS[0], uplift: '0', overrides: {} });
  const [ratesSaving, setRatesSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    const r = (user.user_metadata || {}).rates || {};
    setRates({
      region: r.region || VQ_REGIONS[0],
      uplift: r.uplift != null ? String(r.uplift) : '0',
      overrides: r.overrides || {},
    });
  }, [user]);

  const saveRates = async () => {
    if (!window.VQAuth || !user) { toast('You need to be signed in.', 'error'); return; }
    setRatesSaving(true);
    try {
      const { error } = await window.VQAuth.updateUserMeta({
        rates: {
          region: rates.region,
          uplift: Number(rates.uplift) || 0,
          overrides: rates.overrides,
        },
      });
      if (error) throw error;
      toast('Rate overrides saved.', 'success');
    } catch (e) {
      toast(e.message || 'Could not save rates.', 'error');
    } finally {
      setRatesSaving(false);
    }
  };

  // ── Billing — real plan from the account; nothing fabricated ────────────────────
  const planCode = ((meta.plan || 'free') + '').toLowerCase();
  const planInfo = planCode === 'pro'    ? { name: 'Pro',    price: '£39/month' }
                 : planCode === 'studio' ? { name: 'Studio', price: '£99/month' }
                 : { name: 'Free', price: '£0/month' };
  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
    : null;

  const tabs = [
    { id: 'account',  label: 'Account' },
    { id: 'branding', label: 'Branding' },
    { id: 'rates',    label: 'Rates' },
    { id: 'billing',  label: 'Billing' },
  ];

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="settings" go={go} user={user} toast={toast} />
      <main className="app-main dash-main">
        <VQParticleField />
        {/* Horizontal tab bar */}
        <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.08)', marginBottom: '28px', paddingTop: '8px' }}>
          {tabs.map(t => (
            <button key={t.id}
              style={{
                background: 'none', border: 'none', outline: 'none',
                borderBottom: `2px solid ${tab === t.id ? 'var(--amber)' : 'transparent'}`,
                color: tab === t.id ? 'white' : 'rgba(255,255,255,0.45)',
                padding: '8px 20px 14px',
                fontSize: '14px', fontWeight: tab === t.id ? 600 : 500,
                cursor: 'pointer', transition: 'all 0.15s ease',
                marginBottom: '-1px', fontFamily: 'var(--font-b)',
              }}
              onClick={() => setTab(t.id)}>{t.label}
            </button>
          ))}
        </div>

        {tab === 'account' && (
          <>
            <div className="dash-hd"><h1 className="dash-h1">Account</h1></div>
            <div className="scard vd-rise">
              <p className="scard-title">Personal details</p>
              <div className="form-grid">
                <div className="fld"><label className="flbl">First name</label>
                  <input className="finp" value={acct.first} onChange={e => setA('first', e.target.value)} placeholder="Your first name" /></div>
                <div className="fld"><label className="flbl">Last name</label>
                  <input className="finp" value={acct.last} onChange={e => setA('last', e.target.value)} placeholder="Your last name" /></div>
                <div className="fld"><label className="flbl">Email address</label>
                  <input className="finp" type="email" value={acct.email} onChange={e => setA('email', e.target.value)} placeholder="you@example.com" /></div>
                <div className="fld"><label className="flbl">Phone</label>
                  <input className="finp" type="tel" value={acct.phone} onChange={e => setA('phone', e.target.value)} placeholder="Optional" /></div>
              </div>
              <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)', marginBottom: '16px' }}>
                Changing your email sends a confirmation link to the new address before it takes effect.
              </p>
              <button className="btn btn-amber btn-pill" onClick={saveAccount} disabled={acctSaving}>
                {acctSaving ? 'Saving…' : 'Save changes'}
              </button>
            </div>

            <div className="scard vd-rise" style={{ animationDelay: '0.08s' }}>
              <p className="scard-title">Change password</p>
              <div className="form-grid">
                <div className="fld"><label className="flbl">Current password</label>
                  <input className="finp" type="password" placeholder="••••••••" autoComplete="current-password"
                    value={pw.current} onChange={e => setPw(f => ({ ...f, current: e.target.value }))} /></div>
                <div className="fld"><label className="flbl">New password</label>
                  <input className="finp" type="password" placeholder="8+ characters" autoComplete="new-password"
                    value={pw.next} onChange={e => setPw(f => ({ ...f, next: e.target.value }))} /></div>
              </div>
              <button className="btn btn-outline btn-pill" onClick={changePassword} disabled={pwSaving}>
                {pwSaving ? 'Updating…' : 'Update password'}
              </button>
            </div>

            <div className="scard vd-rise" style={{ animationDelay: '0.16s' }}>
              <p className="scard-title" style={{ color: 'var(--red)' }}>Danger zone</p>
              <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.45)', marginBottom: '16px' }}>
                Permanently delete your account and all project data. Cannot be undone.
              </p>
              <button className="btn btn-danger btn-pill"
                style={{ background: confirmDelete ? 'var(--red)' : 'transparent', color: confirmDelete ? 'white' : 'var(--red)', border: '1px solid var(--red)', padding: '10px 24px' }}
                onClick={handleDeleteAccount}>
                {confirmDelete ? 'Confirm — send deletion request' : 'Delete account'}
              </button>
              {confirmDelete && (
                <button className="btn btn-ghost btn-pill" style={{ marginLeft: '12px' }} onClick={() => setConfirmDelete(false)}>
                  Cancel
                </button>
              )}
            </div>
          </>
        )}

        {tab === 'branding' && (
          <>
            <div className="dash-hd"><h1 className="dash-h1">Branding</h1></div>
            <div className="scard vd-rise">
              <p className="scard-title">Company identity</p>
              <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.42)', marginBottom: '20px' }}>Appears on all exported BoQs. Available on Pro and Studio plans.</p>
              <div className="form-grid">
                <div className="fld"><label className="flbl">Company name</label>
                  <input className="finp" value={brand.company_name} onChange={e => setB('company_name', e.target.value)} placeholder="Your company name" /></div>
                <div className="fld"><label className="flbl">Company address</label>
                  <input className="finp" value={brand.company_address} onChange={e => setB('company_address', e.target.value)} placeholder="Street, City, Postcode" /></div>
                <div className="fld"><label className="flbl">Company phone</label>
                  <input className="finp" type="tel" value={brand.company_phone} onChange={e => setB('company_phone', e.target.value)} placeholder="e.g. 028 9012 3456" /></div>
                <div className="fld"><label className="flbl">Company email</label>
                  <input className="finp" type="email" value={brand.company_email} onChange={e => setB('company_email', e.target.value)} placeholder="office@example.co.uk" /></div>
              </div>
            </div>
            <div className="scard vd-rise" style={{ animationDelay: '0.08s' }}>
              <p className="scard-title">Logo</p>
              {logoPreview && (
                <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <img src={logoPreview} alt="Company logo"
                    style={{ height: '56px', borderRadius: '8px', background: 'rgba(255,255,255,0.06)', padding: '6px' }} />
                  <button className="btn btn-ghost btn-sm"
                    onClick={() => { setLogoPreview(''); toast('Logo removed — click Save Branding to confirm.', 'info'); }}>
                    Remove
                  </button>
                </div>
              )}
              <div className="upload-zone" style={{ padding: '32px' }}
                onClick={() => logoRef.current?.click()}
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); handleLogoFile(e.dataTransfer.files[0]); }}>
                <p style={{ fontSize: '14px', color: 'var(--c-400)' }}>Drop your logo here or click to upload. PNG or JPG, max 2 MB.</p>
              </div>
              <input ref={logoRef} type="file" accept=".png,.jpg,.jpeg" style={{ display: 'none' }}
                onChange={e => { handleLogoFile(e.target.files[0]); e.target.value = ''; }} />
              <div style={{ marginTop: '24px' }}>
                <button className="btn btn-amber btn-pill" onClick={saveBranding} disabled={brandSaving}>
                  {brandSaving ? 'Saving…' : 'Save Branding'}
                </button>
              </div>
            </div>
          </>
        )}

        {tab === 'rates' && (
          <>
            <div className="dash-hd"><h1 className="dash-h1">Rate overrides</h1></div>
            <div className="scard vd-rise">
              <p className="scard-title">Regional settings</p>
              <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.42)', marginBottom: '20px' }}>Base rates follow BCIS Q2 2026. Override individual trades below. Leave blank to use BCIS defaults.</p>
              <div className="form-grid">
                <div className="fld"><label className="flbl">Region</label>
                  <select className="finp" value={rates.region} onChange={e => setRates(f => ({ ...f, region: e.target.value }))}>
                    {VQ_REGIONS.map(r => <option key={r}>{r}</option>)}
                  </select>
                </div>
                <div className="fld"><label className="flbl">Regional uplift (%)</label>
                  <input className="finp" type="number" value={rates.uplift}
                    onChange={e => setRates(f => ({ ...f, uplift: e.target.value }))} /></div>
              </div>
            </div>
            <div className="scard vd-rise" style={{ animationDelay: '0.08s' }}>
              <p className="scard-title">Trade overrides (£/unit)</p>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                <thead><tr style={{ background: 'rgba(15,20,28,0.7)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {['Trade','BCIS default','Your override'].map(h => <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: 'rgba(255,255,255,0.45)', fontSize: '13px' }}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {VQ_RATE_TRADES.map(([trade, bcis]) => (
                    <tr key={trade} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ padding: '12px 16px', color: 'rgba(255,255,255,0.65)' }}>{trade}</td>
                      <td style={{ padding: '12px 16px', color: 'rgba(255,255,255,0.38)' }}>{bcis}</td>
                      <td style={{ padding: '12px 16px' }}>
                        <input type="text" placeholder="e.g. 0.70" className="finp" style={{ width: '120px' }}
                          value={rates.overrides[trade] || ''}
                          onChange={e => setRates(f => ({ ...f, overrides: { ...f.overrides, [trade]: e.target.value } }))} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: '24px' }}>
                <button className="btn btn-amber btn-pill" onClick={saveRates} disabled={ratesSaving}>
                  {ratesSaving ? 'Saving…' : 'Save rate overrides'}
                </button>
              </div>
            </div>
          </>
        )}

        {tab === 'billing' && (
          <>
            <div className="dash-hd"><h1 className="dash-h1">Billing</h1></div>
            <div className="scard vd-rise">
              <p className="scard-title">Current plan</p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px', marginBottom: '16px' }}>
                <div>
                  <p style={{ fontWeight: 700, fontSize: '18px', marginBottom: '4px', color: 'white' }}>{planInfo.name} — {planInfo.price}</p>
                  <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.42)' }}>
                    {memberSince ? `Member since ${memberSince}` : 'Active plan on this account'}
                  </p>
                </div>
                <button className="btn btn-outline btn-pill btn-sm" onClick={() => go('pricing')}>Change plan</button>
              </div>
            </div>
            <div className="scard vd-rise" style={{ animationDelay: '0.08s' }}>
              <p className="scard-title">Payment method</p>
              <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.45)', marginBottom: '16px' }}>
                No payment method on file. Payment details are collected when you upgrade to a paid plan.
              </p>
              <button className="btn btn-outline btn-pill btn-sm" onClick={() => go('pricing')}>View plans →</button>
            </div>
            <div className="scard vd-rise" style={{ animationDelay: '0.16s' }}>
              <p className="scard-title">Invoices</p>
              <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.45)' }}>
                No invoices yet — they will appear here once billing starts on a paid plan.
              </p>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

// ─── PROJECT SETUP ────────────────────────────────────────────────────────────────
const CONTRACT_TYPES = ['JCT Standard','JCT Design & Build','NEC3','NEC4','CIJC','Minor Works','Cost Plus','Framework'];
const LOCATION_FACTORS = ['Belfast','Londonderry','Dublin','London','Manchester','Birmingham','Edinburgh','Glasgow','Cardiff','Bristol'];
const DELETE_OPTIONS = [
  { label: 'Never',   value: null },
  { label: '30 days', value: 30 },
  { label: '60 days', value: 60 },
  { label: '90 days', value: 90 },
  { label: '180 days', value: 180 },
  { label: '1 year',  value: 365 },
];

function ProjectSetupPage({ go, toast }) {
  const [form, setForm] = React.useState({
    name: '',
    client_name: '',
    contract_type: 'JCT Standard',
    location_factor: 'Belfast',
    notes_for_ai: '',
    auto_delete_days: null,
    description: '',
  });
  const [saving, setSaving] = React.useState(false);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleCreate = async () => {
    if (!form.name.trim()) { toast('Project name is required.', 'error'); return; }
    setSaving(true);
    try {
      const sessionRes = window.VQAuth ? await window.VQAuth.getSession() : null;
      const token = sessionRes?.data?.session?.access_token || '';
      const res = await fetch(`${VQ_API}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        // No status here — the server / DB default decides, so a drifted
        // projects_status_check constraint can never reject the create.
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to create project');
      toast('Project created.', 'success');
      go('workspace', { projectId: data.id });
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ background: 'var(--vd-bg, #0f1117)', minHeight: '100vh' }}>
    <div className="vd-root">
      <AppSidebar currentPage="projects" go={go} toast={toast} />
      <div className="vd-main">
        <div className="vd-topbar">
          <span className="vd-section-title">New Project</span>
          <span className="vd-link" onClick={() => go('dashboard')}>← Back to dashboard</span>
        </div>
        <div style={{ maxWidth: 640, margin: '0 auto', padding: '32px 24px' }}>

          {/* Name */}
          <div className="fld" style={{ marginBottom: 20 }}>
            <label className="flbl">Project name <span style={{color:'var(--amber)'}}>*</span></label>
            <input className="finp" placeholder="e.g. Elmwood Avenue — New Build" value={form.name} onChange={e => set('name', e.target.value)} />
          </div>

          {/* Client */}
          <div className="fld" style={{ marginBottom: 20 }}>
            <label className="flbl">Client name</label>
            <input className="finp" placeholder="e.g. Apex Developments Ltd" value={form.client_name} onChange={e => set('client_name', e.target.value)} />
          </div>

          {/* Description */}
          <div className="fld" style={{ marginBottom: 20 }}>
            <label className="flbl">Description</label>
            <textarea className="finp" rows={3} placeholder="Brief project scope or notes" value={form.description} onChange={e => set('description', e.target.value)} style={{ resize: 'vertical', minHeight: 80 }} />
          </div>

          {/* Contract + Location row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
            <div className="fld">
              <label className="flbl">Contract type</label>
              <select className="finp" value={form.contract_type} onChange={e => set('contract_type', e.target.value)}>
                {CONTRACT_TYPES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="fld">
              <label className="flbl">Location</label>
              <select className="finp" value={form.location_factor} onChange={e => set('location_factor', e.target.value)}>
                {LOCATION_FACTORS.map(l => <option key={l}>{l}</option>)}
              </select>
            </div>
          </div>

          {/* AI instructions */}
          <div className="fld" style={{ marginBottom: 20 }}>
            <label className="flbl">Standing instructions for AI</label>
            <textarea className="finp" rows={4} placeholder="e.g. Always use CIJC wage rates. Flag any provisional sums above £10,000. This project excludes external works." value={form.notes_for_ai} onChange={e => set('notes_for_ai', e.target.value)} style={{ resize: 'vertical', minHeight: 100 }} />
            <p style={{ fontSize: 12, color: 'var(--c-400)', marginTop: 6 }}>These instructions are passed to the AI on every BoQ generation and chat message for this project.</p>
          </div>

          {/* Auto-delete */}
          <div className="fld" style={{ marginBottom: 32 }}>
            <label className="flbl">Auto-delete project after</label>
            <select className="finp" value={form.auto_delete_days ?? ''} onChange={e => set('auto_delete_days', e.target.value === '' ? null : Number(e.target.value))}>
              {DELETE_OPTIONS.map(o => <option key={String(o.value)} value={o.value ?? ''}>{o.label}</option>)}
            </select>
            <p style={{ fontSize: 12, color: 'var(--c-400)', marginTop: 6 }}>All project data including drawings, BoQ, and chat history will be permanently deleted. GDPR compliant.</p>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn btn-amber btn-pill" onClick={handleCreate} disabled={saving} style={{ flex: 1 }}>
              {saving ? 'Creating…' : 'Create project →'}
            </button>
            <button className="btn btn-outline btn-pill" onClick={() => go('dashboard')} disabled={saving}>
              Cancel
            </button>
          </div>

        </div>
      </div>
    </div>
    </div>
  );
}

// ─── PROJECT WORKSPACE ────────────────────────────────────────────────────────────
function ProjectWorkspacePage({ go, toast, projectId, onBoqReady }) {
  const [project, setProject] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [tab, setTab] = React.useState('generate');
  const [chatMessages, setChatMessages] = React.useState([]);
  const [chatInput, setChatInput] = React.useState('');
  const [chatSending, setChatSending] = React.useState(false);
  const [uploadStatus, setUploadStatus] = React.useState('idle'); // idle | uploading | processing | done
  const [boqData, setBoqData] = React.useState(null);
  const chatEndRef = React.useRef(null);

  const getToken = async () => {
    const res = window.VQAuth ? await window.VQAuth.getSession() : null;
    return res?.data?.session?.access_token || '';
  };

  const loadProject = async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const res = await fetch(`${VQ_API}/projects/${projectId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Project not found');
      const data = await res.json();
      setProject(data);
      if (data.boq_data) { setBoqData(data.boq_data); setTab('results'); }
    } catch (e) {
      toast('Could not load project.', 'error');
      go('dashboard');
    } finally {
      setLoading(false);
    }
  };

  const loadChat = async () => {
    try {
      const token = await getToken();
      const res = await fetch(`${VQ_API}/projects/${projectId}/chat`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) setChatMessages(await res.json());
    } catch (e) {}
  };

  React.useEffect(() => { loadProject(); loadChat(); }, [projectId]);
  React.useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);

  const handleUploadAndGenerate = async (file) => {
    if (!file) return;
    setUploadStatus('uploading');
    setTab('generate');
    // Same abort-on-hang protection as UploadPage.processFile (shared helper).
    const timer = vqAbortTimer();
    try {
      const token = await getToken();
      const fd = new FormData();
      fd.append('file', file);
      fd.append('project_id', projectId);
      if (project?.notes_for_ai) fd.append('notes_for_ai', project.notes_for_ai);
      if (project?.location_factor) fd.append('location_factor', project.location_factor);
      setUploadStatus('processing');
      const res = await fetch(`${VQ_API}/process`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
        body: fd,
        signal: timer.signal,
      });
      timer.clear();
      if (!res.ok) {
        // Expired session → sign-in, matching the Upload page behaviour.
        if (res.status === 401) {
          toast('Your session expired. Please sign in again.', 'error');
          setUploadStatus('idle');
          setTimeout(() => go('signin'), 1200);
          return;
        }
        const err = await res.json().catch(() => ({ error: res.statusText || 'Processing failed' }));
        const msg = err.error || 'Processing failed';
        if (res.status === 429 || res.status === 403) {
          toast(msg + ' See Pricing to upgrade.', 'error');
          // Navigate to pricing after a short delay so the user reads the message
          setTimeout(() => go('pricing'), 3500);
        } else {
          toast(msg, 'error');
        }
        setUploadStatus('idle');
        return;
      }
      const data = await res.json();
      setBoqData(data);
      onBoqReady?.(data);
      setUploadStatus('done');
      toast('BoQ generated.', 'success');
      setTab('results');
    } catch (e) {
      // Differentiate abort vs network/CORS vs other, and log the real error.
      timer.clear();
      console.error('[VQ] workspace /process upload failed:', e);
      toast(vqUploadErrorMessage(e), 'error');
      setUploadStatus('idle');
    }
  };

  const handleSendChat = async () => {
    const msg = chatInput.trim();
    if (!msg || chatSending) return;
    setChatInput('');
    setChatSending(true);
    setChatMessages(prev => [...prev, { role: 'user', content: msg, created_at: new Date().toISOString() }]);
    try {
      const token = await getToken();
      const res = await fetch(`${VQ_API}/projects/${projectId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: msg }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Chat failed');
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.reply, created_at: new Date().toISOString() }]);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setChatSending(false);
    }
  };

  if (loading) return (
    <div className="vd-root">
      <AppSidebar currentPage="projects" go={go} toast={toast} />
      <div className="vd-main" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
        <p style={{ color:'var(--c-400)' }}>Loading project…</p>
      </div>
    </div>
  );

  return (
    <div className="vd-root">
      <AppSidebar currentPage="projects" go={go} toast={toast} />
      <div className="vd-main">

        {/* Topbar */}
        <div className="vd-topbar" style={{ justifyContent:'space-between' }}>
          <div style={{ display:'flex', alignItems:'center', gap:12 }}>
            <span className="vd-link" onClick={() => go('dashboard')}>← Projects</span>
            <span style={{ color:'var(--c-300)' }}>/</span>
            <span className="vd-section-title">{project?.name || 'Untitled'}</span>
            {project?.client_name && <span style={{ fontSize:13, color:'var(--c-400)' }}>{project.client_name}</span>}
          </div>
          <button className="btn btn-outline btn-pill btn-sm" onClick={() => go('projectsettings', { projectId })}>Settings</button>
        </div>

        {/* Tab bar */}
        <div style={{ display:'flex', gap:0, borderBottom:'1px solid rgba(255,255,255,0.08)', padding:'0 24px' }}>
          {[
            { id:'generate', label:'Generate BoQ' },
            { id:'results',  label:'Results' },
            { id:'chat',     label:'Ask AI' },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              padding:'12px 20px', fontSize:13, fontWeight: tab===t.id ? 600 : 400,
              color: tab===t.id ? 'var(--amber)' : 'var(--c-500)',
              borderBottom: tab===t.id ? '2px solid var(--amber)' : '2px solid transparent',
              background:'none', border:'none',
              cursor:'pointer', transition:'color 0.15s',
            }}>{t.label}</button>
          ))}
        </div>

        {/* Tab: Generate */}
        {tab === 'generate' && (
          <div style={{ padding:'40px 24px', maxWidth:600, margin:'0 auto' }}>
            {uploadStatus === 'idle' || uploadStatus === 'done' ? (
              <>
                <p style={{ fontSize:14, color:'var(--c-400)', marginBottom:24 }}>
                  Upload a drawing or specification PDF to generate a BoQ for this project.
                  {project?.notes_for_ai && <span style={{ color:'var(--amber)' }}> AI instructions active.</span>}
                </p>
                <label style={{ display:'block', border:'2px dashed var(--c-300)', borderRadius:12, padding:'48px 32px', textAlign:'center', cursor:'pointer', transition:'border-color 0.15s' }}
                  onDragOver={e => e.preventDefault()}
                  onDrop={e => { e.preventDefault(); handleUploadAndGenerate(e.dataTransfer.files[0]); }}>
                  <input type="file" accept=".pdf" style={{ display:'none' }} onChange={e => handleUploadAndGenerate(e.target.files[0])} />
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color:'var(--c-300)', margin:'0 auto 16px' }}>
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
                    <line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/>
                  </svg>
                  <p style={{ fontWeight:600, color:'rgba(255,255,255,0.82)', marginBottom:4 }}>Drop PDF here or click to upload</p>
                  <p style={{ fontSize:12, color:'var(--c-400)' }}>NRM2-compliant BoQ generated automatically</p>
                </label>
              </>
            ) : (
              <div style={{ textAlign:'center', padding:'48px 0' }}>
                <div style={{ width:48, height:48, border:'3px solid var(--amber)', borderTopColor:'transparent', borderRadius:'50%', margin:'0 auto 24px', animation:'spin 0.8s linear infinite' }} />
                <p style={{ fontWeight:600, color:'rgba(255,255,255,0.82)' }}>
                  {uploadStatus === 'uploading' ? 'Uploading drawing…' : 'AI reading your drawing…'}
                </p>
                <p style={{ fontSize:13, color:'var(--c-400)', marginTop:8 }}>This takes 30–90 seconds for a typical drawing set.</p>
              </div>
            )}
          </div>
        )}

        {/* Tab: Results */}
        {tab === 'results' && (
          <div style={{ padding:'24px' }}>
            {boqData ? (
              <ResultsPage go={go} toast={toast} boqData={boqData} embedded={true} />
            ) : (
              <div style={{ textAlign:'center', padding:'64px 0' }}>
                <p style={{ color:'var(--c-400)' }}>No BoQ generated yet. Upload a drawing to get started.</p>
                <button className="btn btn-amber btn-pill" style={{ marginTop:16 }} onClick={() => setTab('generate')}>Upload drawing</button>
              </div>
            )}
          </div>
        )}

        {/* Tab: Chat */}
        {tab === 'chat' && (
          <div style={{ display:'flex', flexDirection:'column', height:'calc(100vh - 120px)' }}>
            <div style={{ flex:1, overflowY:'auto', padding:'24px', display:'flex', flexDirection:'column', gap:16 }}>
              {chatMessages.length === 0 && (
                <div style={{ textAlign:'center', padding:'48px 0', color:'var(--c-400)' }}>
                  <p style={{ fontWeight:600, marginBottom:8 }}>Ask anything about this project</p>
                  <p style={{ fontSize:13 }}>Quantities, costs, scope, NRM2 structure — all answered from your BoQ data.</p>
                </div>
              )}
              {chatMessages.map((m, i) => (
                <div key={i} style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth:'72%',
                  background: m.role === 'user' ? 'var(--amber)' : 'var(--c-100)',
                  color: m.role === 'user' ? 'white' : 'var(--c-900)',
                  padding:'12px 16px', borderRadius: m.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                  fontSize:14, lineHeight:1.6,
                }}>
                  {m.content}
                </div>
              ))}
              {chatSending && (
                <div style={{ alignSelf:'flex-start', background:'var(--c-100)', padding:'12px 16px', borderRadius:'16px 16px 16px 4px', fontSize:14, color:'var(--c-400)' }}>
                  Thinking…
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
            <div style={{ padding:'16px 24px', borderTop:'1px solid rgba(255,255,255,0.08)', display:'flex', gap:12 }}>
              <input
                className="finp"
                style={{ flex:1 }}
                placeholder={boqData ? 'Ask about quantities, costs, scope…' : 'Generate a BoQ first to unlock chat'}
                value={chatInput}
                disabled={!boqData || chatSending}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSendChat()}
              />
              <button className="btn btn-amber btn-pill" onClick={handleSendChat} disabled={!boqData || chatSending || !chatInput.trim()}>
                Send
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

// ─── PROJECT SETTINGS ─────────────────────────────────────────────────────────────
function ProjectSettingsPage({ go, toast, projectId }) {
  const [form, setForm] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);

  const getToken = async () => {
    const res = window.VQAuth ? await window.VQAuth.getSession() : null;
    return res?.data?.session?.access_token || '';
  };

  React.useEffect(() => {
    const load = async () => {
      try {
        const token = await getToken();
        const res = await fetch(`${VQ_API}/projects/${projectId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        setForm({
          name:             data.name || '',
          client_name:      data.client_name || '',
          description:      data.description || '',
          contract_type:    data.contract_type || 'JCT Standard',
          location_factor:  data.location_factor || 'Belfast',
          notes_for_ai:     data.notes_for_ai || '',
          auto_delete_days: data.auto_delete_days ?? null,
        });
      } catch {
        toast('Could not load project settings.', 'error');
        go('dashboard');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [projectId]);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSave = async () => {
    if (!form.name.trim()) { toast('Project name is required.', 'error'); return; }
    setSaving(true);
    try {
      const token = await getToken();
      const res = await fetch(`${VQ_API}/projects/${projectId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error((await res.json()).error || 'Save failed');
      toast('Settings saved.', 'success');
      go('workspace', { projectId });
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    setDeleting(true);
    try {
      const token = await getToken();
      const res = await fetch(`${VQ_API}/projects/${projectId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok && res.status !== 204) throw new Error('Delete failed');
      toast('Project deleted.', 'success');
      go('dashboard');
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  if (loading) return (
    <div className="vd-root">
      <AppSidebar currentPage="projects" go={go} toast={toast} />
      <div className="vd-main" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
        <p style={{ color:'var(--c-400)' }}>Loading…</p>
      </div>
    </div>
  );

  return (
    <div className="vd-root">
      <AppSidebar currentPage="projects" go={go} toast={toast} />
      <div className="vd-main">

        <div className="vd-topbar">
          <span className="vd-section-title">Project Settings</span>
          <span className="vd-link" onClick={() => go('workspace', { projectId })}>← Back to project</span>
        </div>

        <div style={{ maxWidth: 640, margin: '0 auto', padding: '32px 24px' }}>

          {/* Name */}
          <div className="fld" style={{ marginBottom: 20 }}>
            <label className="flbl">Project name <span style={{color:'var(--amber)'}}>*</span></label>
            <input className="finp" value={form.name} onChange={e => set('name', e.target.value)} />
          </div>

          {/* Client */}
          <div className="fld" style={{ marginBottom: 20 }}>
            <label className="flbl">Client name</label>
            <input className="finp" value={form.client_name} onChange={e => set('client_name', e.target.value)} />
          </div>

          {/* Description */}
          <div className="fld" style={{ marginBottom: 20 }}>
            <label className="flbl">Description</label>
            <textarea className="finp" rows={3} value={form.description} onChange={e => set('description', e.target.value)} style={{ resize:'vertical', minHeight:80 }} />
          </div>

          {/* Contract + Location */}
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:20 }}>
            <div className="fld">
              <label className="flbl">Contract type</label>
              <select className="finp" value={form.contract_type} onChange={e => set('contract_type', e.target.value)}>
                {CONTRACT_TYPES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="fld">
              <label className="flbl">Location</label>
              <select className="finp" value={form.location_factor} onChange={e => set('location_factor', e.target.value)}>
                {LOCATION_FACTORS.map(l => <option key={l}>{l}</option>)}
              </select>
            </div>
          </div>

          {/* AI instructions */}
          <div className="fld" style={{ marginBottom: 20 }}>
            <label className="flbl">Standing instructions for AI</label>
            <textarea className="finp" rows={4} value={form.notes_for_ai} onChange={e => set('notes_for_ai', e.target.value)} style={{ resize:'vertical', minHeight:100 }} />
            <p style={{ fontSize:12, color:'var(--c-400)', marginTop:6 }}>Passed to the AI on every BoQ generation and chat message for this project.</p>
          </div>

          {/* Auto-delete */}
          <div className="fld" style={{ marginBottom: 40 }}>
            <label className="flbl">Auto-delete project after</label>
            <select className="finp" value={form.auto_delete_days ?? ''} onChange={e => set('auto_delete_days', e.target.value === '' ? null : Number(e.target.value))}>
              {DELETE_OPTIONS.map(o => <option key={String(o.value)} value={o.value ?? ''}>{o.label}</option>)}
            </select>
            <p style={{ fontSize:12, color:'var(--c-400)', marginTop:6 }}>All project data including drawings, BoQ, and chat history will be permanently deleted.</p>
          </div>

          {/* Save */}
          <div style={{ display:'flex', gap:12, marginBottom: 48 }}>
            <button className="btn btn-amber btn-pill" onClick={handleSave} disabled={saving} style={{ flex:1 }}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            <button className="btn btn-outline btn-pill" onClick={() => go('workspace', { projectId })} disabled={saving}>
              Cancel
            </button>
          </div>

          {/* Danger zone */}
          <div style={{ borderTop:'1px solid rgba(255,255,255,0.1)', paddingTop:32 }}>
            <p style={{ fontSize:13, fontWeight:600, color:'rgba(255,255,255,0.75)', marginBottom:8 }}>Danger zone</p>
            <p style={{ fontSize:13, color:'var(--c-400)', marginBottom:16 }}>
              Permanently deletes this project, all uploaded drawings, the generated BoQ, and all chat history. This cannot be undone.
            </p>
            <button
              className="btn btn-pill"
              onClick={handleDelete}
              disabled={deleting}
              style={{ background: confirmDelete ? '#dc2626' : 'transparent', color: confirmDelete ? 'white' : '#dc2626', border:'1px solid #dc2626', padding:'10px 24px', fontSize:13 }}>
              {deleting ? 'Deleting…' : confirmDelete ? 'Confirm — delete permanently' : 'Delete project'}
            </button>
            {confirmDelete && !deleting && (
              <button className="btn btn-outline btn-pill" onClick={() => setConfirmDelete(false)} style={{ marginLeft:12, fontSize:13 }}>
                Cancel
              </button>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}

// ─── SIGN UP ───────────────────────────────────────────────────────────────────────
function SignUpPage({ go, toast, plan = 'pro' }) {
  const [selectedPlan, setSelectedPlan] = useState(plan);
  const [name, setName]                 = useState('');
  const [email, setEmail]               = useState('');
  const [password, setPassword]         = useState('');
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState('');

  const handleSubmit = async e => {
    e.preventDefault();
    setError('');

    if (!name.trim())  { setError('Please enter your full name.');            return; }
    if (!email)        { setError('Please enter your work email.');            return; }
    if (!password)     { setError('Please choose a password.');               return; }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }

    if (!window.VQAuth) {
      setError('Authentication is not configured. Please contact support.');
      return;
    }

    setLoading(true);
    const { data, error: err } = await window.VQAuth.signUp(email, password, name.trim(), selectedPlan);
    setLoading(false);

    if (err) {
      const msg = err.message || '';
      if (msg.toLowerCase().includes('already registered') || msg.toLowerCase().includes('already exists')) {
        setError('An account with this email already exists. Try signing in instead.');
      } else {
        setError(msg || 'Could not create account. Please try again.');
      }
      return;
    }

    if (data && data.session) {
      go('dashboard');
    } else {
      go('checkemail', { pendingEmail: email });
    }
  };

  return (
    <div className="signin-pg">
      <div className="signin-card" style={{ maxWidth: '440px' }}>
        <img src="logo-transparent.png" alt="Vulcan Quanta"
          style={{ height: '48px', marginBottom: '32px', display: 'block', cursor: 'pointer' }}
          onClick={() => go('signin')} />
        <h1 className="signin-h">Create your account</h1>
        <p className="signin-sub" style={{ marginBottom: '24px' }}>Get a priced BoQ in under 2 minutes.</p>

        {error && <div className="auth-err" role="alert">{error}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="fld" style={{ marginBottom: '16px' }}>
            <label className="flbl" htmlFor="su-plan">Plan</label>
            <select id="su-plan" className="finp" value={selectedPlan}
              onChange={e => setSelectedPlan(e.target.value)}>
              <option value="free">Free — £0/month</option>
              <option value="pro">Pro — £39/month</option>
              <option value="studio">Studio — £99/month</option>
            </select>
          </div>
          <div className="fld" style={{ marginBottom: '16px' }}>
            <label className="flbl" htmlFor="su-name">Full name</label>
            <input id="su-name" className="finp" type="text" placeholder="James Henderson"
              value={name} onChange={e => setName(e.target.value)}
              autoComplete="name" required autoFocus />
          </div>
          <div className="fld" style={{ marginBottom: '16px' }}>
            <label className="flbl" htmlFor="su-email">Work email</label>
            <input id="su-email" className="finp" type="email" placeholder="you@example.com"
              value={email} onChange={e => setEmail(e.target.value)}
              autoComplete="email" required />
          </div>
          <div className="fld" style={{ marginBottom: '28px' }}>
            <label className="flbl" htmlFor="su-pw">Password</label>
            <input id="su-pw" className="finp" type="password" placeholder="8+ characters"
              value={password} onChange={e => setPassword(e.target.value)}
              autoComplete="new-password" required />
          </div>
          <button className="btn btn-amber btn-pill" style={{ width: '100%' }}
            type="submit" disabled={loading}>
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p style={{ marginTop: '16px', fontSize: '12px', color: 'var(--c-400)', textAlign: 'center', lineHeight: '1.6' }}>
          By creating an account you agree to our{' '}
          <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>Terms of Service</span>
          {' '}and{' '}
          <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>Privacy Policy</span>.
        </p>
        <p style={{ marginTop: '16px', textAlign: 'center', fontSize: '13px', color: 'var(--c-400)' }}>
          Already have an account?{' '}
          <span style={{ color: 'var(--amber)', fontWeight: 600, cursor: 'pointer' }}
            onClick={() => go('signin')}>Sign in →</span>
        </p>
      </div>
    </div>
  );
}

// Persists across SignInPage unmount/remount within the same browser session.
// Set to true when the video plays to completion; checked on every mount.
let heroPlayed = false;

// ─── SIGN IN ───────────────────────────────────────────────────────────────────────
function SignInPage({ go, toast, user }) {
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  // Initialise from heroPlayed so returning visitors see the dock immediately,
  // with no post-mount state update or visible flicker.
  const [dockVisible, setDockVisible] = useState(heroPlayed);
  const videoRef = useRef(null);

  useEffect(() => {
    // Video already played this session — dock is visible via initial state, nothing to do.
    if (heroPlayed) return;

    const video = videoRef.current;
    let fallback;

    // Reveal the centred dock and mark the intro as done. heroPlayed flips the
    // wrapper to transparent and unmounts the <video>, leaving the captured
    // last frame (in #video-bg-freeze) as the persistent background.
    const revealDock = () => {
      heroPlayed = true;
      setDockVisible(true);
    };

    // When the video finishes: freeze on the last frame by painting it to a canvas
    // and stamping it onto the persistent freeze-frame div, then show the dock.
    const onEnded = () => {
      try {
        const canvas = document.createElement('canvas');
        canvas.width  = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        const freeze = document.getElementById('video-bg-freeze');
        if (freeze) freeze.style.backgroundImage = `url(${canvas.toDataURL('image/jpeg', 0.85)})`;
      } catch (e) {}
      clearTimeout(fallback);
      revealDock();
    };

    if (video) {
      // Dock appears only once the video has played all the way through.
      video.addEventListener('ended', onEnded, { once: true });
      // If the video can't load/play, don't strand the user on a blank intro.
      video.addEventListener('error', revealDock, { once: true });
      // Play immediately if enough data is buffered, otherwise wait for canplaythrough.
      const playVideo = () => video.play().catch(() => {});
      if (video.readyState >= 3) {
        playVideo();
      } else {
        video.addEventListener('canplaythrough', playVideo, { once: true });
      }
    }

    // Safety net: if 'ended' never fires (codec/load failure), reveal the dock
    // anyway after a generous window so the sign-in screen is never stuck hidden.
    fallback = setTimeout(revealDock, 15000);
    return () => clearTimeout(fallback);
  }, []);

  const handleSubmit = async e => {
    e.preventDefault();
    setError('');

    if (!email || !password) { setError('Please fill in all fields.'); return; }

    if (!window.VQAuth) {
      setError('Authentication is not configured. Please contact support.');
      return;
    }

    setLoading(true);
    const { data, error: err } = await window.VQAuth.signIn(email, password);
    setLoading(false);

    if (err) {
      const msg = err.message || '';
      if (msg.toLowerCase().includes('invalid') || msg.toLowerCase().includes('credentials')) {
        setError('Incorrect email or password. Please check and try again.');
      } else if (msg.toLowerCase().includes('email not confirmed')) {
        setError('Please verify your email before signing in. Check your inbox.');
      } else {
        setError(msg || 'Sign in failed. Please try again.');
      }
      return;
    }

    go('dashboard');
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: heroPlayed ? 'transparent' : '#080706', overflow: 'hidden' }}>
      {/* Video only on first visit — skipped once heroPlayed is true */}
      {!heroPlayed && (
        <video
          ref={videoRef}
          src="hero.mp4"
          autoPlay
          muted
          playsInline
          preload="auto"
          style={{
            position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
            objectFit: 'cover', zIndex: 0,
          }}
          aria-hidden="true"
        />
      )}
      {/* Dark overlay to improve text contrast */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(0,0,0,0.48)', zIndex: 1, pointerEvents: 'none',
      }} />

      {/* VULCAN QUANTA title — CSS animation fades it in from first paint */}
      <div className="signin-vq-title">
        VULCAN QUANTA
      </div>

      {/* Login dock — centred; fades in once the intro video has played through */}
      <div className={`signin-dock${dockVisible ? ' dock-visible' : ''}`}>
        <div className="signin-card">
          <img src="logo-transparent.png" alt="Vulcan Quanta"
            style={{ height: '40px', marginBottom: '28px', cursor: 'pointer', display: 'block' }}
            onClick={() => go('signin')} />

          {user ? (
            <>
              <h1 className="signin-h">Welcome back.</h1>
              <p className="signin-sub" style={{ marginBottom: '32px' }}>You're already signed in.</p>
              <button className="btn btn-amber btn-pill" style={{ width: '100%' }}
                onClick={() => go('dashboard')}>
                Enter Dashboard →
              </button>
            </>
          ) : (
            <>
              <h1 className="signin-h">Sign in</h1>
              <p className="signin-sub" style={{ marginBottom: '24px' }}>Welcome back.</p>

              {error && <div className="auth-err" role="alert">{error}</div>}

              <form onSubmit={handleSubmit} noValidate>
                <div className="fld" style={{ marginBottom: '14px' }}>
                  <label className="flbl" htmlFor="si-email">Email address</label>
                  <input id="si-email" className="finp" type="email" placeholder="you@example.com"
                    value={email} onChange={e => setEmail(e.target.value)}
                    autoComplete="email" required autoFocus />
                </div>
                <div className="fld" style={{ marginBottom: '24px' }}>
                  <label className="flbl" htmlFor="si-pw">Password</label>
                  <input id="si-pw" className="finp" type="password" placeholder="••••••••"
                    value={password} onChange={e => setPassword(e.target.value)}
                    autoComplete="current-password" required />
                </div>
                <button className="btn btn-amber btn-pill" style={{ width: '100%' }}
                  type="submit" disabled={loading}>
                  {loading ? 'Signing in…' : 'Sign in'}
                </button>
              </form>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '18px', fontSize: '13px' }}>
                <span style={{ color: 'var(--amber)', cursor: 'pointer' }}
                  onClick={() => go('forgotpassword')}>Forgot password?</span>
              </div>
              <p style={{ marginTop: '18px', textAlign: 'center', fontSize: '13px', color: 'rgba(255,255,255,0.4)' }}>
                No account?{' '}
                <span style={{ color: 'var(--amber)', fontWeight: 600, cursor: 'pointer' }}
                  onClick={() => go('signup')}>Start free →</span>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── FORGOT PASSWORD ──────────────────────────────────────────────────────────────────
function ForgotPasswordPage({ go, toast }) {
  const [email, setEmail]     = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [sent, setSent]       = useState(false);

  const handleSubmit = async e => {
    e.preventDefault();
    setError('');

    if (!email) { setError('Please enter your email address.'); return; }

    if (!window.VQAuth) {
      setError('Authentication is not configured. Please contact support.');
      return;
    }

    setLoading(true);
    const redirectTo = window.location.href.split('#')[0];
    const { error: err } = await window.VQAuth.forgotPassword(email, redirectTo);
    setLoading(false);

    if (err) {
      setError(err.message || 'Failed to send reset email. Please try again.');
      return;
    }

    setSent(true);
  };

  if (sent) {
    return (
      <div className="signin-pg">
        <div className="signin-card" style={{ textAlign: 'center' }}>
          <img src="logo-transparent.png" alt="Vulcan Quanta"
            style={{ height: '48px', marginBottom: '32px', display: 'block', margin: '0 auto 32px' }} />
          <div style={{ width: '64px', height: '64px', background: 'rgba(215,117,85,0.1)', borderRadius: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px', fontSize: '28px' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{display:'inline',verticalAlign:'middle'}}><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
          </div>
          <h1 className="signin-h" style={{ marginBottom: '12px' }}>Check your inbox</h1>
          <p style={{ color: 'var(--c-500)', fontSize: '15px', lineHeight: '1.65', marginBottom: '8px' }}>
            We sent a reset link to
          </p>
          <p style={{ fontWeight: 700, color: 'var(--c-950)', fontSize: '15px', marginBottom: '24px', wordBreak: 'break-word' }}>
            {email}
          </p>
          <p style={{ color: 'var(--c-500)', fontSize: '14px', lineHeight: '1.65', marginBottom: '28px' }}>
            Click the link in the email to choose a new password. The link expires in 1 hour.
          </p>
          <p style={{ fontSize: '13px', color: 'var(--c-400)', marginBottom: '28px' }}>
            Didn't receive it? Check your spam folder, or{' '}
            <span style={{ color: 'var(--amber)', cursor: 'pointer', fontWeight: 600 }}
              onClick={() => { setSent(false); setEmail(''); }}>try again</span>.
          </p>
          <button className="btn btn-outline btn-pill" style={{ width: '100%' }}
            onClick={() => go('signin')}>← Back to sign in</button>
        </div>
      </div>
    );
  }

  return (
    <div className="signin-pg">
      <div className="signin-card">
        <img src="logo-transparent.png" alt="Vulcan Quanta"
          style={{ height: '48px', marginBottom: '32px', cursor: 'pointer', display: 'block' }}
          onClick={() => go('signin')} />
        <h1 className="signin-h">Reset your password</h1>
        <p className="signin-sub" style={{ marginBottom: '28px' }}>
          Enter your account email and we'll send a reset link.
        </p>

        {error && <div className="auth-err" role="alert">{error}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="fld" style={{ marginBottom: '28px' }}>
            <label className="flbl" htmlFor="fp-email">Email address</label>
            <input id="fp-email" className="finp" type="email" placeholder="you@example.com"
              value={email} onChange={e => setEmail(e.target.value)}
              autoComplete="email" required autoFocus />
          </div>
          <button className="btn btn-amber btn-pill" style={{ width: '100%' }}
            type="submit" disabled={loading}>
            {loading ? 'Sending reset link…' : 'Send reset link'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '24px' }}>
          <span style={{ color: 'var(--blue)', fontSize: '13px', cursor: 'pointer' }}
            onClick={() => go('signin')}>← Back to sign in</span>
        </div>
      </div>
    </div>
  );
}

// ─── CHECK EMAIL ──────────────────────────────────────────────────────────────────────
function CheckEmailPage({ go, toast, email }) {
  const [resending, setResending] = useState(false);
  const [resent, setResent]       = useState(false);

  const handleResend = async () => {
    if (resending || resent) return;
    if (!email) { toast('Email address not available — try signing up again.', 'error'); return; }

    if (!window.VQAuth) {
      toast('Authentication is not configured. Please contact support.', 'error');
      return;
    }

    setResending(true);
    const { error } = await window.VQAuth.resendVerification(email);
    setResending(false);

    if (error) {
      toast(error.message || 'Failed to resend. Please try again.', 'error');
    } else {
      setResent(true);
      toast('Verification email sent.', 'success');
    }
  };

  return (
    <div className="signin-pg">
      <div className="signin-card" style={{ textAlign: 'center' }}>
        <img src="logo-transparent.png" alt="Vulcan Quanta"
          style={{ height: '48px', marginBottom: '32px', display: 'block', margin: '0 auto 32px' }} />
        <div style={{ width: '64px', height: '64px', background: 'rgba(215,117,85,0.1)', borderRadius: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px', fontSize: '28px' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{display:'inline',verticalAlign:'middle'}}><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
        </div>
        <h1 className="signin-h" style={{ marginBottom: '12px' }}>Verify your email</h1>
        {email
          ? <p style={{ color: 'var(--c-500)', fontSize: '15px', lineHeight: '1.65', marginBottom: '8px' }}>
              We sent a verification link to
            </p>
          : null
        }
        {email && (
          <p style={{ fontWeight: 700, color: 'var(--c-950)', fontSize: '15px', marginBottom: '24px', wordBreak: 'break-word' }}>
            {email}
          </p>
        )}
        {!email && (
          <p style={{ color: 'var(--c-500)', fontSize: '15px', lineHeight: '1.65', marginBottom: '24px' }}>
            Check your inbox for a verification link and click it to activate your account.
          </p>
        )}

        <div style={{ background: 'var(--c-50)', border: '1px solid var(--c-200)', borderRadius: '10px', padding: '16px 20px', marginBottom: '28px', fontSize: '14px', color: 'var(--c-600)', lineHeight: '1.65', textAlign: 'left' }}>
          <strong style={{ color: 'var(--c-950)' }}>Tip:</strong> Check your spam or junk folder if the email doesn't arrive within a few minutes.
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {email && (
            <button className="btn btn-outline btn-pill" style={{ width: '100%' }}
              onClick={handleResend} disabled={resending || resent}>
              {resent ? '✓ Email sent again' : resending ? 'Sending…' : 'Resend verification email'}
            </button>
          )}
          <p style={{ fontSize: '13px', color: 'var(--c-400)', marginTop: '4px' }}>
            Already verified?{' '}
            <span style={{ color: 'var(--amber)', fontWeight: 600, cursor: 'pointer' }}
              onClick={() => go('signin')}>Sign in →</span>
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── RESET PASSWORD ─────────────────────────────────────────────────────────────────────
function ResetPasswordPage({ go, toast }) {
  const [password, setPassword]   = useState('');
  const [confirm, setConfirm]     = useState('');
  const [showPw, setShowPw]       = useState(false);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const [done, setDone]           = useState(false);

  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => go('signin'), 3000);
    return () => clearTimeout(t);
  }, [done]);

  const handleSubmit = async e => {
    e.preventDefault();
    setError('');

    if (!password || !confirm) { setError('Please fill in both password fields.'); return; }
    if (password.length < 8)   { setError('Password must be at least 8 characters.'); return; }
    if (password !== confirm)   { setError('Passwords do not match. Please try again.'); return; }

    if (!window.VQAuth) {
      setError('Authentication is not configured. Please contact support.');
      return;
    }

    setLoading(true);
    const { error: err } = await window.VQAuth.updatePassword(password);
    setLoading(false);

    if (err) {
      setError(err.message || 'Failed to update password. Your reset link may have expired.');
      return;
    }

    setDone(true);
    toast('Password updated successfully.', 'success');
  };

  if (done) {
    return (
      <div className="signin-pg">
        <div className="signin-card" style={{ textAlign: 'center' }}>
          <img src="logo-transparent.png" alt="Vulcan Quanta"
            style={{ height: '48px', marginBottom: '32px', display: 'block', margin: '0 auto 32px' }} />
          <div style={{ width: '64px', height: '64px', background: 'rgba(16,185,129,0.1)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px', fontSize: '28px', color: 'var(--green)', fontWeight: 800 }}>
            ✓
          </div>
          <h1 className="signin-h" style={{ marginBottom: '12px' }}>Password updated</h1>
          <p style={{ color: 'var(--c-500)', fontSize: '15px', lineHeight: '1.65', marginBottom: '32px' }}>
            Your password has been changed. Redirecting you to sign in&hellip;
          </p>
          <button className="btn btn-amber btn-pill" style={{ width: '100%' }}
            onClick={() => go('signin')}>Sign in now</button>
        </div>
      </div>
    );
  }

  return (
    <div className="signin-pg">
      <div className="signin-card">
        <img src="logo-transparent.png" alt="Vulcan Quanta"
          style={{ height: '48px', marginBottom: '32px', cursor: 'pointer', display: 'block' }}
          onClick={() => go('signin')} />
        <h1 className="signin-h">Set a new password</h1>
        <p className="signin-sub" style={{ marginBottom: '28px' }}>Choose a strong password for your account.</p>

        {error && <div className="auth-err" role="alert">{error}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="fld" style={{ marginBottom: '16px' }}>
            <label className="flbl" htmlFor="rp-pw">New password</label>
            <input id="rp-pw" className="finp"
              type={showPw ? 'text' : 'password'}
              placeholder="8+ characters"
              value={password} onChange={e => setPassword(e.target.value)}
              autoComplete="new-password" required autoFocus />
          </div>
          <div className="fld" style={{ marginBottom: '12px' }}>
            <label className="flbl" htmlFor="rp-confirm">Confirm new password</label>
            <input id="rp-confirm" className="finp"
              type={showPw ? 'text' : 'password'}
              placeholder="Repeat your password"
              value={confirm} onChange={e => setConfirm(e.target.value)}
              autoComplete="new-password" required />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--c-500)', cursor: 'pointer', marginBottom: '28px', userSelect: 'none' }}>
            <input type="checkbox" checked={showPw} onChange={e => setShowPw(e.target.checked)} />
            Show password
          </label>
          <button className="btn btn-amber btn-pill" style={{ width: '100%' }}
            type="submit" disabled={loading}>
            {loading ? 'Updating password…' : 'Update password'}
          </button>
        </form>
      </div>
    </div>
  );
}

// ─── PRICING ────────────────────────────────────────────────────────────────────────
function PricingPage({ go, toast }) {
  const plans = [
    { name: 'Free', price: '£0', period: 'forever', rec: false,
      feats: [{ on: true, t: '2 projects per month' },{ on: true, t: 'Watermarked output' },{ on: true, t: 'PDF export' },{ on: false, t: 'Excel export' },{ on: false, t: 'Custom branding' },{ on: false, t: 'Priority support' }],
      cta: 'Get started', action: () => go('signup') },
    { name: 'Pro', price: '£39', period: 'per month', rec: true,
      feats: [{ on: true, t: 'Unlimited projects' },{ on: true, t: 'No watermark' },{ on: true, t: 'PDF & Excel export' },{ on: true, t: 'Your branding & logo' },{ on: true, t: 'Custom trade sections' },{ on: false, t: 'Team seats (up to 5)' }],
      cta: 'Start free trial', action: () => go('signup') },
    { name: 'Studio', price: '£99', period: 'per month', rec: false,
      feats: [{ on: true, t: 'Everything in Pro' },{ on: true, t: 'Up to 5 team seats' },{ on: true, t: 'White-label output' },{ on: true, t: 'Custom rates & rules' },{ on: true, t: 'Variation order templates' },{ on: true, t: 'Priority support' }],
      cta: 'Contact sales', action: () => toast('Contact us: hello@vulcanquanta.com', 'info') },
  ];
  const compareRows = [
    ['Projects / month','2','Unlimited','Unlimited'],['Watermark on output','Yes','No','No'],
    ['PDF export','✓','✓','✓'],['Excel export','—','✓','✓'],
    ['Custom branding','—','✓','✓'],['Custom trade sections','—','✓','✓'],
    ['Team seats','1','1','5'],['White-label output','—','—','✓'],
    ['Custom rates & rules','—','—','✓'],['Variation order templates','—','—','✓'],['Priority support','—','—','✓'],
  ];
  return (
    <div style={{ background: 'var(--white)', paddingBottom: '120px' }}>
      <div style={{ background: 'var(--c-950)', padding: '120px 0 96px', borderBottom: '1px solid var(--c-800)' }}>
        <div className="inner" style={{ textAlign: 'center' }}>
          <h1 className="display-xl" style={{ color: 'white', marginBottom: '20px' }}>Simple, transparent pricing</h1>
          <p style={{ color: 'var(--c-300)', fontSize: '19px', maxWidth: '480px', margin: '0 auto' }}>Start free. Scale as you grow. No long-term contracts. Cancel anytime.</p>
        </div>
      </div>
      <div className="inner" style={{ marginTop: '-48px' }}>
        <div className="pricing-grid">
          {plans.map((plan, i) => (
            <div key={i} className={`pricing-card ${plan.rec ? 'rec' : ''}`}>
              {plan.rec && <p className="pricing-badge">Most popular</p>}
              <p className="pricing-name">{plan.name}</p>
              <p className="pricing-price">{plan.price}</p>
              <p className="pricing-period">{plan.period}</p>
              <ul className="pricing-feats">{plan.feats.map((f, j) => <li key={j} className={f.on ? 'on' : 'off'}>{f.t}</li>)}</ul>
              <button className={`btn btn-pill ${plan.rec ? 'btn-amber' : 'btn-outline'}`} style={{ width: '100%' }} onClick={plan.action}>{plan.cta}</button>
            </div>
          ))}
        </div>
        <h2 className="display-lg" style={{ textAlign: 'center', margin: '96px 0 48px' }}>Full feature comparison</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px', border: '1px solid var(--c-200)', borderRadius: '8px', overflow: 'hidden' }}>
          <thead>
            <tr style={{ background: 'var(--c-50)', borderBottom: '2px solid var(--c-200)' }}>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: 700, color: 'var(--c-950)' }}>Feature</th>
              {['Free','Pro','Studio'].map(p => <th key={p} style={{ padding: '16px', textAlign: 'center', fontWeight: 700, color: 'var(--c-950)' }}>{p}</th>)}
            </tr>
          </thead>
          <tbody>
            {compareRows.map(([feat, ...vals], i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--c-100)', background: i % 2 === 0 ? 'white' : 'var(--c-50)' }}>
                <td style={{ padding: '14px 16px', fontWeight: 500 }}>{feat}</td>
                {vals.map((v, j) => (
                  <td key={j} style={{ padding: '14px 16px', textAlign: 'center', color: v === '✓' ? 'var(--green)' : v === '—' ? 'var(--c-300)' : 'var(--c-700)', fontWeight: v === '✓' ? 700 : 400 }}>{v}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── MEASUREMENT HUB ────────────────────────────────────────────────────────────
// Phase 1: UI shell only — static three-panel workspace, no data wiring, no API
// calls. Sources listed here are placeholders for the upcoming integrations.
// Stroke line-icons for the source cards (18px, currentColor) — same visual family
// as the sidebar/stat icons used elsewhere in the app.
const MHUB_ICON = {
  csv: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" />
      <line x1="8" y1="13" x2="16" y2="13" /><line x1="8" y1="17" x2="13" y2="17" />
    </svg>
  ),
  xlsx: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" /><line x1="4" y1="10" x2="20" y2="10" />
      <line x1="4" y1="15" x2="20" y2="15" /><line x1="12" y1="4" x2="12" y2="20" />
    </svg>
  ),
  excel: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" /><line x1="4" y1="9" x2="20" y2="9" />
      <line x1="9" y1="9" x2="9" y2="20" /><polyline points="13 13 15 15 18 12" />
    </svg>
  ),
  manual: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z" />
    </svg>
  ),
  file: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" />
    </svg>
  ),
};

// Source cards. `accept` only filters the native picker; nothing is processed yet.
const MHUB_SOURCES = [
  { id: 'bluebeam_csv',  name: 'Import Bluebeam CSV',       desc: 'Load a measurements CSV exported from Bluebeam Revu.',      accept: '.csv',            icon: MHUB_ICON.csv },
  { id: 'bluebeam_xlsx', name: 'Import Bluebeam XLSX',      desc: 'Load a measurements workbook exported from Bluebeam Revu.', accept: '.xlsx',           icon: MHUB_ICON.xlsx },
  { id: 'excel_takeoff', name: 'Import Excel Takeoff',      desc: 'Load a takeoff prepared in Excel (.xlsx, .xls or .csv).',   accept: '.xlsx,.xls,.csv', icon: MHUB_ICON.excel },
  { id: 'manual_entry',  name: 'Manual Measurement Entry',  desc: 'Attach a sketch or notes to key measurements in by hand.',  accept: '',                icon: MHUB_ICON.manual },
];

const MHUB_DETAIL_ROWS = [
  ['Source', '—'],
  ['Quantity', '—'],
  ['Unit', '—'],
  ['NRM2 section', '—'],
  ['Drawing ref', '—'],
];

// Sortable, searchable, paginated grid for parsed measurements. Pure display —
// no AI, classification or pricing. Filtering/sorting run once per change via
// useMemo over the full dataset, but only one page of rows (PAGE_SIZE) is ever
// in the DOM, so 1000+ rows stay responsive.
const MHUB_PAGE_SIZE = 50;

function MeasurementGrid({ rows, meta }) {
  const [q, setQ]             = useState('');
  const [sortKey, setSortKey] = useState('description');
  const [sortDir, setSortDir] = useState('asc');
  const [page, setPage]       = useState(0);

  const filtered = React.useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter(r =>
      String(r.description ?? '').toLowerCase().includes(term) ||
      String(r.unit ?? '').toLowerCase().includes(term) ||
      String(r.quantity ?? '').toLowerCase().includes(term));
  }, [rows, q]);

  const sorted = React.useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1;
    const arr = filtered.slice();
    arr.sort((a, b) => {
      if (sortKey === 'quantity') {
        const av = a.quantity == null ? -Infinity : Number(a.quantity);
        const bv = b.quantity == null ? -Infinity : Number(b.quantity);
        return av === bv ? 0 : (av < bv ? -1 : 1) * dir;
      }
      const av = String(a[sortKey] ?? '').toLowerCase();
      const bv = String(b[sortKey] ?? '').toLowerCase();
      return av === bv ? 0 : (av < bv ? -1 : 1) * dir;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / MHUB_PAGE_SIZE));
  const safePage  = Math.min(page, pageCount - 1);
  const start     = safePage * MHUB_PAGE_SIZE;
  const visible   = sorted.slice(start, start + MHUB_PAGE_SIZE);

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('asc'); }
    setPage(0);
  };
  const caret = (key) => (sortKey === key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '');
  const onSearch = (v) => { setQ(v); setPage(0); };

  const COLS = [
    { key: 'description', label: 'Description', align: 'left'  },
    { key: 'quantity',    label: 'Quantity',    align: 'right' },
    { key: 'unit',        label: 'Unit',        align: 'left'  },
  ];

  return (
    <div className="scard vd-rise mhub-grid-card" style={{ marginBottom: 0, animationDelay: '0.08s', padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: '16px', flexWrap: 'wrap', marginBottom: '18px' }}>
        <div>
          <p className="scard-title" style={{ border: 'none', padding: 0, marginBottom: '4px' }}>Measurements</p>
          <p style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.42)' }}>
            {meta?.source ? `${meta.source} · ` : ''}{meta?.file ? `${meta.file} · ` : ''}
            {rows.length.toLocaleString('en-GB')} row{rows.length !== 1 ? 's' : ''}
          </p>
        </div>
        <input
          className="finp"
          type="search"
          placeholder="Search description or unit…"
          value={q}
          onChange={e => onSearch(e.target.value)}
          data-testid="mhub-search"
          style={{ width: '260px', maxWidth: '100%' }}
        />
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="rboq" data-testid="mhub-table">
          <thead>
            <tr>
              {COLS.map(c => (
                <th key={c.key}
                  className={c.align === 'right' ? 'r' : ''}
                  onClick={() => toggleSort(c.key)}
                  data-testid={`mhub-th-${c.key}`}
                  aria-sort={sortKey === c.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  style={{ cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}>
                  {c.label}{caret(c.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr className="rboq-item"><td colSpan={3} style={{ textAlign: 'center', padding: '28px 16px', color: 'rgba(255,255,255,0.45)' }}>
                No measurements match “{q}”.
              </td></tr>
            ) : visible.map((r, i) => (
              <tr key={start + i} className={`rboq-item${(start + i) % 2 === 1 ? ' alt' : ''}`}>
                <td>{r.description}</td>
                <td className="r">{r.quantity == null || r.quantity === '' ? '—' : r.quantity}</td>
                <td>{r.unit || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginTop: '16px' }}>
        <span style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.45)' }} data-testid="mhub-range">
          {sorted.length === 0
            ? 'No results'
            : `Showing ${start + 1}–${start + visible.length} of ${sorted.length.toLocaleString('en-GB')}` +
              (sorted.length !== rows.length ? ` (filtered from ${rows.length.toLocaleString('en-GB')})` : '')}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button className="btn btn-outline btn-pill btn-sm" disabled={safePage <= 0}
            onClick={() => setPage(p => Math.max(0, p - 1))} data-testid="mhub-prev">← Prev</button>
          <span style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.6)' }} data-testid="mhub-page">
            Page {safePage + 1} of {pageCount}
          </span>
          <button className="btn btn-outline btn-pill btn-sm" disabled={safePage >= pageCount - 1}
            onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))} data-testid="mhub-next">Next →</button>
        </div>
      </div>
    </div>
  );
}

// Confidence badge: green ≥80%, amber ≥50%, red below; "Manual" once overridden.
function MhubConfidence({ value, overridden }) {
  if (overridden) {
    return (
      <span style={{
        fontSize: '11px', fontWeight: 700, color: 'var(--amber)',
        border: '1px solid rgba(215,117,85,0.4)', borderRadius: '999px', padding: '2px 9px', whiteSpace: 'nowrap',
      }}>Manual</span>
    );
  }
  const pct = Math.round((Number(value) || 0) * 100);
  const color = pct >= 80 ? '#3fb950' : pct >= 50 ? 'var(--amber)' : '#e26d5c';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '7px' }}>
      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color, flexShrink: 0 }} />
      <span style={{ fontSize: '12.5px', fontVariantNumeric: 'tabular-nums', color: 'rgba(255,255,255,0.75)' }}>{pct}%</span>
    </span>
  );
}

// Classification workflow table: Imported → Normalised → NRM2 Section → Rate Key,
// with a confidence score and per-row manual overrides. Pure display + overrides;
// no AI, no pricing. Paginated so large takeoffs stay responsive.
const MHUB_CLS_PAGE = 50;

function ClassificationTable({ rows, options, overrides, onOverride, onReset, onReclassify, classifying, onGenerateBoq, generating }) {
  const [page, setPage]         = useState(0);
  const [q, setQ]               = useState('');
  const [confidenceFilter, setConfidenceFilter] = useState('all');
  const nrm2Options = (options && options.nrm2_sections) || [];
  const rateKeys    = (options && options.rate_keys) || [];

  const effective = (i, field) => {
    const o = overrides[i];
    return (o && o[field] !== undefined) ? o[field] : (rows[i][field] ?? '');
  };
  const isOverridden = (i) => {
    const o = overrides[i];
    return !!o && (o.nrm2_section !== undefined || o.rate_key !== undefined);
  };

  // Build an indexed array so overrides stay aligned after filtering.
  const indexed = rows.map((r, i) => ({ r, i }));

  const filtered = React.useMemo(() => {
    const term = q.trim().toLowerCase();
    return indexed.filter(({ r, i }) => {
      if (term) {
        const hit = String(r.description ?? '').toLowerCase().includes(term)
          || String(r.normalised_description ?? '').toLowerCase().includes(term);
        if (!hit) return false;
      }
      const pct = (Number(r.confidence) || 0) * 100;
      const section = effective(i, 'nrm2_section');
      if (confidenceFilter === 'high'   && pct < 80)          return false;
      if (confidenceFilter === 'medium' && (pct < 50 || pct >= 80)) return false;
      if (confidenceFilter === 'low'    && pct >= 50)          return false;
      if (confidenceFilter === 'unclassified' && section)      return false;
      return true;
    });
  }, [rows, overrides, q, confidenceFilter]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / MHUB_CLS_PAGE));
  const safePage  = Math.min(page, pageCount - 1);
  const start     = safePage * MHUB_CLS_PAGE;
  const visible   = filtered.slice(start, start + MHUB_CLS_PAGE);

  const onSearch = (v) => { setQ(v); setPage(0); };
  const onFilter = (v) => { setConfidenceFilter(v); setPage(0); };

  const reviewCount    = rows.filter((r, i) => !isOverridden(i) && (Number(r.confidence) || 0) < 0.5).length;
  const unmatchedCount = rows.filter((r, i) => !effective(i, 'nrm2_section')).length;

  const selStyle = {
    background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.14)',
    borderRadius: '6px', color: 'white', fontSize: '12.5px', padding: '5px 7px', maxWidth: '100%', width: '100%',
  };
  const filterSelStyle = {
    background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.14)',
    borderRadius: '999px', color: 'white', fontSize: '12.5px', padding: '5px 14px',
    cursor: 'pointer', outline: 'none', appearance: 'none', WebkitAppearance: 'none',
    paddingRight: '28px',
    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='rgba(255,255,255,0.4)'/%3E%3C/svg%3E")`,
    backgroundRepeat: 'no-repeat', backgroundPosition: 'right 10px center',
  };

  return (
    <div className="scard vd-rise" style={{ marginBottom: 0, padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: '16px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <div>
          <p className="scard-title" style={{ border: 'none', padding: 0, marginBottom: '4px' }}>Classification</p>
          <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', letterSpacing: '0.01em' }}>
            Imported → Normalised → NRM2 Section → Rate Key
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          {reviewCount > 0 && (
            <button
              onClick={() => { setConfidenceFilter('low'); setPage(0); }}
              data-testid="cls-review-trigger"
              style={{
                background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                fontSize: '12.5px', color: '#e26d5c',
                textDecoration: confidenceFilter === 'low' ? 'none' : 'underline',
                textDecorationStyle: 'dotted',
              }}
            >{reviewCount} low-confidence row{reviewCount !== 1 ? 's' : ''} to review</button>
          )}
          {unmatchedCount > 0 && (
            <button
              onClick={() => { setConfidenceFilter('unclassified'); setPage(0); }}
              data-testid="cls-unclassified-trigger"
              style={{
                background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                fontSize: '12.5px', color: '#7c9cfc',
                textDecoration: confidenceFilter === 'unclassified' ? 'none' : 'underline',
                textDecorationStyle: 'dotted',
              }}
            >{unmatchedCount} unclassified row{unmatchedCount !== 1 ? 's' : ''}</button>
          )}
          <button className="btn btn-outline btn-pill btn-sm" onClick={onReclassify} disabled={classifying || generating} data-testid="cls-reclassify">
            {classifying ? 'Classifying…' : 'Re-classify'}
          </button>
          <button
            className="btn btn-amber btn-pill btn-sm"
            onClick={onGenerateBoq}
            disabled={!rows.length || classifying || generating}
            data-testid="cls-generate-boq"
          >
            {generating ? 'Generating…' : 'Generate BoQ →'}
          </button>
        </div>
      </div>

      {/* Search + filter toolbar — mirrors MeasurementGrid layout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '14px' }}>
        <input
          className="finp"
          type="search"
          placeholder="Search description…"
          value={q}
          onChange={e => onSearch(e.target.value)}
          data-testid="cls-search"
          style={{ flex: '1 1 220px', maxWidth: '320px' }}
        />
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <select
            value={confidenceFilter}
            onChange={e => onFilter(e.target.value)}
            data-testid="cls-confidence-filter"
            style={filterSelStyle}
          >
            <option value="all">All</option>
            <option value="high">High Confidence ≥80%</option>
            <option value="medium">Medium Confidence 50–79%</option>
            <option value="low">Low Confidence &lt;50%</option>
            <option value="unclassified">Unclassified</option>
          </select>
        </div>
        {confidenceFilter === 'low' && (
          <span data-testid="cls-review-active" style={{
            fontSize: '12px', fontWeight: 600, color: '#e26d5c',
            background: 'rgba(226,109,92,0.12)', border: '1px solid rgba(226,109,92,0.3)',
            borderRadius: '999px', padding: '3px 10px', whiteSpace: 'nowrap',
          }}>● Review mode</span>
        )}
        {confidenceFilter === 'unclassified' && (
          <span data-testid="cls-unclassified-active" style={{
            fontSize: '12px', fontWeight: 600, color: '#7c9cfc',
            background: 'rgba(124,156,252,0.10)', border: '1px solid rgba(124,156,252,0.28)',
            borderRadius: '999px', padding: '3px 10px', whiteSpace: 'nowrap',
          }}>● Unclassified only</span>
        )}
        {(q || confidenceFilter !== 'all') && (
          <button
            className="btn btn-outline btn-pill btn-sm"
            onClick={() => { setQ(''); setConfidenceFilter('all'); setPage(0); }}
            data-testid="cls-clear-filters"
          >
            {confidenceFilter === 'low' && !q ? 'Clear review filter' : confidenceFilter === 'unclassified' && !q ? 'Clear unclassified filter' : 'Clear'}
          </button>
        )}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="rboq" data-testid="cls-table">
          <thead>
            <tr>
              <th>Imported measurement</th>
              <th>Normalised</th>
              <th style={{ minWidth: '180px' }}>NRM2 Section</th>
              <th style={{ minWidth: '200px' }}>Rate Key</th>
              <th className="r">Confidence</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr className="rboq-item">
                <td colSpan={6} style={{ textAlign: 'center', padding: '28px 16px', color: 'rgba(255,255,255,0.45)' }}>
                  No rows match the current search or filter.
                </td>
              </tr>
            ) : visible.map(({ r, i }, vi) => {
              const overridden = isOverridden(i);
              const unmatched  = !effective(i, 'nrm2_section');
              return (
                <tr key={i}
                  className={`rboq-item${vi % 2 === 1 ? ' alt' : ''}`}
                  data-testid={`cls-row-${i}`}
                  style={unmatched ? { borderLeft: '3px solid rgba(124,156,252,0.6)' } : undefined}
                >
                  <td>
                    <div>{r.description || '—'}</div>
                    <div style={{ fontSize: '11.5px', color: 'rgba(255,255,255,0.4)' }}>
                      {r.quantity == null || r.quantity === '' ? '' : `${r.quantity} `}{r.unit || ''}
                    </div>
                  </td>
                  <td>
                    <div>{r.normalised_description || '—'}</div>
                    {r.normalised_unit ? <div style={{ fontSize: '11.5px', color: 'rgba(255,255,255,0.4)' }}>{r.normalised_unit}</div> : null}
                  </td>
                  <td>
                    <select style={selStyle} value={effective(i, 'nrm2_section') || ''}
                      data-testid={`cls-nrm2-${i}`}
                      onChange={e => onOverride(i, 'nrm2_section', e.target.value || null)}>
                      <option value="">Unclassified</option>
                      {nrm2Options.map(o => <option key={o.code} value={o.code}>{o.code} {o.label}</option>)}
                    </select>
                  </td>
                  <td>
                    <select style={selStyle} value={effective(i, 'rate_key') || ''}
                      data-testid={`cls-ratekey-${i}`}
                      onChange={e => onOverride(i, 'rate_key', e.target.value || null)}>
                      <option value="">— none —</option>
                      {rateKeys.map(k => <option key={k} value={k}>{k}</option>)}
                    </select>
                  </td>
                  <td className="r"><MhubConfidence value={r.confidence} overridden={overridden} /></td>
                  <td className="r">
                    <button onClick={() => onReset(i)} disabled={!overridden} aria-label="Reset row"
                      data-testid={`cls-reset-${i}`}
                      style={{
                        background: 'none', border: 'none', cursor: overridden ? 'pointer' : 'default',
                        color: overridden ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.2)', fontSize: '12px', padding: 0,
                      }}>Reset</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginTop: '16px' }}>
        <span style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.45)' }} data-testid="cls-range">
          {filtered.length === 0
            ? 'No results'
            : `Showing ${start + 1}–${start + visible.length} of ${filtered.length.toLocaleString('en-GB')}` +
              (filtered.length !== rows.length ? ` (filtered from ${rows.length.toLocaleString('en-GB')})` : '')}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button className="btn btn-outline btn-pill btn-sm" disabled={safePage <= 0} onClick={() => setPage(p => Math.max(0, p - 1))} data-testid="cls-prev">← Prev</button>
          <span style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.6)' }} data-testid="cls-page">Page {safePage + 1} of {pageCount}</span>
          <button className="btn btn-outline btn-pill btn-sm" disabled={safePage >= pageCount - 1} onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))} data-testid="cls-next">Next →</button>
        </div>
      </div>
    </div>
  );
}

function MeasurementHubPage({ go, toast, onBoqReady }) {
  // Per-source picked File (drives the filename chip). Picking a file also kicks
  // off an import to POST /measurement/import, whose parsed rows populate the grid.
  const [tab, setTab]             = useState('measurements');
  const [files, setFiles]         = useState({});
  const [measurements, setMeasurements] = useState(null);   // null until first successful import
  const [activeMeta, setActiveMeta]     = useState(null);   // { source, file }
  const [importId, setImportId]   = useState(0);            // bumps to remount the grid (resets sort/search/page)
  const [importing, setImporting] = useState(null);         // source id currently importing
  const [importError, setImportError]   = useState(null);

  // Classification state lives here so it persists across tab switches and only
  // recomputes when a new dataset is imported (tracked via importId).
  const [classification, setClassification] = useState({ forImportId: -1, rows: null, options: null });
  const [classifying, setClassifying]       = useState(false);
  const [classifyError, setClassifyError]   = useState(null);
  const [overrides, setOverrides]           = useState({});
  const [generating, setGenerating]         = useState(false);
  const [generatedBoq, setGeneratedBoq]     = useState(null);
  const inputRefs = useRef({});

  const openPicker = (id) => { inputRefs.current[id] && inputRefs.current[id].click(); };

  // Fire-and-forget: persist a user classification override to the backend.
  // Called after every NRM2 / rate-key dropdown change.
  const persistOverride = async (sourceTerm, nrm2Section, rateKey) => {
    if (!sourceTerm) return;
    try {
      const token = await vqToken();
      if (!token) return;
      fetch(`${VQ_API}/measurement/overrides`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ source_term: sourceTerm, nrm2_section: nrm2Section || null, rate_key: rateKey || null }),
      });
    } catch (_) {}
  };

  // Fire-and-forget: delete a user override when the row is reset.
  const deletePersistedOverride = async (sourceTerm) => {
    if (!sourceTerm) return;
    try {
      const token = await vqToken();
      if (!token) return;
      fetch(`${VQ_API}/measurement/overrides`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ source_term: sourceTerm }),
      });
    } catch (_) {}
  };

  const runClassify = async () => {
    if (!measurements || !measurements.length) return;
    setClassifying(true);
    setClassifyError(null);
    try {
      const token = await vqToken();
      const res  = await fetch(`${VQ_API}/measurement/classify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ measurements }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = data.error || 'Classification failed — please try again.';
        setClassifyError(msg); toast(msg, 'error'); return;
      }
      const classified = data.classified || [];
      // Seed local override state from server-applied user_override rows so the
      // "Manual" confidence badge renders correctly without another round-trip.
      const seeded = {};
      classified.forEach((r, i) => {
        if (r.overridden) seeded[i] = { nrm2_section: r.nrm2_section, rate_key: r.rate_key };
      });
      setClassification({ forImportId: importId, rows: classified, options: data.options || { nrm2_sections: [], rate_keys: [] } });
      setOverrides(seeded);
    } catch (e) {
      const msg = 'Network error — could not reach the server.';
      setClassifyError(msg); toast(msg, 'error');
    } finally {
      setClassifying(false);
    }
  };

  const runGenerateBoq = async () => {
    if (!classification.rows || !classification.rows.length) return;
    setGenerating(true);
    try {
      const token = await vqToken();
      const effective = classification.rows.map((r, i) => {
        const o = overrides[i] || {};
        return { ...r, ...(o.nrm2_section !== undefined ? { nrm2_section: o.nrm2_section } : {}), ...(o.rate_key !== undefined ? { rate_key: o.rate_key } : {}) };
      });
      const res = await fetch(`${VQ_API}/measurement/generate-boq`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ classified_measurements: effective }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast(data.error || 'BoQ generation failed — please try again.', 'error');
        return;
      }
      setGeneratedBoq(data.boq_data);
      if (onBoqReady) onBoqReady(data.boq_data);
      toast('BoQ generated — opening Results…', 'success');
      setTimeout(() => go('results'), 600);
    } catch (e) {
      toast('Network error — could not reach the server.', 'error');
    } finally {
      setGenerating(false);
    }
  };

  // Auto-classify when the Classification tab is opened with a dataset that hasn't
  // been classified yet (or after a fresh import changed importId).
  useEffect(() => {
    if (tab === 'classification' && measurements && measurements.length
        && classification.forImportId !== importId && !classifying) {
      runClassify();
    }
  }, [tab, importId, measurements]);

  const setOverride = (idx, field, value) => {
    setOverrides(prev => ({ ...prev, [idx]: { ...(prev[idx] || {}), [field]: value } }));
    const row = (classification.rows || [])[idx];
    if (row) {
      // Read prev overrides synchronously (captured in closure — correct before state flush).
      const prev = overrides[idx] || {};
      const nrm2 = field === 'nrm2_section' ? (value || null) : (prev.nrm2_section !== undefined ? prev.nrm2_section : (row.nrm2_section || null));
      const rkey = field === 'rate_key'     ? (value || null) : (prev.rate_key     !== undefined ? prev.rate_key     : (row.rate_key     || null));
      persistOverride(row.normalised_description, nrm2, rkey);
    }
  };
  const resetOverride = (idx) => {
    const row = (classification.rows || [])[idx];
    if (row) deletePersistedOverride(row.normalised_description);
    setOverrides(prev => { const next = { ...prev }; delete next[idx]; return next; });
  };

  const runImport = async (source, file) => {
    setImporting(source.id);
    setImportError(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res  = await fetch(`${VQ_API}/measurement/import`, { method: 'POST', body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = data.error || 'Import failed — please check the file and try again.';
        setImportError(msg);
        toast(msg, 'error');
        return;
      }
      const parsed = Array.isArray(data.measurements) ? data.measurements : [];
      setMeasurements(parsed);
      setActiveMeta({ source: source.name, file: file.name });
      setImportId(n => n + 1);   // fresh grid state for the new dataset
      toast(`Imported ${parsed.length} measurement${parsed.length !== 1 ? 's' : ''}.`, 'success');
    } catch (e) {
      const msg = 'Network error — could not reach the server.';
      setImportError(msg);
      toast(msg, 'error');
    } finally {
      setImporting(null);
    }
  };

  const handlePick = (id, fileList) => {
    const file = fileList && fileList[0];
    if (!file) return;
    setFiles(prev => ({ ...prev, [id]: file }));
    const source = MHUB_SOURCES.find(s => s.id === id);
    if (source) runImport(source, file);
  };

  const clearFile = (id) => setFiles(prev => {
    const next = { ...prev };
    delete next[id];
    return next;
  });

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="measurehub" go={go} toast={toast} />
      <main className="app-main dash-main">
        <VQParticleField />
        <div className="dash-hd">
          <h1 className="dash-h1">Bluebeam Measurement Hub</h1>
        </div>
        <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.42)', marginTop: '-20px', marginBottom: '20px' }}>
          Bring measurements from Bluebeam and on-screen takeoff into your Bills of Quantities.
        </p>

        {/* Workspace tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.08)', marginBottom: '24px' }}>
          {[{ id: 'measurements', label: 'Measurements' }, { id: 'classification', label: 'Classification' }].map(tb => (
            <button key={tb.id} onClick={() => setTab(tb.id)} data-testid={`mhub-tab-${tb.id}`}
              style={{
                background: 'none', border: 'none', outline: 'none',
                borderBottom: `2px solid ${tab === tb.id ? 'var(--amber)' : 'transparent'}`,
                color: tab === tb.id ? 'white' : 'rgba(255,255,255,0.45)',
                padding: '8px 20px 14px', fontSize: '14px', fontWeight: tab === tb.id ? 600 : 500,
                cursor: 'pointer', marginBottom: '-1px', fontFamily: 'var(--font-b)',
              }}>{tb.label}</button>
          ))}
        </div>

        {tab === 'measurements' && (
        <div className="mhub-grid">

          {/* Left panel — Measurement Sources (one glass card per source) */}
          <div className="vd-rise" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <p style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'rgba(255,255,255,0.4)' }}>
              Measurement Sources
            </p>
            {MHUB_SOURCES.map(s => {
              const picked = files[s.id];
              return (
                <div key={s.id} className="scard" style={{ marginBottom: 0, padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
                    <div style={{
                      width: '38px', height: '38px', borderRadius: '10px', flexShrink: 0,
                      background: 'rgba(215,117,85,0.12)', border: '1px solid rgba(215,117,85,0.25)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--amber)',
                    }}>
                      {s.icon}
                    </div>
                    <p style={{ fontSize: '14px', fontWeight: 600, color: 'white' }}>{s.name}</p>
                  </div>
                  <p style={{ fontSize: '12.5px', lineHeight: 1.5, color: 'rgba(255,255,255,0.42)', marginBottom: '14px' }}>{s.desc}</p>

                  <input
                    ref={el => { inputRefs.current[s.id] = el; }}
                    type="file"
                    accept={s.accept || undefined}
                    style={{ display: 'none' }}
                    data-testid={`mhub-input-${s.id}`}
                    onChange={e => { handlePick(s.id, e.target.files); e.target.value = ''; }}
                  />
                  <button className="btn btn-outline btn-pill btn-sm" onClick={() => openPicker(s.id)} disabled={importing === s.id}>
                    {importing === s.id ? 'Importing…' : (picked ? 'Replace file' : 'Import')}
                  </button>

                  {picked && (
                    <div style={{
                      marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px',
                      background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: '8px', padding: '8px 10px',
                    }}>
                      <span style={{ color: 'var(--amber)', flexShrink: 0, display: 'flex' }}>{MHUB_ICON.file}</span>
                      <span title={picked.name} style={{
                        fontSize: '12.5px', color: 'rgba(255,255,255,0.8)', flex: 1, minWidth: 0,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>{picked.name}</span>
                      <button onClick={() => clearFile(s.id)} aria-label="Remove file" style={{
                        background: 'none', border: 'none', color: 'rgba(255,255,255,0.4)',
                        cursor: 'pointer', fontSize: '16px', lineHeight: 1, padding: 0, flexShrink: 0,
                      }}>×</button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Main area — measurement grid once imported, otherwise empty workspace */}
          {measurements ? (
            <MeasurementGrid key={importId} rows={measurements} meta={activeMeta} />
          ) : (
            <div className="empty-state vd-rise" style={{ animationDelay: '0.08s' }}>
              <div className="empty-icon">📐</div>
              <p className="empty-h">No measurements yet</p>
              <p className="empty-p">
                Import a Bluebeam CSV/XLSX or an Excel takeoff from the panel on the
                left. Parsed measurements will appear here in a sortable, searchable grid.
              </p>
              {importError && (
                <p style={{ fontSize: '13px', color: 'var(--red, #e26d5c)', marginTop: '4px' }}>{importError}</p>
              )}
            </div>
          )}

          {/* Right panel — Details */}
          <div className="scard vd-rise mhub-details" style={{ marginBottom: 0, animationDelay: '0.16s' }}>
            <p className="scard-title">Details</p>
            <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.42)', marginBottom: '16px', lineHeight: 1.55 }}>
              Select a measurement in the workspace to see its properties here.
            </p>
            {MHUB_DETAIL_ROWS.map(([label, value]) => (
              <div key={label} style={{
                display: 'flex', justifyContent: 'space-between', gap: '12px',
                padding: '9px 0', borderBottom: '1px solid rgba(255,255,255,0.06)',
              }}>
                <span style={{ fontSize: '12.5px', color: 'rgba(255,255,255,0.45)' }}>{label}</span>
                <span style={{ fontSize: '12.5px', fontWeight: 600, color: 'rgba(255,255,255,0.7)' }}>{value}</span>
              </div>
            ))}
          </div>

        </div>
        )}

        {tab === 'classification' && (
          (!measurements || !measurements.length) ? (
            <div className="empty-state vd-rise">
              <div className="empty-icon">🏷️</div>
              <p className="empty-h">Nothing to classify yet</p>
              <p className="empty-p">
                Import measurements on the Measurements tab first. Each row is then
                normalised and mapped to an NRM2 section and rate key, with a
                confidence score you can override.
              </p>
              <button className="btn btn-outline btn-pill" onClick={() => setTab('measurements')}>
                Go to Measurements
              </button>
            </div>
          ) : classifyError && !classification.rows ? (
            <div className="empty-state vd-rise">
              <div className="empty-icon">⚠️</div>
              <p className="empty-h">Classification failed</p>
              <p className="empty-p">{classifyError}</p>
              <button className="btn btn-outline btn-pill" onClick={runClassify}>Try again</button>
            </div>
          ) : !classification.rows || classification.forImportId !== importId ? (
            <div className="empty-state vd-rise">
              <div className="empty-icon">⏳</div>
              <p className="empty-h">Classifying measurements…</p>
              <p className="empty-p">Normalising rows and mapping them to NRM2 sections and rate keys.</p>
            </div>
          ) : (
            <ClassificationTable
              rows={classification.rows}
              options={classification.options}
              overrides={overrides}
              onOverride={setOverride}
              onReset={resetOverride}
              onReclassify={runClassify}
              classifying={classifying}
              onGenerateBoq={runGenerateBoq}
              generating={generating}
            />
          )
        )}
      </main>
    </div>
  );
}

// ─── PUBLIC DEMO ──────────────────────────────────────────────────────────────────
// Interactive demo at /demo — no account required. Posts to the unauthenticated
// /demo-process endpoint and renders the restricted preview via ResultsPage demo mode.
const VQ_DEMO_SAMPLES = [
  { name: 'Domestic Extension',  desc: 'Single-storey rear extension with new kitchen, wetroom and pitched roof.' },
  { name: 'Commercial Fit-Out',  desc: 'Office unit fit-out: partitions, suspended ceilings, M&E and finishes.' },
  { name: 'Groundworks Package', desc: 'Reduced-level dig, foundations, drainage runs and external paving.' },
];

function DemoPage({ go, toast }) {
  const [sample, setSample]     = useState(VQ_DEMO_SAMPLES[0].name);
  const [file, setFile]         = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [status, setStatus]     = useState('idle');   // idle | processing | done
  const [demoBoq, setDemoBoq]   = useState(null);

  const acceptFile = f => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.pdf')) { toast('Only PDF files are accepted.', 'error'); return; }
    setFile(f);
    setDemoBoq(null);
    setStatus('idle');
  };

  const handleGenerate = async () => {
    if (status === 'processing') return;
    if (!file) { toast('Select a PDF drawing package first.', 'error'); return; }

    console.log('Demo started');
    setStatus('processing');
    setDemoBoq(null);

    // Demo runs the same heavy Claude pipeline as /process, so it needs the same
    // abort-on-hang protection (the public path has no auth, hence no 401 branch).
    const timer = vqAbortTimer();
    try {
      const formData = new FormData();
      formData.append('file', file);                 // same field name Flask expects in /demo-process
      formData.append('sample_project', sample);     // which sample card the visitor picked

      const res = await fetch(`${VQ_API}/demo-process`, { method: 'POST', body: formData, signal: timer.signal });
      timer.clear();

      if (res.status === 429) {
        const err = await res.json().catch(() => ({}));
        console.log('Demo blocked by rate limit');
        toast(err.error || 'Demo limit reached. Please create a free account to continue.', 'error');
        setStatus('idle');
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        toast(err.error || 'Demo failed — please try again.', 'error');
        setStatus('idle');
        return;
      }

      const data = await res.json();
      console.log('Demo completed');
      setDemoBoq(data);
      setStatus('done');
    } catch (err) {
      // Same abort/network/other differentiation + structured logging as the
      // authenticated upload flows.
      timer.clear();
      console.error('[VQ] /demo-process failed:', err);
      toast(vqUploadErrorMessage(err), 'error');
      setStatus('idle');
    }
  };

  return (
    <div style={{ background: '#1d2127', minHeight: '100vh', paddingBottom: '120px' }}>
      <VQParticleField />
      <div style={{ position: 'relative', zIndex: 1 }}>

        {/* Hero */}
        <div style={{ padding: '120px 0 48px' }}>
          <div className="inner" style={{ textAlign: 'center' }}>
            <h1 className="display-xl" style={{ color: 'white', marginBottom: '20px' }}>Try Vulcan Quanta</h1>
            <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '19px', maxWidth: '520px', margin: '0 auto' }}>
              Upload a sample drawing package and receive a preview of a Bill of Quantities.
            </p>
          </div>
        </div>

        <div className="inner" style={{ maxWidth: '960px' }}>

          {/* Sample project cards */}
          <p style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'rgba(255,255,255,0.4)', marginBottom: '14px' }}>1 · Choose a sample project type</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '40px' }}>
            {VQ_DEMO_SAMPLES.map(s => {
              const active = sample === s.name;
              return (
                <div key={s.name} onClick={() => setSample(s.name)}
                  style={{
                    cursor: 'pointer', borderRadius: '12px', padding: '24px',
                    background: active ? 'rgba(215,117,85,0.10)' : 'rgba(29,33,39,0.6)',
                    border: `1px solid ${active ? 'var(--amber)' : 'rgba(255,255,255,0.08)'}`,
                    transition: 'border-color var(--t), background var(--t)',
                  }}>
                  <p style={{ fontFamily: 'var(--font-d)', fontSize: '17px', fontWeight: 700, color: 'white', marginBottom: '8px' }}>{s.name}</p>
                  <p style={{ fontSize: '13px', lineHeight: 1.5, color: 'rgba(255,255,255,0.45)' }}>{s.desc}</p>
                  {active && <p style={{ marginTop: '12px', fontSize: '12px', fontWeight: 600, color: 'var(--amber)' }}>✓ Selected</p>}
                </div>
              );
            })}
          </div>

          {/* Upload area */}
          <p style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'rgba(255,255,255,0.4)', marginBottom: '14px' }}>2 · Upload a drawing package (PDF)</p>
          <div
            className={`upload-zone${dragOver ? ' drag' : ''}`}
            style={{ padding: '48px 40px', marginBottom: '24px' }}
            onDrop={e => { e.preventDefault(); setDragOver(false); acceptFile(e.dataTransfer.files[0]); }}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onClick={() => document.getElementById('vq-demo-file-input').click()}
          >
            <p className="upload-h">{file ? file.name : 'Drop your drawing here'}</p>
            <p className="upload-sub">{file ? 'Ready to generate — or drop a different PDF' : 'or click to select a PDF file'}</p>
            <input id="vq-demo-file-input" type="file" accept=".pdf" style={{ display: 'none' }}
              onChange={e => { acceptFile(e.target.files[0]); e.target.value = ''; }} />
          </div>

          {/* Generate */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <button className="btn btn-amber btn-pill" onClick={handleGenerate} disabled={status === 'processing'}>
              {status === 'processing' ? '⏳ Generating preview…' : 'Generate Preview'}
            </button>
            {status === 'processing' && <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.45)' }}>AI is reading your drawing — this takes about a minute.</span>}
          </div>

          {/* Restricted preview */}
          {demoBoq && (
            <>
              <div style={{
                margin: '48px 0 0', padding: '14px 18px', borderRadius: '10px',
                border: '1px solid rgba(215,117,85,0.45)', background: 'rgba(215,117,85,0.12)',
                color: 'white', fontSize: '14px', display: 'flex', justifyContent: 'space-between',
                alignItems: 'center', gap: '16px', flexWrap: 'wrap',
              }}>
                <span><strong>Demo Preview</strong> — Create a free account to unlock full NRM2 output and exports.</span>
                <button className="btn btn-amber btn-pill" onClick={() => go('signup')}>Create free account</button>
              </div>
              <ResultsPage embedded demo boqData={demoBoq} go={go} toast={toast} />
            </>
          )}

        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  LandingPage, ResultsPage, DashboardPage, UploadPage, SettingsPage,
  ProjectSetupPage, ProjectWorkspacePage, ProjectSettingsPage,
  ProjectsPage, ReportsPage, ExportsPage, HistoryPage,
  SignUpPage, SignInPage, PricingPage,
  ForgotPasswordPage, CheckEmailPage, ResetPasswordPage,
  DemoPage, MeasurementHubPage,
});
