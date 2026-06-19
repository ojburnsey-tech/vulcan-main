// vq-shared.jsx — Header, Footer, AnnouncementBar, BoQMockup, ToastContainer
const { useState, useEffect } = React;

// Derive up-to-two-letter initials from a full name, falling back to the email's
// local part (e.g. "Oliver QS" → "OQ", "ojburnsey@gmail.com" → "OJ").
function vqInitials(fullName, email) {
  const src = (fullName && fullName.trim()) || (email ? email.split('@')[0] : '');
  if (!src) return '?';
  const parts = src.trim().split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

// Map a stored plan code to a human label, all in orange in the UI.
function vqPlanLabel(plan) {
  switch ((plan || 'free').toLowerCase()) {
    case 'pro':    return 'Professional Plan';
    case 'studio': return 'Studio Plan';
    default:       return 'Free Plan';
  }
}

// Clean stroke-based line icons for the sidebar (16px, currentColor).
function VQIcon(props) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      style={{ display: 'block', flexShrink: 0 }}>
      {props.children}
    </svg>
  );
}

const VQ_NAV_ICONS = {
  dashboard: <VQIcon><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></VQIcon>,
  projects:  <VQIcon><path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" /></VQIcon>,
  measure:   <VQIcon><path d="M21.3 8.7l-6-6a1 1 0 00-1.4 0L2.7 13.9a1 1 0 000 1.4l6 6a1 1 0 001.4 0L21.3 10.1a1 1 0 000-1.4z" /><line x1="7.5" y1="10.5" x2="9" y2="12" /><line x1="10.5" y1="7.5" x2="12" y2="9" /><line x1="13.5" y1="4.5" x2="15" y2="6" /></VQIcon>,
  uploads:   <VQIcon><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></VQIcon>,
  reports:   <VQIcon><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></VQIcon>,
  exports:   <VQIcon><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></VQIcon>,
  history:   <VQIcon><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></VQIcon>,
  settings:  <VQIcon><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" /></VQIcon>,
  signout:   <VQIcon><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></VQIcon>,
  review:    <VQIcon><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" /></VQIcon>,
};

function AnnouncementBar({ go }) {
  return null;
}

// ─── ARCHITECTURAL PARTICLE FIELD ───────────────────────────────────────────────────
// A fixed SVG layer behind app content: faint topographic contour lines with small
// amber data-points travelling along them — construction data moving through a
// network, not a starfield. Pure SMIL animation (no rAF loop, no blur filters) so
// it composites cheaply and holds 60fps on low-end devices. Hidden entirely for
// prefers-reduced-motion users (static contours remain).
const VQ_FLOW_PATHS = [
  // Long survey contours sweeping across the centre and lower half of the viewport.
  { d: 'M-80,640 C180,560 360,690 640,620 C920,550 1080,680 1300,610 C1400,580 1480,600 1540,590', op: 0.075, dur: 17 },
  { d: 'M-80,720 C240,660 420,770 700,700 C980,630 1160,760 1380,690 C1460,665 1500,680 1540,672', op: 0.06,  dur: 21 },
  { d: 'M-80,810 C200,760 440,850 720,790 C1000,730 1200,840 1420,780 C1480,765 1520,772 1540,768', op: 0.05,  dur: 24 },
  { d: 'M-80,470 C260,420 460,520 760,460 C1060,400 1220,500 1440,450 C1490,440 1520,445 1540,442', op: 0.06,  dur: 19 },
  { d: 'M-80,300 C300,260 520,350 820,300 C1120,250 1280,330 1480,290 C1510,284 1530,287 1540,286', op: 0.05,  dur: 23 },
];

// Static intermediate contours (never animated) — fill out the topographic texture.
const VQ_STATIC_CONTOURS = [
  { d: 'M-80,680 C210,615 390,730 670,660 C950,590 1120,720 1340,650 C1440,620 1500,640 1540,630', op: 0.05 },
  { d: 'M-80,765 C220,710 430,810 710,745 C990,680 1180,800 1400,735 C1470,715 1510,726 1540,720', op: 0.04 },
  { d: 'M-80,545 C240,495 450,590 740,535 C1030,480 1200,575 1430,520 C1485,508 1520,514 1540,511', op: 0.045 },
  { d: 'M-80,385 C280,340 490,435 790,380 C1090,325 1250,415 1460,370 C1505,360 1528,364 1540,362', op: 0.04 },
];

