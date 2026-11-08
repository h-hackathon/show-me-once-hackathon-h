// Show Me Once — content script : capture des clics, saisies et soumissions dans chaque page.
// Envoie tout au service worker, qui ignore les messages s'il n'y a pas d'enregistrement en cours.
(() => {
  // Une instance "orpheline" (extension rechargée) ne peut plus envoyer de messages : on la remplace.
  const alive = () => { try { return !!chrome.runtime?.id; } catch (_) { return false; } };
  if (window.__showMeOnceAlive && window.__showMeOnceAlive()) return;
  window.__showMeOnceAlive = alive;

  const SENSITIVE = /pass(word)?|pwd|secret|token|otp|cvv|cvc|card.?number|cc-|iban|ssn/i;

  const clip = (s, n = 160) => (s || "").replace(/\s+/g, " ").trim().slice(0, n);

  function cssPath(el) {
    if (!(el instanceof Element)) return null;
    if (el.id && !/\d{3,}/.test(el.id)) return `#${CSS.escape(el.id)}`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      const testId = node.getAttribute("data-testid") || node.getAttribute("data-test") || node.getAttribute("data-cy");
      if (testId) { parts.unshift(`${part}[data-testid="${testId}"]`); break; }
      if (node.id && !/\d{3,}/.test(node.id)) { parts.unshift(`#${CSS.escape(node.id)}`); break; }
      const name = node.getAttribute("name");
      if (name) part += `[name="${name}"]`;
      else {
        const parent = node.parentElement;
        if (parent) {
          const same = [...parent.children].filter((c) => c.tagName === node.tagName);
          if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
        }
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(" > ");
  }

  function xPath(el) {
    const segs = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      let i = 1;
      for (let s = n.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === n.tagName) i++;
      segs.unshift(`${n.tagName.toLowerCase()}[${i}]`);
    }
    return "/" + segs.join("/");
  }

  function labelFor(el) {
    if (el.labels && el.labels.length) return clip(el.labels[0].innerText);
    const lb = el.getAttribute("aria-labelledby");
    if (lb) { const t = document.getElementById(lb.split(" ")[0]); if (t) return clip(t.innerText); }
    return null;
  }

  // Remonte jusqu'à l'élément réellement "actionnable" (bouton, lien, champ, role=…)
  function actionable(el) {
    const sel = 'a,button,input,select,textarea,label,summary,[role="button"],[role="link"],[role="tab"],[role="menuitem"],[role="option"],[role="checkbox"],[onclick],[tabindex]';
    return (el instanceof Element && el.closest(sel)) || el;
  }

  function describe(el) {
    const r = el.getBoundingClientRect();
    const link = el.closest && el.closest("a[href]");
    return {
      tag: el.tagName ? el.tagName.toLowerCase() : null,
      type: el.getAttribute?.("type") || null,
      role: el.getAttribute?.("role") || null,
      text: clip(el.innerText || (["submit", "button", "reset"].includes(el.type) ? el.value : "")),
      aria_label: el.getAttribute?.("aria-label") || null,
      title: el.getAttribute?.("title") || null,
      placeholder: el.getAttribute?.("placeholder") || null,
      name: el.getAttribute?.("name") || null,
      label: labelFor(el),
      href: link ? link.href : null,
      selector: cssPath(el),
      xpath: xPath(el),
      bbox: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      // Contexte : la ligne de tableau / l'item de liste qui contient l'élément (ex : quel litige on a ouvert)
      row_text: rowText(el),
      section: sectionTitle(el),
    };
  }

  function rowText(el) {
    const row = el.closest && el.closest('tr, [role="row"], li, [data-testid*="row" i]');
    if (!row || row === el) return null;
    const cells = row.querySelectorAll('td, [role="cell"], [role="gridcell"]');
    const txt = cells.length ? [...cells].map((c) => clip(c.innerText, 60)).filter(Boolean).join(" | ") : clip(row.innerText, 200);
    return clip(txt, 240) || null;
  }

  // Titre de la section / du panneau le plus proche (h1-h3, dialog, aria-label de region)
  function sectionTitle(el) {
    for (let n = el.parentElement, depth = 0; n && depth < 12; n = n.parentElement, depth++) {
      const lbl = n.getAttribute?.("aria-label");
      if (lbl && /^(section|dialog|region|aside|nav|form)$/i.test(n.getAttribute("role") || n.tagName)) return clip(lbl, 80);
      const h = n.querySelector?.(":scope > h1, :scope > h2, :scope > h3, :scope > header h1, :scope > header h2, :scope > header h3");
      if (h && h.innerText) return clip(h.innerText, 80);
    }
    return null;
  }

  function isSensitiveField(el) {
    if (!el || !el.getAttribute) return false;
    const attrs = [el.type, el.name, el.id, el.getAttribute("autocomplete"), el.getAttribute("aria-label"), el.placeholder].join(" ");
    return el.type === "password" || SENSITIVE.test(attrs);
  }

  function context() {
    return {
      url: location.href,
      title: document.title,
      frame: window.top === window ? "top" : "iframe",
      viewport: { w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio },
    };
  }

  function send(event) {
    if (!alive()) return;
    try {
      chrome.runtime.sendMessage({ type: "dom-event", event: { ts: Date.now(), ...context(), ...event } });
    } catch (_) { /* extension rechargée : on ignore */ }
  }

  // Clic — on écoute pointerdown (avant navigation) pour que la capture d'écran montre l'état AVANT le clic.
  document.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const el = actionable(e.target);
    send({ kind: "click", x: Math.round(e.clientX), y: Math.round(e.clientY), target: describe(el) });
  }, true);

  // Saisie — on garde la valeur finale du champ (événement change), masquée si sensible.
  document.addEventListener("change", (e) => {
    const el = e.target;
    if (!el || !/^(input|textarea|select)$/i.test(el.tagName)) return;
    const sensitive = isSensitiveField(el);
    let value;
    if (el.tagName === "SELECT") value = clip(el.options[el.selectedIndex]?.text || el.value);
    else if (el.type === "checkbox" || el.type === "radio") value = el.checked;
    else if (el.type === "file") value = [...(el.files || [])].map((f) => f.name).join(", ");
    else value = sensitive ? "«masqué»" : clip(el.value, 500);
    send({ kind: "input", value, sensitive, target: describe(el) });
  }, true);

  // contenteditable (éditeurs riches type Gmail / Notion / Intercom)
  document.addEventListener("focusout", (e) => {
    const el = e.target;
    if (el && el.isContentEditable && !el.parentElement?.isContentEditable) {
      send({ kind: "input", value: clip(el.innerText, 500), sensitive: false, target: describe(el) });
    }
  }, true);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === "Escape" || e.key === "Tab") {
      send({ kind: "key", key: e.key, target: describe(e.target) });
    }
  }, true);

  document.addEventListener("submit", (e) => {
    send({ kind: "submit", target: describe(e.target), action: e.target.action || null });
  }, true);

  // Les changements d'URL (y compris SPA via pushState) sont suivis par le service worker (tabs.onUpdated).
})();
