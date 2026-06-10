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

function AnnouncementBar({ go }) {
  return null;
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
              style={{ height: '34px', display: 'block', filter: 'drop-shadow(0 0 1px rgba(255,255,255,0.15)) brightness(1.15)' }} />
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
            <img src="logo-transparent.png" alt="Vulcan Quanta" style={{ height: '52px', filter: 'brightness(0) invert(1)', marginBottom: '14px', display: 'block' }} />
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
  // Items without a target are placeholders for sections not yet built.
  const navItems = [
    { label: 'Dashboard', icon: '⊞', target: 'dashboard', match: 'dashboard' },
    { label: 'Projects',  icon: '▤', target: 'dashboard', match: 'projects'  },
    { label: 'Uploads',   icon: '↑', target: 'upload',    match: 'upload'     },
    { label: 'Reports',   icon: '▦', target: null,        match: 'reports'    },
    { label: 'Exports',   icon: '⤓', target: null,        match: 'exports'    },
    { label: 'History',   icon: '◷', target: null,        match: 'history'    },
    { label: 'Settings',  icon: '⚙', target: 'settings',  match: 'settings'   },
  ];

  const handleNav = (item) => {
    if (item.target) go(item.target);
    else if (toast) toast(`${item.label} — coming soon.`, 'info');
  };

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
            style={{ height: '28px', display: 'block' }}
          />
        ) : (
          <span style={{ fontFamily: "'Cinzel', serif", fontSize: '13px', fontWeight: 700, color: 'white', letterSpacing: '0.15em' }}>VQ</span>
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
            <span style={{ fontSize: '15px', lineHeight: 1 }}>{item.icon}</span>
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
          <span style={{ fontSize: '14px' }}>⚙</span>
          <span>Settings</span>
        </div>
        <div className="app-side-item" onClick={handleSignOut}>
          <span style={{ fontSize: '13px' }}>→</span>
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

Object.assign(window, { AnnouncementBar, Header, Footer, BoQMockup, ToastContainer, AppSidebar });
