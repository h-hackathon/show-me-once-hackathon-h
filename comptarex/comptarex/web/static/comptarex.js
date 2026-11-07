/* COMPTAREX Cabinet 6.2 — scripts de la page (pas d'appel réseau, sauf la création de fournisseur) */
(function () {
  "use strict";

  // Menu en arbre : une seule branche principale ouverte à la fois.
  document.querySelectorAll(".node[data-branch]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var branche = document.getElementById(btn.dataset.branch);
      var ouvrir = branche.hidden;
      if (btn.dataset.level === "1" && ouvrir) {
        document.querySelectorAll('.node[data-level="1"]').forEach(function (autre) {
          if (autre !== btn) {
            document.getElementById(autre.dataset.branch).hidden = true;
            autre.setAttribute("aria-expanded", "false");
            autre.querySelector(".box").textContent = "+";
          }
        });
      }
      branche.hidden = !ouvrir;
      btn.setAttribute("aria-expanded", ouvrir ? "true" : "false");
      btn.querySelector(".box").textContent = ouvrir ? "−" : "+";
    });
  });

  // Compte à rebours de session (décoratif : la session réelle dure 30 jours).
  var expire = document.getElementById("expire");
  if (expire) {
    var reste = 899;
    setInterval(function () {
      reste = Math.max(0, reste - 1);
      expire.textContent = Math.floor(reste / 60) + ":" + String(reste % 60).padStart(2, "0");
    }, 1000);
  }

  // Onglets.
  document.querySelectorAll("[data-tabs]").forEach(function (groupe) {
    var champ = groupe.querySelector('input[name="onglet"]');
    groupe.querySelectorAll("[data-tab]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        groupe.querySelectorAll("[data-tab]").forEach(function (t) {
          var actif = t === tab;
          t.classList.toggle("on", actif);
          t.setAttribute("aria-selected", actif ? "true" : "false");
        });
        groupe.querySelectorAll("[data-panel]").forEach(function (p) {
          p.hidden = p.dataset.panel !== tab.dataset.tab;
        });
        if (champ) champ.value = tab.dataset.tab;
      });
    });
  });

  // Boîtes de message.
  document.querySelectorAll("[data-close]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.getElementById(btn.dataset.close).hidden = true;
    });
  });
  var ok = document.querySelector("#msgbox [data-close]");
  if (ok) ok.focus();

  // Zoom de la visionneuse.
  var zoom = document.getElementById("zoom");
  if (zoom) {
    zoom.addEventListener("change", function () {
      document.querySelector(".papier").style.transform = "scale(" + (parseInt(zoom.value, 10) / 100) + ")";
    });
  }

  // ------------------------------------------------------------ saisie des factures
  var form = document.getElementById("form-facture");
  if (!form) return;

  var TAUX = { "20 %": [2000, false], "10 %": [1000, false], "5,5 %": [550, false], "0 %": [0, false],
               "20 % autoliquidation UE": [2000, true] };

  function montant(txt) {
    var t = (txt || "").replace(/\s| |€/g, "");
    if (t.indexOf(",") >= 0 && t.indexOf(".") >= 0) t = t.replace(/\./g, "");
    t = t.replace(",", ".");
    var n = parseFloat(t);
    return isNaN(n) ? null : Math.round(n * 100);
  }
  function fmt(c) {
    var s = c < 0 ? "-" : "";
    c = Math.abs(c);
    var e = Math.floor(c / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return s + e + "," + String(c % 100).padStart(2, "0");
  }
  function arrondi(x) { return Math.floor(x + 0.5); }

  function recalculer() {
    var ht = 0, tva = 0;
    form.querySelectorAll("tr[data-ligne]").forEach(function (tr) {
      var q = parseFloat((tr.querySelector('[name="quantite"]').value || "").replace(",", "."));
      var p = montant(tr.querySelector('[name="prix_unitaire"]').value);
      var taxe = TAUX[tr.querySelector('[name="taxe"]').value];
      var cell = tr.querySelector("[data-montant]");
      if (!isNaN(q) && q > 0 && p !== null && taxe) {
        var l = arrondi(q * p);
        ht += l;
        if (!taxe[1]) tva += arrondi(l * taxe[0] / 10000);
        cell.textContent = fmt(l);
      } else {
        cell.textContent = "";
      }
    });
    document.getElementById("total-ht").textContent = fmt(ht);
    document.getElementById("total-tva").textContent = fmt(tva);
    document.getElementById("total-ttc").textContent = fmt(ht + tva);
  }
  form.addEventListener("input", recalculer);
  form.addEventListener("change", recalculer);

  // Autocomplétion du fournisseur (liste embarquée dans la page).
  var data = JSON.parse(document.getElementById("fournisseurs-data").textContent);
  var champ = document.getElementById("fournisseur");
  var cache = document.getElementById("fournisseur_id");
  var liste = document.getElementById("fournisseur-liste");
  function norm(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase(); }
  function choisir(f) {
    champ.value = f.nom;
    cache.value = f.id;
    liste.hidden = true;
    champ.setAttribute("aria-expanded", "false");
  }
  function proposer() {
    var q = norm(champ.value.trim());
    cache.value = "";
    liste.innerHTML = "";
    if (q.length < 2 || champ.readOnly) { liste.hidden = true; return; }
    data.filter(function (f) { return norm(f.nom).indexOf(q) >= 0; }).slice(0, 8).forEach(function (f, i) {
      var li = document.createElement("li");
      li.setAttribute("role", "option");
      li.textContent = f.nom + " — " + f.code;
      if (i === 0) li.className = "on";
      li.addEventListener("mousedown", function (ev) { ev.preventDefault(); choisir(f); });
      li._f = f;
      liste.appendChild(li);
    });
    var creer = document.createElement("li");
    creer.setAttribute("role", "option");
    creer.className = "creer" + (liste.children.length ? "" : " on");
    creer.textContent = "+ Créer le fournisseur « " + champ.value.trim() + " »";
    creer.addEventListener("mousedown", function (ev) { ev.preventDefault(); ouvrirCreation(); });
    liste.appendChild(creer);
    liste.hidden = false;
    champ.setAttribute("aria-expanded", "true");
  }
  champ.addEventListener("input", proposer);
  champ.addEventListener("blur", function () { setTimeout(function () { liste.hidden = true; }, 150); });
  champ.addEventListener("keydown", function (ev) {
    if (liste.hidden) return;
    var items = Array.prototype.slice.call(liste.children);
    var i = items.findIndex(function (li) { return li.classList.contains("on"); });
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      ev.preventDefault();
      if (i >= 0) items[i].classList.remove("on");
      i = ev.key === "ArrowDown" ? Math.min(items.length - 1, i + 1) : Math.max(0, i - 1);
      items[i].classList.add("on");
    } else if (ev.key === "Enter") {
      ev.preventDefault();
      if (i >= 0 && items[i]._f) choisir(items[i]._f); else if (i >= 0) ouvrirCreation();
    } else if (ev.key === "Escape") {
      liste.hidden = true;
    }
  });

  var modale = document.getElementById("modale-fournisseur");
  function ouvrirCreation() {
    liste.hidden = true;
    document.getElementById("nf-nom").value = champ.value.trim();
    document.getElementById("nf-erreur").textContent = "";
    modale.hidden = false;
    document.getElementById("nf-nom").focus();
  }
  document.getElementById("nf-creer").addEventListener("click", function () {
    var corps = new FormData();
    corps.append("_csrf", form.querySelector('[name="_csrf"]').value);
    corps.append("nom", document.getElementById("nf-nom").value);
    corps.append("pays", document.getElementById("nf-pays").value);
    corps.append("tva", document.getElementById("nf-tva").value);
    fetch(form.dataset.creer, { method: "POST", body: corps, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (f) {
        if (f.erreur) { document.getElementById("nf-erreur").textContent = f.erreur; return; }
        data.push(f);
        choisir(f);
        modale.hidden = true;
        document.getElementById("fournisseur-note").textContent = "Fournisseur créé : " + f.nom + " (" + f.code + ").";
      });
  });

  // Fenêtres de confirmation (validation, et « Sauvegarder » en v2 si activé).
  var confirmation = document.getElementById("modale-confirmation");
  var enAttente = null;
  form.querySelectorAll("button[data-confirm]").forEach(function (btn) {
    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      enAttente = btn.value;
      document.getElementById("confirmation-texte").textContent = btn.dataset.confirm;
      confirmation.hidden = false;
      document.getElementById("confirmation-oui").focus();
    });
  });
  document.getElementById("confirmation-oui").addEventListener("click", function () {
    var h = document.createElement("input");
    h.type = "hidden"; h.name = "action"; h.value = enAttente;
    form.appendChild(h);
    form.submit();
  });
})();
