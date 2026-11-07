"""Site web COMPTAREX Cabinet 6.2 : pages HTML fabriquées par le serveur, aucune API pour l'agent.

Seule exception : l'API technique /api/* (JSON, en-tête X-Admin-Token), réservée au contrôle du banc
de test (lire les factures réellement enregistrées, remettre à zéro, basculer l'interface v1/v2).

    uv run comptarex-web        # http://127.0.0.1:8042
"""
from __future__ import annotations

import hmac
import secrets
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, Response, abort, g, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix

from .. import compta, config, db

config.verifier_production()
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config.update(PERMANENT_SESSION_LIFETIME=timedelta(days=30), SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_NAME="COMPTAREXSESSID", SESSION_COOKIE_SECURE=config.PROD)
if config.PROD:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)   # HTTPS terminé par Railway

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]
PAR_PAGE = 15


def conn():
    if "conn" not in g:
        g.conn = db.connect()
    return g.conn


@app.teardown_appcontext
def _close(_exc):
    c = g.pop("conn", None)
    if c is not None:
        c.close()


app.jinja_env.filters["fmt"] = compta.fmt
app.jinja_env.filters["date_fr"] = compta.date_fr


@app.context_processor
def _contexte():
    now = datetime.now()
    d = compta.dossier(conn(), session["dossier"]) if session.get("dossier") else None
    ui = compta.ui(conn())
    return {
        "ui": ui, "version_logiciel": "6.3.0" if ui["version"] == "v2" else "6.2.4",
        "version_courte": "6.3" if ui["version"] == "v2" else "6.2",
        "dossier": d, "dossier_libelle": compta.libelle_dossier(d) if d else "",
        "lecture_seule": session.get("lecture_seule", False),
        "maintenant": f"{JOURS[now.weekday()]} {now.day:02d} {MOIS[now.month - 1]} {now.year} — {now:%H:%M}",
        "utilisateur": config.USER_CODE, "cabinet": config.CABINET, "csrf": session.get("csrf", ""),
        "nb_non_lus": conn().execute("SELECT COUNT(*) FROM messages WHERE dossier = ? AND lu = 0 AND sens = 'recu'",
                                     (d["code"],)).fetchone()[0] if d else 0,
    }


@app.before_request
def _csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST" and not request.path.startswith("/api/"):
        if not hmac.compare_digest(request.form.get("_csrf", "") or request.headers.get("X-CSRF", ""),
                                   session["csrf"]):
            return render_template("expire.html"), 400


def connecte(vue):
    @wraps(vue)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return vue(*args, **kwargs)
    return wrapper


def avec_dossier(vue):
    @wraps(vue)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        if not session.get("dossier"):
            return redirect(url_for("dossiers"))
        return vue(*args, **kwargs)
    return wrapper


def page_param() -> int:
    try:
        return max(1, int(request.args.get("page", 1)))
    except ValueError:
        return 1


