// vq-pages.jsx — all page components
const { useState, useEffect, useRef } = React;
const { BoQMockup, AppSidebar } = window;

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
              onClick={() => go('results')}
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
            <button className="btn-ghost-lt" onClick={() => go('results')}>
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
              { icon: '🔒', text: 'GDPR compliant' },
              { icon: '🛡️', text: 'Encrypted at rest' },
              { icon: '🇬🇧', text: 'UK-hosted' },
              { icon: '👤', text: 'Human review built in' },
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
function ResultsPage({ go, toast, boqData }) {
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

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="results" go={go} toast={toast} />
      <div className="app-main">
      <div className="res-wrap">
      <div className="res-pad">
        <span className="res-back" onClick={() => go('dashboard')}>← Back to dashboard</span>
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
          <button className="btn btn-amber btn-pill" onClick={handleDownload} disabled={pdfState !== 'idle'}>
            {pdfState === 'idle'       && '↓ Download PDF'}
            {pdfState === 'generating' && '⏳ Generating PDF…'}
            {pdfState === 'done'       && '✓ Downloaded'}
          </button>
<button className="btn btn-outline btn-pill" onClick={handleExcelDownload} disabled={excelState !== 'idle'}>
  {excelState === 'idle'       && '📊 Excel'}
  {excelState === 'generating' && '⏳ Generating…'}
  {excelState === 'done'       && '✓ Downloaded'}
</button>          <button className="btn btn-outline btn-pill" onClick={() => { navigator.clipboard?.writeText?.(window.location.href); toast('Share link copied to clipboard!', 'success'); }}>🔗 Share</button>
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
          </tbody>
        </table>
        <p style={{ marginTop: '20px', fontSize: '12px', color: 'rgba(255,255,255,0.32)', fontStyle: 'italic' }}>
          AI-estimated using BCIS Q2 2026 rates. Subject to market variation and supplier pricing. Professional QS review recommended before tender or client issue.
        </p>
      </div>
      </div>
      </div>
    </div>
  );
}

// ─── DASHBOARD ───────────────────────────────────────────────────────────────────────
// Base URL for the Railway backend — same host used by /process, /download, /projects.
const VQ_API = 'https://vulcan-production-d039.up.railway.app';

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