function VQParticleField() {
  const [reduceMotion] = useState(() =>
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false);

  return (
    <svg className="vq-particle-field" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMax slice" aria-hidden="true"
      style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', zIndex: 0, pointerEvents: 'none' }}>
      <defs>
        {/* Soft glow without a filter: radial gradient discs are far cheaper than feGaussianBlur */}
        <radialGradient id="vq-pt-glow">
          <stop offset="0%"  stopColor="#D9855B" stopOpacity="0.55" />
          <stop offset="45%" stopColor="#D9855B" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#D9855B" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Topographic contour lines */}
      {VQ_STATIC_CONTOURS.map((c, i) => (
        <path key={`s${i}`} d={c.d} fill="none" stroke="#D9855B" strokeOpacity={c.op} strokeWidth="0.8" />
      ))}
      {VQ_FLOW_PATHS.map((p, i) => (
        <path key={`f${i}`} id={`vq-flow-${i}`} d={p.d} fill="none" stroke="#D9855B" strokeOpacity={p.op} strokeWidth="1" />
      ))}

      {/* Data points travelling along the contours */}
      {!reduceMotion && VQ_FLOW_PATHS.map((p, i) => {
        const begin = -(i * 3.7);
        return (
          <g key={`pt${i}`}>
            {/* glow halo */}
            <circle r="7" fill="url(#vq-pt-glow)" opacity="0.25">
              <animateMotion dur={`${p.dur}s`} begin={`${begin}s`} repeatCount="indefinite" rotate="0">
                <mpath href={`#vq-flow-${i}`} xlinkHref={`#vq-flow-${i}`} />
              </animateMotion>
            </circle>
            {/* short trail node, slightly behind the lead particle */}
            <circle r="1.2" fill="#D9855B" opacity="0.15">
              <animateMotion dur={`${p.dur}s`} begin={`${begin - 0.55}s`} repeatCount="indefinite" rotate="0">
                <mpath href={`#vq-flow-${i}`} xlinkHref={`#vq-flow-${i}`} />
              </animateMotion>
            </circle>
            {/* lead particle with a slow brightness pulse */}
            <circle r="2" fill="#D9855B" opacity="0.3">
              <animateMotion dur={`${p.dur}s`} begin={`${begin}s`} repeatCount="indefinite" rotate="0">
                <mpath href={`#vq-flow-${i}`} xlinkHref={`#vq-flow-${i}`} />
              </animateMotion>
              <animate attributeName="opacity" values="0.18;0.35;0.22;0.35;0.18"
                dur={`${Math.max(5, p.dur / 3)}s`} begin={`${begin}s`} repeatCount="indefinite" />
            </circle>
          </g>
        );
      })}
    </svg>
  );
}

function Header({ page, go, toast, user }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [logoOk, setLogoOk] = useState(true);
  const links = [
    { label: 'How it works', target: 'landing' },
    { label: 'Pricing', target: 'pricing' },
    { label: 'Docs', soon: true, action: () => toast('Documentation coming soon.', 'info') },
  ];

  const handleSignOut = async () => {
    setMenuOpen(false);
    if (window.VQAuth) {
      await window.VQAuth.signOut();
    } else {
      go('landing');
    }
  };

  return (
    <header className="hdr">
      <div className="hdr-inner">
        <span onClick={() => go('landing')} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
          {logoOk ? (
            <img src="logo-transparent.png" alt="Vulcan Quanta"
              onError={() => setLogoOk(false)}
              style={{ height: '48px', display: 'block', filter: 'drop-shadow(0 0 1px rgba(255,255,255,0.15)) brightness(1.15)' }} />
          ) : (
            <span style={{ fontFamily: 'var(--font-d)', fontSize: '17px', fontWeight: 700, color: '#fff', letterSpacing: '0.08em' }}>VULCAN QUANTA</span>
          )}
        </span>
        <nav>
          <ul className="nav-links">
            {links.map((l, i) => (
              <li key={i}>
                <span className="nav-link" onClick={() => l.target ? go(l.target) : l.action?.()}>
                  {l.label}
                  {l.soon && <sup style={{ fontSize: '9px', color: 'var(--c-500)', marginLeft: '3px' }}>soon</sup>}
                </span>
              </li>
            ))}
          </ul>
        </nav>
        <div className="hdr-right">
          {user ? (
            <>
              <button className="btn btn-ghost-dim" onClick={() => go('dashboard')}>Dashboard</button>
              <button className="btn btn-nav-pill" onClick={handleSignOut}>Sign out</button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost-dim" onClick={() => go('signin')}>Sign in</button>
              <button className="btn btn-nav-pill" onClick={() => go('signup')}>Start free</button>
            </>
          )}
        </div>
        <button className="hamburger" aria-label="Menu" onClick={() => setMenuOpen(o => !o)}>
          <span></span><span></span><span></span>
        </button>
      </div>
      {menuOpen && (
        <div className="mobile-menu">
          {links.map((l, i) => (
            <span key={i} className="mobile-link"
              onClick={() => { l.target ? go(l.target) : l.action?.(); setMenuOpen(false); }}>
              {l.label}
            </span>
          ))}
          {user ? (
            <>
              <button className="btn btn-outline btn-pill" style={{ alignSelf: 'flex-start', marginTop: '8px' }}
                onClick={() => { go('dashboard'); setMenuOpen(false); }}>
                Dashboard
              </button>
              <button className="btn btn-ghost btn-pill" style={{ alignSelf: 'flex-start', color: 'rgba(255,255,255,0.6)' }}
                onClick={handleSignOut}>
                Sign out
              </button>
            </>
          ) : (
            <button className="btn btn-amber btn-pill" style={{ alignSelf: 'flex-start', marginTop: '8px' }}
              onClick={() => { go('signup'); setMenuOpen(false); }}>
              Start free
            </button>
          )}
        </div>
      )}
    </header>
  );
}