def paginer(rows: list, par_page: int = PAR_PAGE):
    page = page_param()
    pages = max(1, -(-len(rows) // par_page))
    page = min(page, pages)
    return rows[(page - 1) * par_page: page * par_page], page, pages


# ---------------------------------------------------------------- connexion et dossiers

@app.get("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")


@app.get("/")
def accueil():
    return redirect(url_for("bureau") if session.get("dossier") else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    erreur = None
    if request.method == "POST":
        email, mdp = request.form.get("email", "").strip(), request.form.get("password", "")
        ok = hmac.compare_digest(email.lower(), config.LOGIN.lower()) and hmac.compare_digest(mdp, config.PASSWORD)
        if ok and request.form.get("exercice", "2026") != "2026":
            erreur = "Exercice archivé : seul l'exercice 2026 est ouvert sur ce poste (code 0x23)."
        elif ok:
            csrf = session.get("csrf")
            session.clear()
            session.permanent = True
            session.update(user=config.USER_CODE, csrf=csrf or secrets.token_hex(16))
            return redirect(url_for("dossiers"))
        else:
            session["essais"] = session.get("essais", 0) + 1
            erreur = (f"Identifiants incorrects (code 0x12). Il vous reste {max(1, 3 - session['essais'])} "
                      "essai(s) avant blocage du compte.")
    return render_template("login.html", erreur=erreur, email=request.form.get("email", ""))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dossiers", methods=["GET", "POST"])
@connecte
def dossiers():
    if request.method == "POST":
        code = request.form.get("dossier")
        if not code:
            return _dossiers_page(message="Sélectionnez un dossier dans la liste avant de cliquer sur « Ouvrir ».")
        return redirect(url_for("ouvrir_dossier", code=code, mode=request.form.get("mode", "")))
    return _dossiers_page()


def _dossiers_page(message=None):
    q, collab, etat = request.args.get("q", ""), request.args.get("collab", ""), request.args.get("etat", "")
    rows, total, page, pages = compta.dossiers(conn(), q, collab, etat, page_param())
    return render_template("dossiers.html", rows=rows, total=total, page=page, pages=pages, q=q, collab=collab,
                           etat=etat, message=message, libelle=compta.libelle_dossier, sans_dossier=True)


@app.get("/dossiers/<code>/ouvrir")
@connecte
def ouvrir_dossier(code):
    d = compta.dossier(conn(), code) or abort(404)
    consultation = request.args.get("mode") == "consultation"
    if d["verrou"] and d["verrou"] != config.USER_CODE and not consultation:
        return _dossiers_page(message=f"Le dossier {compta.libelle_dossier(d)} est verrouillé par {d['verrou']} "
                              "(saisie en cours sur un autre poste). Utilisez « Ouvrir en consultation ».")
    session.update(dossier=code, lecture_seule=consultation or d["etat"] == "Clôturé")
    return redirect(url_for("bureau"))


@app.get("/bureau")
@avec_dossier
def bureau():
    c, code = conn(), session["dossier"]
    pieces = compta.pieces(c, code)
    p = max(1, int(request.args.get("p", 1) or 1))
    p_max = max(1, -(-len(pieces) // 5))
    p = min(p, p_max)
    return render_template("bureau.html", section="saisie", messages=compta.messages(c, code)[:4],
                           pieces=pieces[(p - 1) * 5: p * 5], p=p, p_max=p_max, nb_pieces=len(pieces),
                           infos=compta.infos_dossier(c, code),
                           derniere_situation=c.execute(
                               "SELECT MAX(created_at) FROM editions WHERE dossier = ?", (code,)).fetchone()[0])


@app.get("/module/<nom>")
@avec_dossier
def module(nom):
    return render_template("indisponible.html", nom=nom.replace("-", " "))


# ---------------------------------------------------------------- factures à traiter et saisie

@app.get("/inbox")
@avec_dossier
def inbox():
    return render_template("inbox.html", section="saisie", pieces=compta.pieces(conn(), session["dossier"]))


@app.get("/inbox/<code>.pdf")
@connecte
def inbox_pdf(code):
    p = compta.piece(conn(), code) or abort(404)
    return send_from_directory(config.INBOX, p["fichier"], mimetype="application/pdf")


@app.get("/factures")
@avec_dossier
def liste_factures():
    rows, page, pages = paginer(compta.factures(conn(), session["dossier"]))
    return render_template("factures.html", section="saisie", rows=rows, page=page, pages=pages)


def _form_facture() -> dict:
    f = request.form
    lignes = [{"libelle": l, "quantite": q, "prix_unitaire": p, "taxe": t}
              for l, q, p, t in zip(f.getlist("libelle"), f.getlist("quantite"), f.getlist("prix_unitaire"),
                                    f.getlist("taxe"))]
    return {"fournisseur": f.get("fournisseur", ""), "fournisseur_id": f.get("fournisseur_id", ""),
            "reference": f.get("reference", ""), "date": f.get("date", ""), "categorie": f.get("categorie", ""),
            "piece": f.get("piece", ""), "lignes": lignes}


def _lignes_affichees(lignes: list[dict]) -> tuple[list[dict], dict]:
    """Lignes du formulaire avec leur montant HT, et les totaux (lignes incomplètes ignorées)."""
    calculables = []
    for l in lignes:
        q, p = compta.parse_quantite(l["quantite"]), compta.parse_montant(l["prix_unitaire"])
        l["montant"] = compta.fmt(round(q * p)) if q and p is not None else ""
        if q and p is not None and l["taxe"] in compta.TAXES:
            calculables.append({"quantite": q, "prix_unitaire": p, "taxe": l["taxe"]})
    return lignes, compta.calcul(calculables)


def _rendu_facture(donnees, facture=None, erreurs=None, message=None):
    vides = [{"libelle": "", "quantite": "", "prix_unitaire": "", "taxe": "20 %"} for _ in range(3)]
    lignes, totaux = _lignes_affichees(donnees["lignes"] or vides)
    four = [{"id": r["id"], "nom": r["nom"], "code": r["code"]}
            for r in compta.fournisseurs(conn(), session["dossier"])]
    valide = bool(facture and facture["statut"] == "validated")
    return render_template("facture.html", section="saisie", d=donnees, lignes=lignes, totaux=totaux,
                           facture=facture, erreurs=erreurs or [], message=message, fournisseurs=four,
                           taxes=list(compta.TAXES), categories=compta.CATEGORIES,
                           piece=compta.piece(conn(), donnees["piece"]) if donnees.get("piece") else None,
                           fige=valide or session.get("lecture_seule"), v2=compta.ui(conn())["version"] == "v2")


def _traiter_facture(facture_id=None):
    donnees = _form_facture()
    action = request.form.get("action", "")
    facture = compta.facture(conn(), facture_id)
    if action == "ajouter_ligne":
        donnees["lignes"].append({"libelle": "", "quantite": "", "prix_unitaire": "", "taxe": "20 %"})
        return _rendu_facture(donnees, facture)
    if action.startswith("supprimer_"):
        i = int(action.split("_")[1])
        if 0 <= i < len(donnees["lignes"]):
            donnees["lignes"].pop(i)
        return _rendu_facture(donnees, facture)
    if session.get("lecture_seule"):
        return _rendu_facture(donnees, facture, ["Dossier ouvert en consultation : saisie impossible."])
    if action not in ("brouillon", "valider"):
        return _rendu_facture(donnees, facture)
    v2 = compta.ui(conn())["version"] == "v2"
    nouvel_id, erreurs = compta.enregistrer_facture(conn(), session["dossier"], donnees, facture_id,
                                                    valider=action == "valider", categorie_obligatoire=v2)
    if erreurs:
        return _rendu_facture(donnees, facture, erreurs)
    return redirect(url_for("voir_facture", facture_id=nouvel_id, ok=action))


@app.route("/factures/nouvelle", methods=["GET", "POST"])
@avec_dossier
def nouvelle_facture():
    if request.method == "POST":
        return _traiter_facture()
    piece = request.args.get("piece", "")
    p = compta.piece(conn(), piece)
    return _rendu_facture({"fournisseur": "", "fournisseur_id": "", "reference": "", "date": "", "categorie": "",
                           "piece": p["code"] if p else "", "lignes": []})


@app.route("/factures/<int:facture_id>", methods=["GET", "POST"])
@avec_dossier
def voir_facture(facture_id):
    f = compta.facture(conn(), facture_id)
    if not f or f["dossier"] != session["dossier"]:
        abort(404)
    if request.method == "POST":
        return _traiter_facture(facture_id)
    donnees = {"fournisseur": f["fournisseur"], "fournisseur_id": str(f["tiers_id"]), "reference": f["reference"],
               "date": compta.date_fr(f["date"]), "categorie": f["categorie"] or "", "piece": f["piece"] or "",
               "lignes": [{"libelle": l["libelle"], "quantite": f"{l['quantite']:g}".replace(".", ","),
                           "prix_unitaire": compta.fmt(l["prix_unitaire"]).replace(" ", ""), "taxe": l["taxe"]}
                          for l in compta.facture_lignes(conn(), facture_id)]}
    message = {"brouillon": f"Brouillon enregistré sous le n° {f['numero']}.",
               "valider": f"Facture n° {f['numero']} validée et comptabilisée (journal AC)."}.get(
        request.args.get("ok", ""))
    return _rendu_facture(donnees, f, message=message)


@app.post("/fournisseurs/creer")
@avec_dossier
def creer_fournisseur():
    if session.get("lecture_seule"):
        return jsonify(erreur="Dossier ouvert en consultation : création impossible."), 403
    try:
        t = compta.creer_fournisseur(conn(), session["dossier"], request.form.get("nom", ""),
                                     request.form.get("pays", "FR"), request.form.get("tva", ""))
    except ValueError as err:
        return jsonify(erreur=str(err)), 400
    return jsonify(id=t["id"], nom=t["nom"], code=t["code"])


# ---------------------------------------------------------------- éditions

SITUATION_DEFAUT = {"au": "", "type": "gestion", "comparatif": "aucun", "niveau": "3", "brouillard": "",
                    "abonnement": "", "francs": "1", "titre": "SITUATION INTERMEDIAIRE DE GESTION",
                    "orientation": "portrait", "police": "Courier New 9", "entete": "1", "numeroter": "1",
                    "soldes": "", "imprimante": "\\\\SRV-CAB01\\HP LaserJet 4050 PCL6", "exemplaires": "1",
                    "chemin": "C:\\COMPTAREX\\EDITIONS\\", "memoriser": ""}


@app.route("/editions/situation", methods=["GET", "POST"])
@avec_dossier
def situation():
    c = conn()
    if request.method == "GET":
        v = dict(SITUATION_DEFAUT, destination=compta.destination_defaut(c))
        return render_template("situation.html", section="editions", v=v, onglet="criteres")
    v = {k: request.form.get(k, "") for k in list(SITUATION_DEFAUT) + ["destination"]}
    onglet = request.form.get("onglet", "criteres")
    action = request.form.get("action", "")

    def boite(texte, titre="Message de la page Web"):
        return render_template("situation.html", section="editions", v=v, onglet=onglet,
                               boite={"titre": titre, "texte": texte})

    if action == "proprietes":
        return boite("Pilote d'impression non disponible sur ce poste. Contactez votre administrateur réseau.")
    if action == "apercu":
        return boite("Le composant d'aperçu nécessite Java 1.4.2. Installez-le depuis le CD-ROM Comptarex "
                     "ou contactez votre administrateur.")
    au = compta.parse_date_fr(v["au"])
    if au is None:
        return boite("Erreur 0x2F : date invalide. Saisissez la date d'arrêté au format JJ/MM/AAAA.")
    if not (compta.EXO_DEBUT <= au <= compta.EXO_FIN):
        return boite("La date d'arrêté doit être comprise dans l'exercice (01/01/2026 - 31/12/2026).")
    if v["type"] == "fiscale":
        return boite("Le module Liasse fiscale n'est pas installé sur ce poste (code 0x41).")
    if v["comparatif"] == "n1":
        return boite("Exercice N-1 non disponible : dossier repris en 2026 (balance d'ouverture uniquement).")
    if v["comparatif"] == "budget":
        return boite("Aucun budget n'a été saisi pour ce dossier.")
    if v["destination"] not in compta.DESTINATIONS:
        return boite("Choisissez une destination dans l'onglet Destination.")
    if v["memoriser"]:
        db.set_setting(c, "destination_defaut", v["destination"])
    if v["destination"] == "imprimante":
        return boite(f"Edition envoyée vers {v['imprimante']} (travail n° {4400 + secrets.randbelow(600)}). "
                     "Récupérez votre document à l'imprimante.")
    if v["destination"] == "pdf":
        return boite(f"Fichier enregistré sous {v['chemin'].rstrip(chr(92))}\\"
                     f"{compta.nom_fichier_situation(session['dossier'], au.isoformat())} sur le serveur du cabinet.")
    edition_id = compta.nouvelle_edition(c, session["dossier"], "situation", {**v, "au": au.isoformat()})
    return redirect(url_for("traitement", edition_id=edition_id))


def _edition_ou_404(edition_id):
    e = compta.edition(conn(), edition_id)
    if not e or e["dossier"] != session["dossier"]:
        abort(404)
    return e


@app.get("/editions/situation/<int:edition_id>/traitement")
@avec_dossier
def traitement(edition_id):
    _edition_ou_404(edition_id)
    return render_template("traitement.html", section="editions",
                           suite=url_for("resultat_situation", edition_id=edition_id))


@app.get("/editions/situation/<int:edition_id>")
@avec_dossier
def resultat_situation(edition_id):
    e = _edition_ou_404(edition_id)
    p = e["params"]
    s = compta.situation(conn(), session["dossier"], p["au"], bool(p.get("brouillard")), p.get("niveau", "3"),
                         bool(p.get("francs")))
    detail_pages = [s["detail"][i:i + 34] for i in range(0, len(s["detail"]), 34)] or [[]]
    pages = 1 + len(detail_pages)
    page = min(page_param(), pages)
    return render_template("situation_resultat.html", section="editions", e=e, p=p, s=s, page=page, pages=pages,
                           detail=detail_pages[page - 2] if page > 1 else [], niveau=compta.NIVEAUX.get(
                               p.get("niveau", "3"), ""), boite=_boite_viewer())


def _boite_viewer():
    action = request.args.get("action")
    if action == "imprimer":
        return {"titre": "Message de la page Web",
                "texte": "Edition envoyée vers \\\\SRV-CAB01\\HP LaserJet 4050 PCL6. Récupérez votre document "
                         "à l'imprimante."}
    if action == "exporter":
        return {"titre": "Message de la page Web",
                "texte": "Export Excel indisponible : le composant Office 2000 n'est pas installé sur ce poste."}
    return None


@app.route("/editions/situation/<int:edition_id>/transmettre", methods=["GET", "POST"])
@avec_dossier
def transmettre(edition_id):
    e = _edition_ou_404(edition_id)
    au = e["params"]["au"]
    destinataires = compta.DESTINATAIRES.get(session["dossier"], ["DIRIGEANT (client)"])
    v = {"a": destinataires[0], "objet": f"SITUATION AU {compta.date_fr(au)}",
         "corps": f"Bonjour,\n\nVeuillez trouver ci-joint la situation intermédiaire au {compta.date_fr(au)}, "
                  "provisoire.\n\nCordialement,\nC. Moreau",
         "pj": compta.nom_fichier_situation(session["dossier"], au)}
    if request.method == "POST":
        v.update(a=request.form.get("a", ""), objet=request.form.get("objet", ""),
                 corps=request.form.get("corps", ""))
        if session.get("lecture_seule"):
            return render_template("transmettre.html", section="editions", e=e, v=v, destinataires=destinataires,
                                   erreur="Dossier ouvert en consultation : envoi impossible.")
        if v["a"] not in destinataires or not v["objet"].strip():
            return render_template("transmettre.html", section="editions", e=e, v=v, destinataires=destinataires,
                                   erreur="Le destinataire et l'objet sont obligatoires.")
        mid = compta.envoyer_message(conn(), session["dossier"], v["a"], v["objet"], v["corps"], v["pj"])
        return render_template("transmettre.html", section="editions", e=e, v=v, destinataires=destinataires,
                               envoye=f"MSG-{date.today():%Y-%m}-{mid:04d}")
    return render_template("transmettre.html", section="editions", e=e, v=v, destinataires=destinataires)


@app.get("/editions/balance")
@avec_dossier
def balance():
    au_txt, niveau = request.args.get("au", ""), request.args.get("niveau", "6")
    rows, erreur = None, None
    if au_txt:
        au = compta.parse_date_fr(au_txt)
        if au is None:
            erreur = "Erreur 0x2F : date invalide (format JJ/MM/AAAA)."
        else:
            rows = compta.balance(conn(), session["dossier"], au.isoformat(),
                                  niveau if niveau in compta.NIVEAUX else "6", bool(request.args.get("brouillard")))
    page_rows, page, pages = paginer(rows or [], 30)
    totaux = {k: sum(r[k] for r in rows or []) for k in ("debit", "credit", "solde_debiteur", "solde_crediteur")}
    return render_template("balance.html", section="editions", au=au_txt, niveau=niveau, rows=page_rows,
                           calcule=rows is not None, page=page, pages=pages, totaux=totaux, erreur=erreur,
                           niveaux=compta.NIVEAUX, brouillard=request.args.get("brouillard", ""))


# ---------------------------------------------------------------- consultation

@app.get("/consultation/compte")
@avec_dossier
def consultation_compte():
    c, code = conn(), session["dossier"]
    compte, du_txt, au_txt = request.args.get("compte", ""), request.args.get("du", "01/01/2026"), \
        request.args.get("au", "31/12/2026")
    resultat, erreur, lignes, page, pages = None, None, [], 1, 1
    if compte:
        du, au = compta.parse_date_fr(du_txt), compta.parse_date_fr(au_txt)
        if du is None or au is None:
            erreur = "Erreur 0x2F : date invalide (format JJ/MM/AAAA)."
        else:
            resultat = compta.grand_livre(c, code, compte, du.isoformat(), au.isoformat())
            lignes, page, pages = paginer(resultat["lignes"])
    return render_template("compte.html", section="consultation", comptes=compta.comptes(c, code), compte=compte,
                           du=du_txt, au=au_txt, r=resultat, lignes=lignes, page=page, pages=pages, erreur=erreur)


@app.get("/consultation/recherche")
@avec_dossier
def recherche():
    a = request.args
    rows, erreur = None, None
    if "journal" in a:
        du, au = compta.parse_date_fr(a.get("du", "")), compta.parse_date_fr(a.get("au", ""))
        montant = compta.parse_montant(a.get("montant", ""))
        if not a.get("journal"):
            erreur = "Le code journal est obligatoire (code 0x07)."
        elif du is None or au is None:
            erreur = "Erreur 0x2F : date invalide (format JJ/MM/AAAA)."
        elif a.get("montant") and montant is None:
            erreur = "Montant invalide."
        else:
            rows = compta.recherche(conn(), session["dossier"], a["journal"], montant, a.get("libelle", ""),
                                    du.isoformat(), au.isoformat())
    page_rows, page, pages = paginer(rows or [])
    return render_template("recherche.html", section="consultation", a=a, rows=page_rows, total=len(rows or []),
                           calcule=rows is not None, page=page, pages=pages, erreur=erreur, journaux=compta.JOURNAUX)


# ---------------------------------------------------------------- messagerie

@app.get("/messagerie")
@avec_dossier
def messagerie():
    boite = "envoye" if request.args.get("boite") == "envoyes" else "recu"
    rows, page, pages = paginer(compta.messages(conn(), session["dossier"], boite))
    return render_template("messagerie.html", section="communication", rows=rows, boite=boite, page=page,
                           pages=pages)


@app.get("/messagerie/<int:message_id>")
@avec_dossier
def lire_message(message_id):
    m = compta.message(conn(), message_id)
    if not m or m["dossier"] != session["dossier"]:
        abort(404)
    return render_template("message.html", section="communication", m=m)


@app.route("/messagerie/nouveau", methods=["GET", "POST"])
@avec_dossier
def nouveau_message():
    destinataires = compta.DESTINATAIRES.get(session["dossier"], ["DIRIGEANT (client)"])
    v = {"a": request.form.get("a", ""), "objet": request.form.get("objet", request.args.get("objet", "")),
         "corps": request.form.get("corps", "")}
    if request.method == "POST":
        if session.get("lecture_seule"):
            erreur = "Dossier ouvert en consultation : envoi impossible."
        elif v["a"] not in destinataires or not v["objet"].strip():
            erreur = "Le destinataire et l'objet sont obligatoires."
        else:
            mid = compta.envoyer_message(conn(), session["dossier"], v["a"], v["objet"], v["corps"])
            return redirect(url_for("lire_message", message_id=mid))
        return render_template("message_nouveau.html", section="communication", v=v, destinataires=destinataires,
                               erreur=erreur)
    return render_template("message_nouveau.html", section="communication", v=v, destinataires=destinataires)


# ---------------------------------------------------------------- API technique (contrôle du banc de test)

def _admin():
    token = request.headers.get("X-Admin-Token", "")
    if not config.ADMIN_TOKEN or not hmac.compare_digest(token, config.ADMIN_TOKEN):
        abort(401)


@app.errorhandler(401)
def _non_autorise(_err):
    return jsonify(error="X-Admin-Token manquant ou invalide"), 401


@app.get("/api/health")
def api_health():
    return jsonify(ok=True, ui_version=compta.ui(conn())["version"])


@app.get("/api/invoices")
def api_invoices():
    _admin()
    c = conn()
    return jsonify([compta.facture_api(c, f) for f in compta.factures(c, reference=request.args.get("reference"))])


@app.post("/api/admin/reset")
def api_reset():
    _admin()
    return jsonify(compta.reset_saisies(conn()))


@app.route("/api/admin/ui-version", methods=["GET", "POST"])
def api_ui_version():
    _admin()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(compta.set_ui(conn(), body.get("version", ""), body.get("confirm")))
        except ValueError as err:
            return jsonify(error=str(err)), 400
    return jsonify(compta.ui(conn()))


def main() -> None:
    db.connect().close()
    print(f"COMPTAREX Cabinet : http://{config.HOST}:{config.PORT}  (base : {config.DB_PATH})")
    app.run(host=config.HOST, port=config.PORT, threaded=True, debug=False)


if __name__ == "__main__":
    main()
