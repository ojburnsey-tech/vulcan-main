/* ============================================================================
   VULCAN QUANTA — BUTTON GLOW (interaction controller)
   ----------------------------------------------------------------------------
   The cursor-tracking half of the button glow. Pure DOM, framework-agnostic,
   and event-delegated so it works for every button React mounts or unmounts
   across page navigation without re-binding.

   Distilled from the BorderGlow reference, keeping only the interaction maths:
     - cursor angle calculation        (atan2 around the element centre)
     - edge proximity detection        (0 at centre, 1 at the nearest edge)
   The heavy visuals (mesh gradients, radial stacks, conic masks, glow fills,
   sweep animations) are intentionally dropped — see button-glow.css.

   Performance contract:
     - At most ONE requestAnimationFrame is ever in flight (coalesced).
     - We only read layout / write CSS variables while a button is hovered.
     - No per-frame masks or expensive layout work; we write four CSS vars.

   Accessibility: on coarse (touch) pointers or when the user prefers reduced
   motion we do nothing — CSS provides the static, non-tracking glow instead.
   ========================================================================== */
(function () {
  'use strict';

  // The button primitive + the two standalone variants that opt into the glow.
  var SELECTOR = '.btn, .vd-qa-btn, .btn-ghost-lt';

  var mq = window.matchMedia ? window.matchMedia.bind(window) : null;
  var hoverCapable = mq ? mq('(hover: hover)').matches : true;
  var reduceMotion = mq ? mq('(prefers-reduced-motion: reduce)').matches : false;

  // No live tracking for touch devices or reduced-motion users; CSS handles
  // those cases with a static border glow. Bail out entirely — nothing to bind.
  if (!hoverCapable || reduceMotion) return;

  var active = null;   // the button currently under the cursor
  var clientX = 0;     // latest pointer position (viewport coords)
  var clientY = 0;
  var rafId = 0;       // pending rAF handle (0 = none)
  var dirty = false;   // pointer moved since the last frame?

  function isDisabled(el) {
    return el.disabled || el.getAttribute('aria-disabled') === 'true';
  }

  function clearVars(el) {
    var s = el.style;
    s.removeProperty('--bgw-gx');
    s.removeProperty('--bgw-gy');
    s.removeProperty('--bgw-edge');
    s.removeProperty('--bgw-angle');
  }

  function onPointerOver(e) {
    var t = e.target;
    var btn = (t && t.closest) ? t.closest(SELECTOR) : null;
    if (!btn || isDisabled(btn)) return;
    if (btn !== active) {
      if (active) clearVars(active);
      active = btn;
    }
  }

  function onPointerMove(e) {
    if (!active) return;
    clientX = e.clientX;
    clientY = e.clientY;
    dirty = true;
    if (!rafId) rafId = requestAnimationFrame(frame);
  }

  function onPointerOut(e) {
    if (!active) return;
    // Ignore moves between the button and its own children (icons / spans).
    var to = e.relatedTarget;
    if (to && active.contains(to)) return;
    clearVars(active);
    active = null;
  }

  function frame() {
    rafId = 0;
    if (!active || !dirty) return;
    dirty = false;

    // Guard against a button React has since unmounted.
    if (!active.isConnected) { active = null; return; }

    var r = active.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;

    var x = clientX - r.left;
    var y = clientY - r.top;

    // Cursor position as a percentage — drives the radial highlight.
    var gx = (x / r.width) * 100;
    var gy = (y / r.height) * 100;

    // Edge proximity: 1 at the nearest edge, 0 dead centre (from reference).
    var nx = (x / r.width) * 2 - 1;   // -1 .. 1 across width
    var ny = (y / r.height) * 2 - 1;  // -1 .. 1 across height
    var edge = Math.min(1, Math.max(Math.abs(nx), Math.abs(ny)));

    // Cursor angle around the centre — retained from the BorderGlow maths.
    var dx = x - r.width / 2;
    var dy = y - r.height / 2;
    var angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
    if (angle < 0) angle += 360;

    var s = active.style;
    s.setProperty('--bgw-gx', gx.toFixed(2) + '%');
    s.setProperty('--bgw-gy', gy.toFixed(2) + '%');
    s.setProperty('--bgw-edge', edge.toFixed(3));
    s.setProperty('--bgw-angle', angle.toFixed(1) + 'deg');
  }

  document.addEventListener('pointerover', onPointerOver, { passive: true });
  document.addEventListener('pointermove', onPointerMove, { passive: true });
  document.addEventListener('pointerout', onPointerOut, { passive: true });
})();