function Footer({ go }) {
  const cs = (fn) => (e) => { e.preventDefault(); fn(); };
  return (
    <footer className="ftr">
      <div className="inner">
        <div className="ftr-grid">
          <div>
            <img src="logo-transparent.png" alt="Vulcan Quanta" style={{ height: '72px', filter: 'brightness(0) invert(1)', marginBottom: '14px', display: 'block' }} />
            <p className="ftr-desc">AI-powered quantity surveying for UK builders and contractors. A priced Bill of Quantities in under 2 minutes.</p>
          </div>
          <div>
            <p className="ftr-col-title">Product</p>
            <a className="ftr-link" href="#" onClick={cs(() => go('landing'))}>How it works</a>
            <a className="ftr-link" href="#" onClick={cs(() => go('pricing'))}>Pricing</a>
            <a className="ftr-link ftr-link-dim" href="#">Docs (soon)</a>
            <a className="ftr-link ftr-link-dim" href="#">API (soon)</a>
          </div>
          <div>
            <p className="ftr-col-title">Company</p>
            <a className="ftr-link" href="#">About</a>
            <a className="ftr-link" href="#">Blog</a>
            <a className="ftr-link" href="#">Careers</a>
            <a className="ftr-link" href="#">Contact</a>
          </div>
          <div>
            <p className="ftr-col-title">Legal</p>
            <a className="ftr-link" href="#">Terms of service</a>
            <a className="ftr-link" href="#">Privacy policy</a>
            <a className="ftr-link" href="#">Cookie policy</a>
            <a className="ftr-link" href="#">GDPR</a>
          </div>
        </div>
        <hr className="ftr-rule" />
        <div className="ftr-bottom">
          <p className="ftr-copy">© 2026 Vulcan Quanta Ltd. All rights reserved.<br />Company No. 14987234 · VAT No. 456 789 012</p>
          <address className="ftr-address">
            Vulcan Quanta Ltd<br />
            12 St Ann's Square<br />
            Manchester, M2 7HG
          </address>
        </div>
      </div>
    </footer>
  );
}

function BoQMockup() {
  return (
    <div className="boq-mockup">
      <div className="boq-mock-hdr">
        <div>
          <p className="boq-mock-eyebrow">Bill of Quantities</p>
          <p className="boq-mock-title">Oak View Residential Extension</p>
          <p className="boq-mock-meta">Ref: OVR-2026-047 · Jun 2026 · BCIS Q2 2026 rates</p>
        </div>
        <span className="boq-conf-pill">94% confidence</span>
      </div>
      <table className="boq-mini">
        <thead>
          <tr>
            <th>Description</th>
            <th className="r">Qty</th>
            <th className="r">Unit</th>
            <th className="r">Rate</th>
            <th className="r">Total</th>
          </tr>
        </thead>
        <tbody>
          <tr className="boq-trade-hd"><td colSpan="5">A — GROUNDWORKS</td></tr>
          <tr className="boq-row"><td>Excavation to reduced level</td><td className="r">86</td><td className="r">m²</td><td className="r">£6.50</td><td className="r">£559.00</td></tr>
          <tr className="boq-row alt"><td>Concrete strip foundations</td><td className="r">28</td><td className="r">lm</td><td className="r">£95.00</td><td className="r">£2,660.00</td></tr>
          <tr className="boq-trade-hd"><td colSpan="5">B — BRICKWORK</td></tr>
          <tr className="boq-row"><td>Common brickwork, stretcher bond</td><td className="r">210</td><td className="r">m²</td><td className="r">£65.00</td><td className="r">£13,650.00</td></tr>
          <tr className="boq-row flagged"><td>⚠ Clay tile roof covering</td><td className="r">320</td><td className="r">m²</td><td className="r">£38.50</td><td className="r">£12,320.00</td></tr>
          <tr className="boq-sub"><td colSpan="4">Works subtotal</td><td className="r">£29,189.00</td></tr>
          <tr className="boq-sub"><td colSpan="4">Contingency (10%)</td><td className="r">£2,918.90</td></tr>
          <tr className="boq-grand"><td colSpan="4">GRAND TOTAL (EX. VAT)</td><td className="r">£32,107.90</td></tr>
        </tbody>
      </table>
      <div className="boq-mock-ftr">
        <p>AI-generated draft — professional review required before issue to client.</p>
      </div>
    </div>
  );
}