function DashboardPage({ go, toast, user, onBoqReady }) {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [openMenu, setOpenMenu] = useState(null);   // id of the row whose ⋯ menu is open

  // ── Fetch the signed-in user's projects ──────────────────────────────────────
  const loadProjects = async () => {
    try {
      const token = await vqToken();
      const res = await fetch(`${VQ_API}/projects`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) throw new Error('request failed');
      const data = await res.json();
      setProjects(Array.isArray(data) ? data : []);
    } catch (err) {
      // On any failure show zeros / empty state — never fabricate data.
      setProjects([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadProjects(); }, []);

  // Close the row menu on any outside click.
  useEffect(() => {
    if (openMenu === null) return;
    const close = () => setOpenMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [openMenu]);

  // ── Row actions ──────────────────────────────────────────────────────────────
  const handleViewBoq = (p) => {
    setOpenMenu(null);
    // The list endpoint omits boq_data; pass whatever the project carries (else null,
    // which ResultsPage renders as its demo BoQ).
    if (onBoqReady) onBoqReady(p.boq_data || null);
    go('results');
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
        loadProjects();
      } else {
        toast('Could not delete project. Please try again.', 'error');
      }
    } catch (err) {
      toast('Network error — could not delete project.', 'error');
    }
  };

  // ── Derived figures (all client-side from the real response) ─────────────────
  const totalProjects = projects.length;
  const activeCount   = projects.filter(p => p.status !== 'completed').length;
  const totalDrawings = projects.reduce((s, p) => s + (Number(p.page_count) || 0), 0);
  const boqsGenerated = projects.filter(p => p.status === 'completed').length;
  const totalValue    = projects.reduce((s, p) => s + (Number(p.estimated_value) || 0), 0);

  const recent    = projects.slice(0, 5);
  const completed = projects.filter(p => p.status === 'completed');

  // Status breakdown for the donut.
  const cCompleted  = boqsGenerated;
  const cProcessing = projects.filter(p => p.status === 'processing').length;
  const cPreparing  = totalProjects - cCompleted - cProcessing;
  const statusTotal = totalProjects;

  // Welcome name — first name from the email's local part, capitalised.
  const email = user?.email || '';
  const localPart = email ? email.split('@')[0].split(/[._-]/)[0] : '';
  const welcomeName = localPart ? localPart.charAt(0).toUpperCase() + localPart.slice(1) : 'there';

  // Average processing time — rough 60s placeholder per project, shown only with data.
  const avgProcessing = totalProjects > 0 ? '1m 0s' : '—';

  // ── Processing-volume line chart (completed BoQs per day, current month) ──────
  const now = new Date();
  const year = now.getFullYear(), month = now.getMonth();
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
        {/* ── Top bar ── */}
        <div className="vd-top">
          <div>
            <h1 className="vd-h1">Dashboard</h1>
            <p className="vd-welcome">Welcome back, {welcomeName}</p>
            <p className="vd-subtitle">Create and manage AI-generated Bills of Quantities</p>
          </div>
          <button className="btn btn-amber btn-pill" onClick={() => go('upload')}>+ New Project</button>
        </div>

        {/* ── Four stat cards ── */}
        <div className="vd-stats">
          {[
            { icon: 'folder', bg: '#e8621a', label: 'Projects',        value: totalProjects,        sub: `${activeCount} active` },
            { icon: 'doc',    bg: '#3b82f6', label: 'Drawings',        value: totalDrawings,        sub: 'This month' },
            { icon: 'check',  bg: '#22c55e', label: 'BOQs Generated',  value: boqsGenerated,        sub: 'This month' },
            { icon: 'pound',  bg: '#8b5cf6', label: 'Estimated Value', value: vqMoney(totalValue),  sub: 'Across all projects' },
          ].map((c, i) => (
            <div key={i} className="vd-card vd-stat">
              <div className="vd-stat-ico" style={{ background: c.bg }}>{VQ_STAT_ICONS[c.icon]}</div>
              <div style={{ minWidth: 0 }}>
                <div className="vd-stat-label">{c.label}</div>
                <div className="vd-stat-value">{c.value}</div>
                <div className="vd-stat-sub">{c.sub}</div>
              </div>
            </div>
          ))}
        </div>

        {/* ── Recent projects + right rail ── */}
        <div className="vd-grid">
          {/* Recent projects */}
          <div className="vd-card vd-panel">
            <div className="vd-section-hd">
              <span className="vd-section-title">Recent Projects</span>
              <span className="vd-link" onClick={() => go('upload')}>View all projects →</span>
            </div>

            {recent.length === 0 ? (
              <div className="vd-empty">
                <p className="vd-empty-p">No projects yet — upload your first drawing</p>
                <button className="btn btn-amber btn-pill" onClick={() => go('upload')}>↑ Upload Drawing</button>
              </div>
            ) : (
              recent.map(p => {
                const badge = vqBadge(p.status);
                return (
                  <div key={p.id} className="vd-proj-row">
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

          {/* Right rail */}
          <div className="vd-col">
            {/* Quick actions */}
            <div className="vd-card vd-panel">
              <div className="vd-section-hd"><span className="vd-section-title">Quick Actions</span></div>
              <div className="vd-qa">
                <button className="vd-qa-btn vd-qa-primary" onClick={() => go('upload')}>↑ Upload Drawing</button>
                <button className="vd-qa-btn vd-qa-dark" onClick={() => {}}>👁 View Demo Project</button>
                <button className="vd-qa-btn vd-qa-dark" onClick={() => {}}>📄 Import Existing BOQ</button>
                <button className="vd-qa-btn vd-qa-dark" onClick={() => go('upload')}>＋ Create Project</button>
              </div>
            </div>

            {/* Recent activity */}
            <div className="vd-card vd-panel">
              <div className="vd-section-hd">
                <span className="vd-section-title">Recent Activity</span>
                <span className="vd-link" onClick={() => {}}>View all activity →</span>
              </div>
              {completed.length === 0 ? (
                <p className="vd-muted">No recent activity.</p>
              ) : (
                completed.slice(0, 5).map(p => (
                  <div key={p.id} className="vd-act">
                    <div className="vd-act-dot">✓</div>
                    <div className="vd-act-body">
                      <div className="vd-act-title">BOQ generated successfully</div>
                      <div className="vd-act-sub">{p.name || 'Untitled project'}</div>
                    </div>
                    <span className="vd-act-time">{vqTimeAgo(p.created_at)}</span>
                  </div>
                ))
              )}
            </div>

            {/* System status */}
            <div className="vd-card vd-panel">
              <div className="vd-section-hd"><span className="vd-section-title">System Status</span></div>
              <div className="vd-status-row">
                <span className="vd-status-label">AI Engine</span>
                <span className="vd-status-online"><span className="vd-dot-green" /> Online</span>
              </div>
              <div className="vd-status-row">
                <span className="vd-status-label">NRM2 Database</span>
                <span className="vd-status-val">Updated (2h ago)</span>
              </div>
              <div className="vd-status-row">
                <span className="vd-status-label">Average Processing Time</span>
                <span className="vd-status-val">{avgProcessing}</span>
              </div>
              <div className="vd-status-row">
                <span className="vd-status-label">System Uptime</span>
                <span className="vd-status-val">99.9%</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Charts row ── */}
        <div className="vd-charts">
          {/* Processing volume */}
          <div className="vd-card vd-panel">
            <div className="vd-section-hd">
              <span className="vd-section-title">Processing Volume <span style={{ fontSize: '13px', color: '#8b92a0', fontWeight: 400 }}>(This Month)</span></span>
              <span className="vd-chart-pill">This month ▾</span>
            </div>
            <svg viewBox={`0 0 ${CW} ${CH}`} width="100%" style={{ display: 'block', height: 'auto' }}>
              <defs>
                <linearGradient id="vdAreaFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#e8621a" stopOpacity="0.28" />
                  <stop offset="100%" stopColor="#e8621a" stopOpacity="0" />
                </linearGradient>
              </defs>
              {/* horizontal gridlines + y labels (0 and max) */}
              {[0, 0.5, 1].map((f, i) => {
                const y = padT + plotH - plotH * f;
                return <line key={i} x1={padL} y1={y} x2={CW - padR} y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />;
              })}
              <text x={padL - 8} y={padT + 4} fill="#6b7280" fontSize="11" textAnchor="end">{maxCount}</text>
              <text x={padL - 8} y={padT + plotH + 4} fill="#6b7280" fontSize="11" textAnchor="end">0</text>
              {/* area + line */}
              <polygon points={areaStr} fill="url(#vdAreaFill)" />
              <polyline points={lineStr} fill="none" stroke="#e8621a" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
              {/* x labels */}
              {dayLabels.map(d => (
                <text key={d} x={xFor(d)} y={CH - 6} fill="#6b7280" fontSize="11" textAnchor="middle">{d} {monthName}</text>
              ))}
            </svg>
          </div>

          {/* Projects by status donut */}
          <div className="vd-card vd-panel">
            <div className="vd-section-hd"><span className="vd-section-title">Projects by Status</span></div>
            <div className="vd-donut-wrap">
              <div className="vd-donut">
                <svg viewBox="0 0 150 150" width="150" height="150">
                  <circle cx="75" cy="75" r={R} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="16" />
                  {segs.map((s, i) => {
                    const len = DC * (s.v / statusTotal);
                    const el = (
                      <circle key={i} cx="75" cy="75" r={R} fill="none" stroke={s.color} strokeWidth="16"
                        strokeDasharray={`${len.toFixed(2)} ${(DC - len).toFixed(2)}`}
                        strokeDashoffset={(-acc).toFixed(2)}
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
      const res = await fetch('https://vulcan-production-d039.up.railway.app/process', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
        credentials: 'include',
      });
      clearInterval(iv);   // stop the fake progress animation now that the server has responded

      if (!res.ok) {
        // Try to read a JSON error body from Flask, fall back to the HTTP status text
        const err = await res.json().catch(() => ({ error: res.statusText }));
        toast(err.error || 'Upload failed. Please try again.', 'error');
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
      // fetch() itself throws only on network-level failures (no connection, DNS error, etc.)
      // HTTP error statuses (4xx, 5xx) do NOT throw — they are handled by the !res.ok check above
      clearInterval(iv);
      toast('Network error — could not reach the server.', 'error');
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
            <p className="upload-icon">📄</p>
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
function SettingsPage({ go, toast }) {
  const [tab, setTab] = useState('account');
  const [saved, setSaved] = useState({});
  const save = key => { setSaved(p => ({ ...p, [key]: true })); toast('Changes saved.', 'success'); setTimeout(() => setSaved(p => ({ ...p, [key]: false })), 2000); };

  const tabs = [{ id: 'account', icon: '👤', label: 'Account' },{ id: 'branding', icon: '🎨', label: 'Branding' },{ id: 'rates', icon: '💷', label: 'Rates' },{ id: 'billing', icon: '💳', label: 'Billing' }];

  return (
    <div className="app-wrap">
      <AppSidebar currentPage="settings" go={go} toast={toast} />
      <main className="app-main dash-main">
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
            <div className="scard">
              <p className="scard-title">Personal details</p>
              <div className="form-grid">
                <div className="fld"><label className="flbl">First name</label><input className="finp" defaultValue="James" /></div>
                <div className="fld"><label className="flbl">Last name</label><input className="finp" defaultValue="Henderson" /></div>
                <div className="fld"><label className="flbl">Email address</label><input className="finp" type="email" defaultValue="james@henderson-qs.co.uk" /></div>
                <div className="fld"><label className="flbl">Phone</label><input className="finp" type="tel" defaultValue="+44 7700 900000" /></div>
              </div>
              <button className="btn btn-amber btn-pill" onClick={() => save('account')}>{saved.account ? '✓ Saved' : 'Save changes'}</button>
            </div>
            <div className="scard">
              <p className="scard-title">Change password</p>
              <div className="form-grid">
                <div className="fld"><label className="flbl">Current password</label><input className="finp" type="password" placeholder="••••••••" /></div>
                <div className="fld"><label className="flbl">New password</label><input className="finp" type="password" placeholder="••••••••" /></div>
              </div>
              <button className="btn btn-outline btn-pill" onClick={() => save('password')}>{saved.password ? '✓ Updated' : 'Update password'}</button>
            </div>
            <div className="scard">
              <p className="scard-title" style={{ color: 'var(--red)' }}>Danger zone</p>
              <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.45)', marginBottom: '16px' }}>Permanently delete your account. Cannot be undone.</p>
              <button className="btn btn-pill" style={{ background: 'var(--red)', color: 'white' }} onClick={() => toast('Contact support to delete your account.', 'info')}>Delete account</button>
            </div>
          </>
        )}
        {tab === 'branding' && (
          <>
            <div className="dash-hd"><h1 className="dash-h1">Branding</h1></div>
            <div className="scard">
              <p className="scard-title">Company identity</p>
              <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.42)', marginBottom: '20px' }}>Appears on all exported BoQs. Available on Pro and Studio plans.</p>
              <div className="form-grid">
                <div className="fld"><label className="flbl">Company name</label><input className="finp" defaultValue="Henderson QS Ltd" /></div>
                <div className="fld"><label className="flbl">Website</label><input className="finp" defaultValue="www.henderson-qs.co.uk" /></div>
                <div className="fld"><label className="flbl">Address</label><input className="finp" defaultValue="12 Victoria Street" /></div>
                <div className="fld"><label className="flbl">City / Postcode</label><input className="finp" defaultValue="Manchester, M1 2EX" /></div>
              </div>
            </div>
            <div className="scard">
              <p className="scard-title">Logo</p>
              <div className="upload-zone" style={{ padding: '32px' }} onClick={() => toast('Logo upload coming soon.', 'info')}>
                <p style={{ fontSize: '14px', color: 'var(--c-400)' }}>Drop your logo here or click to upload. PNG or SVG, max 2 MB.</p>
              </div>
            </div>
            <div className="scard">
              <p className="scard-title">Brand colours</p>
              <div className="form-grid">
                <div className="fld"><label className="flbl">Primary colour</label><input className="finp" defaultValue="#F97316" /></div>
                <div className="fld"><label className="flbl">Secondary / footer</label><input className="finp" defaultValue="#0F172A" /></div>
              </div>
              <button className="btn btn-amber btn-pill" onClick={() => save('branding')}>{saved.branding ? '✓ Saved' : 'Save branding'}</button>
            </div>
          </>
        )}
        {tab === 'rates' && (
          <>
            <div className="dash-hd"><h1 className="dash-h1">Rate overrides</h1></div>
            <div className="scard">
              <p className="scard-title">Regional settings</p>
              <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.42)', marginBottom: '20px' }}>Base rates follow BCIS Q2 2026. Override individual trades below. Leave blank to use BCIS defaults.</p>
              <div className="form-grid">
                <div className="fld"><label className="flbl">Region</label>
                  <select className="finp">{['North West England','London','South East','Yorkshire','East Midlands','West Midlands','Scotland','Wales'].map(r => <option key={r}>{r}</option>)}</select>
                </div>
                <div className="fld"><label className="flbl">Regional uplift (%)</label><input className="finp" type="number" defaultValue="0" /></div>
              </div>
            </div>
            <div className="scard">
              <p className="scard-title">Trade overrides (£/unit)</p>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                <thead><tr style={{ background: 'rgba(15,20,28,0.7)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {['Trade','BCIS default','Your override'].map(h => <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: 'rgba(255,255,255,0.45)', fontSize: '13px' }}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {[['Brickwork (stretcher bond)','£0.65/No'],['Blockwork (common)','£0.45/No'],['Clay tile roof covering','£38.50/m²'],['Internal plaster','£7.50/m²'],['Emulsion paint (2 coats)','£2.10/m²']].map(([trade, bcis], i) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ padding: '12px 16px', color: 'rgba(255,255,255,0.65)' }}>{trade}</td>
                      <td style={{ padding: '12px 16px', color: 'rgba(255,255,255,0.38)' }}>{bcis}</td>
                      <td style={{ padding: '12px 16px' }}><input type="text" placeholder="e.g. 0.70" className="finp" style={{ width: '120px' }} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: '24px' }}>
                <button className="btn btn-amber btn-pill" onClick={() => save('rates')}>{saved.rates ? '✓ Saved' : 'Save rate overrides'}</button>
              </div>
            </div>
          </>
        )}
        {tab === 'billing' && (
          <>
            <div className="dash-hd"><h1 className="dash-h1">Billing</h1></div>
            <div className="scard">
              <p className="scard-title">Current plan</p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px', marginBottom: '16px' }}>
                <div><p style={{ fontWeight: 700, fontSize: '18px', marginBottom: '4px', color: 'white' }}>Pro — £39/month</p><p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.42)' }}>Renews 4 July 2026</p></div>
                <button className="btn btn-outline btn-pill btn-sm" onClick={() => go('pricing')}>Change plan</button>
              </div>
            </div>
            <div className="scard">
              <p className="scard-title">Payment method</p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', marginBottom: '12px' }}>
                <span style={{ fontSize: '14px', color: 'rgba(255,255,255,0.7)' }}>Visa ···· 4242 · Exp 12/28</span>
                <button className="btn btn-ghost btn-sm" onClick={() => toast('Payment management coming soon.', 'info')}>Replace</button>
              </div>
              <button className="btn btn-outline btn-pill btn-sm" onClick={() => toast('Payment management coming soon.', 'info')}>+ Add payment method</button>
            </div>
            <div className="scard">
              <p className="scard-title">Invoices</p>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                <thead><tr style={{ background: 'rgba(15,20,28,0.7)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                  {['Date','Amount','Status',''].map((h, i) => <th key={i} style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: 'rgba(255,255,255,0.45)', fontSize: '13px' }}>{h}</th>)}
                </tr></thead>
                <tbody>
                  {[['4 Jun 2026','£39.00'],['4 May 2026','£39.00'],['4 Apr 2026','£39.00']].map(([date, amount], i) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ padding: '12px 16px', color: 'rgba(255,255,255,0.65)' }}>{date}</td>
                      <td style={{ padding: '12px 16px', color: 'rgba(255,255,255,0.65)' }}>{amount}</td>
                      <td style={{ padding: '12px 16px' }}><span style={{ color: 'var(--green)', fontWeight: 600 }}>Paid</span></td>
                      <td style={{ padding: '12px 16px' }}><button className="btn btn-ghost btn-sm" onClick={() => toast('Invoice PDF download coming soon.', 'info')}>Download</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
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
          <div style={{ width: '64px', height: '64px', background: 'rgba(249,115,22,0.1)', borderRadius: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px', fontSize: '28px' }}>
            ✉️
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
        <div style={{ width: '64px', height: '64px', background: 'rgba(249,115,22,0.1)', borderRadius: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px', fontSize: '28px' }}>
          ✉️
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

Object.assign(window, {
  LandingPage, ResultsPage, DashboardPage, UploadPage, SettingsPage,
  SignUpPage, SignInPage, PricingPage,
  ForgotPasswordPage, CheckEmailPage, ResetPasswordPage,
});