function AppSidebar({ currentPage, go, user: userProp, toast }) {
  const [logoOk, setLogoOk] = useState(true);
  // The shared sidebar appears on pages that don't pass `user`, so when no prop is
  // supplied we resolve the signed-in user from the Supabase session ourselves.
  const [user, setUser] = useState(userProp || null);

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

  const handleSignOut = async () => {
    if (window.VQAuth) {
      await window.VQAuth.signOut();
    } else {
      go('landing');
    }
  };

  // `match` drives the active highlight; `target` is where the item navigates.
  const navItems = [
    { label: 'Dashboard', icon: VQ_NAV_ICONS.dashboard, target: 'dashboard', match: 'dashboard' },
    { label: 'Projects',  icon: VQ_NAV_ICONS.projects,  target: 'projects',  match: 'projects'  },
    { label: 'Measurement Hub', icon: VQ_NAV_ICONS.measure, target: 'measurehub', match: 'measurehub' },
    { label: 'Uploads',   icon: VQ_NAV_ICONS.uploads,   target: 'upload',    match: 'upload'     },
    { label: 'Reports',   icon: VQ_NAV_ICONS.reports,   target: 'reports',   match: 'reports'    },
    { label: 'Exports',   icon: VQ_NAV_ICONS.exports,   target: 'exports',   match: 'exports'    },
    { label: 'History',   icon: VQ_NAV_ICONS.history,   target: 'history',   match: 'history'    },
    { label: 'Review & Sign-off', icon: VQ_NAV_ICONS.review, target: 'review', match: 'review' },
    { label: 'Settings',  icon: VQ_NAV_ICONS.settings,  target: 'settings',  match: 'settings'   },
  ];

  const handleNav = (item) => { if (item.target) go(item.target); };

  const email     = user?.email || '';
  const meta      = user?.user_metadata || {};
  const fullName  = meta.full_name || '';
  const avatarUrl = meta.avatar_url || '';
  const initials  = vqInitials(fullName, email);
  const planLabel = vqPlanLabel(meta.plan);
  const profileLabel = email || fullName || 'Account';

  return (
    <aside className="app-side">
      <div className="app-side-logo" onClick={() => go('landing')}>
        {logoOk ? (
          <img
            src="logo-transparent.png"
            alt="Vulcan Quanta"
            onError={() => setLogoOk(false)}
            style={{ height: '40px', display: 'block' }}
          />
        ) : (
          <span style={{ fontFamily: "'Cinzel', serif", fontSize: '18px', fontWeight: 700, color: 'white', letterSpacing: '0.15em' }}>VQ</span>
        )}
      </div>
      <p className="app-side-lbl">Navigation</p>
      <nav>
        {navItems.map(item => (
          <div
            key={item.label}
            className={`app-side-item${currentPage === item.match ? ' active' : ''}`}
            onClick={() => handleNav(item)}
          >
            <span style={{ display: 'flex', alignItems: 'center' }}>{item.icon}</span>
            <span>{item.label}</span>
          </div>
        ))}
      </nav>
      <div className="app-side-bottom">
        <div className="vd-profile">
          {avatarUrl
            ? <img className="vd-avatar-img" src={avatarUrl} alt="" />
            : <div className="vd-avatar">{initials}</div>}
          <div className="vd-profile-info">
            <div className="vd-profile-name" title={profileLabel}>{profileLabel}</div>
            <div className="vd-profile-plan">{planLabel}</div>
          </div>
        </div>
        <div className="app-side-item" onClick={() => go('settings')}>
          <span style={{ display: 'flex', alignItems: 'center' }}>{VQ_NAV_ICONS.settings}</span>
          <span>Settings</span>
        </div>
        <div className="app-side-item" onClick={handleSignOut}>
          <span style={{ display: 'flex', alignItems: 'center' }}>{VQ_NAV_ICONS.signout}</span>
          <span>Sign out</span>
        </div>
      </div>
    </aside>
  );
}

function ToastContainer({ toasts }) {
  if (!toasts.length) return null;
  return (
    <div className="toast-wrap">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>{t.msg}</div>
      ))}
    </div>
  );
}

Object.assign(window, { AnnouncementBar, Header, Footer, BoQMockup, ToastContainer, AppSidebar, VQParticleField });
