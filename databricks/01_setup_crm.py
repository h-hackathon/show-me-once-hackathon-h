# Databricks notebook source
# MAGIC %md
# MAGIC # Show me once — setup de la base CRM fictive
# MAGIC Crée `workspace.decathlon_crm` : 5 tables reliées (clients, campagnes, envois, evenements, commandes)
# MAGIC et les 10 notebooks `rapport_<PAYS>` dans ton dossier `show-me-once`. À lancer une seule fois (Run all).
# MAGIC Données 100 % fictives, générées avec une graine fixe : identiques à la vérité terrain du repo.

# COMMAND ----------

CATALOGUE, SCHEMA = "workspace", "decathlon_crm"

# COMMAND ----------

# --- crm_data : base CRM fictive « Decathlon » (bibliothèque standard uniquement) -------------------------
# Ce fichier est recopié tel quel dans le notebook Databricks de setup : les données créées dans Databricks
# et la vérité terrain calculée en local sont donc STRICTEMENT identiques (même graine aléatoire).
#
# 5 tables reliées : clients ─< envois >─ campagnes,  envois ─< evenements,  clients ─< commandes >─ campagnes
#
# Pièges cachés dans la semaine du rapport (SEMAINE) :
#   FR : une campagne « [TEST] … » envoyée à la liste interne   → à exclure du rapport
#   IT : un bug de tracking duplique les ouvertures (taux > 100 %) → ne pas publier la ligne, prévenir
#   CH : aucune campagne envoyée cette semaine                  → ne pas toucher l'onglet, prévenir
import random
from datetime import date, timedelta

PAYS = ["FR", "IT", "ES", "DE", "BE", "PT", "NL", "PL", "GB", "CH"]
SEMAINE = "2026-10-26"             # lundi de la semaine du rapport (dernière semaine complète)
SEMAINE_PRECEDENTE = "2026-10-19"  # état du dashboard avant la mise à jour
DEBUT, FIN = date(2026, 9, 7), date(2026, 11, 6)
SEED = 42

SPORTS = ["Running", "Randonnée", "Vélo", "Natation", "Fitness", "Ski", "Football", "Tennis", "Yoga", "Camping"]
THEMES = ["Nouveautés", "Petits prix", "Conseils d'expert", "Spécial week-end", "Essentiels de saison"]
SEGMENTS = ["Nouveau", "Régulier", "Fidèle", "Inactif"]
VILLES = {"FR": ["Paris", "Lyon", "Lille", "Bordeaux"], "IT": ["Milano", "Roma", "Torino"], "ES": ["Madrid", "Barcelona", "Sevilla"],
          "DE": ["Berlin", "München", "Hamburg"], "BE": ["Bruxelles", "Anvers", "Liège"], "PT": ["Lisboa", "Porto"],
          "NL": ["Amsterdam", "Rotterdam"], "PL": ["Warszawa", "Kraków"], "GB": ["London", "Manchester"], "CH": ["Genève", "Zürich", "Lausanne"]}

# colonnes de chaque table, dans l'ordre (types Spark pour le notebook)
SCHEMAS = {
    "clients": "client_id STRING, pays STRING, ville STRING, segment STRING, date_inscription DATE, optin_email BOOLEAN",
    "campagnes": "campagne_id STRING, pays STRING, nom STRING, sport STRING, objet_email STRING, date_envoi DATE",
    "envois": "envoi_id STRING, campagne_id STRING, client_id STRING, date_envoi DATE",
    "evenements": "evenement_id STRING, envoi_id STRING, type STRING, date_evenement DATE",
    "commandes": "commande_id STRING, client_id STRING, campagne_id STRING, montant_eur DOUBLE, date_commande DATE",
}
CLES = {  # clés primaires / étrangères (contraintes informatives Unity Catalog)
    "clients": ("client_id", []),
    "campagnes": ("campagne_id", []),
    "envois": ("envoi_id", [("campagne_id", "campagnes"), ("client_id", "clients")]),
    "evenements": ("evenement_id", [("envoi_id", "envois")]),
    "commandes": ("commande_id", [("client_id", "clients")]),
}
COLONNES_RAPPORT = ["campagne_id", "campagne", "date_envoi", "envois", "ouvertures", "clics",
                    "desabonnements", "commandes", "ca_eur", "taux_ouverture", "taux_clic"]


def _d(s):
    return date.fromisoformat(s) if isinstance(s, str) else s


def generate(seed=SEED):
    """Renvoie {table: [tuple, …]} dans l'ordre des colonnes de SCHEMAS. Uniquement r.random() : stable d'une version de Python à l'autre."""
    r = random.Random(seed)
    pick = lambda seq: seq[int(r.random() * len(seq))]
    semaine = _d(SEMAINE)
    clients, campagnes, envois, evenements, commandes = [], [], [], [], []
    par_pays = {}

    for pays in PAYS:
        n = 1200 + int(r.random() * 600)
        liste = []
        for _ in range(n):
            cid = f"C{len(clients) + 1:06d}"
            inscription = date(2019, 1, 1) + timedelta(days=int(r.random() * 2700))
            optin = r.random() < 0.85
            clients.append((cid, pays, pick(VILLES[pays]), pick(SEGMENTS), inscription, optin))
            if optin:
                liste.append(cid)
        par_pays[pays] = liste

    for pays in PAYS:
        k, lundi = 0, DEBUT
        while lundi <= FIN:
            jours = [1, 3]  # mardi et jeudi
            if pays == "CH" and lundi == semaine:
                jours = []  # piège : pas de campagne CH cette semaine
            for j in jours:
                envoi = lundi + timedelta(days=j)
                if envoi > FIN:
                    continue
                k += 1
                sport, theme = pick(SPORTS), pick(THEMES)
                campagnes.append((f"CMP-{pays}-{k:03d}", pays, f"{sport} — {theme}", sport,
                                  f"{theme} {sport.lower()} : on vous a sélectionné le meilleur", envoi))
            if pays == "FR" and lundi == semaine:
                k += 1  # piège : campagne de test envoyée à la liste interne
                campagnes.append((f"CMP-FR-{k:03d}", "FR", "[TEST] Newsletter Running", "Running",
                                  "TEST - ne pas tenir compte", lundi + timedelta(days=2)))
            lundi += timedelta(days=7)

    bug_it = next(c[0] for c in campagnes if c[1] == "IT" and c[5] >= semaine)  # 1re campagne IT de la semaine

    for cmp_id, pays, nom, _, _, d_envoi in campagnes:
        test = nom.startswith("[TEST]")
        frac = 0 if test else 0.35 + r.random() * 0.25
        p_open = 0.18 + r.random() * 0.20
        destinataires = par_pays[pays][:12] if test else [c for c in par_pays[pays] if r.random() < frac]
        for cid in destinataires:
            eid = f"E{len(envois) + 1:07d}"
            envois.append((eid, cmp_id, cid, d_envoi))
            if r.random() < 0.01:
                evenements.append((f"V{len(evenements) + 1:07d}", eid, "rebond", d_envoi))
                continue
            if r.random() < p_open:
                ouvertures = 2 if r.random() < 0.12 else 1
                if cmp_id == bug_it:
                    ouvertures *= 4  # piège : le pixel de tracking compte chaque ouverture 4 fois
                for _ in range(ouvertures):
                    evenements.append((f"V{len(evenements) + 1:07d}", eid, "ouverture",
                                       d_envoi + timedelta(days=int(r.random() * 3))))
                if r.random() < 0.15:
                    jour = d_envoi + timedelta(days=int(r.random() * 3))
                    evenements.append((f"V{len(evenements) + 1:07d}", eid, "clic", jour))
                    if r.random() < 0.12:
                        montant = round(15 + r.random() * 235, 2)
                        commandes.append((f"O{len(commandes) + 1:06d}", cid, cmp_id, montant, jour))
                if r.random() < 0.004:
                    evenements.append((f"V{len(evenements) + 1:07d}", eid, "desabonnement", d_envoi))

    tous = [c[0] for c in clients]
    for _ in range(2500):  # commandes hors campagne (non attribuées)
        commandes.append((f"O{len(commandes) + 1:06d}", pick(tous), None, round(10 + r.random() * 300, 2),
                          DEBUT + timedelta(days=int(r.random() * (FIN - DEBUT).days))))

    return {"clients": clients, "campagnes": campagnes, "envois": envois,
            "evenements": evenements, "commandes": commandes}


def report(tables, pays, semaine=SEMAINE):
    """Même calcul que le SQL du notebook rapport_<PAYS> (la vérité terrain)."""
    debut = _d(semaine)
    fin = debut + timedelta(days=7)
    camps = sorted((c for c in tables["campagnes"] if c[1] == pays and debut <= c[5] < fin), key=lambda c: (c[5], c[0]))
    ids = {c[0] for c in camps}
    env, env_cmp = {}, {}
    for eid, cmp_id, _, _ in tables["envois"]:
        if cmp_id in ids:
            env[cmp_id] = env.get(cmp_id, 0) + 1
            env_cmp[eid] = cmp_id
    ev = {}
    for _, eid, typ, _ in tables["evenements"]:
        if eid in env_cmp:
            key = (env_cmp[eid], typ)
            ev[key] = ev.get(key, 0) + 1
    cmd = {}
    for _, _, cmp_id, montant, _ in tables["commandes"]:
        if cmp_id in ids:
            n, ca = cmd.get(cmp_id, (0, 0.0))
            cmd[cmp_id] = (n + 1, ca + montant)
    rows = []
    for cmp_id, _, nom, _, _, d_envoi in camps:
        e = env.get(cmp_id, 0)
        o, c = ev.get((cmp_id, "ouverture"), 0), ev.get((cmp_id, "clic"), 0)
        n, ca = cmd.get(cmp_id, (0, 0.0))
        rows.append({"campagne_id": cmp_id, "campagne": nom, "date_envoi": d_envoi.isoformat(), "envois": e,
                     "ouvertures": o, "clics": c, "desabonnements": ev.get((cmp_id, "desabonnement"), 0),
                     "commandes": n, "ca_eur": round(ca, 2),
                     "taux_ouverture": round(100 * o / e, 1) if e else 0.0,
                     "taux_clic": round(100 * c / e, 1) if e else 0.0})
    return rows


def apply_rules(rows):
    """Règles métier de la personne (ce que la Skill doit apprendre). Renvoie (lignes gardées, [(id, raison)])."""
    kept, excluded = [], []
    for row in rows:
        if row["campagne"].startswith("[TEST]"):
            excluded.append((row["campagne_id"], "campagne de test"))
        elif row["taux_ouverture"] > 100:
            excluded.append((row["campagne_id"], "taux d'ouverture > 100 % (bug de tracking)"))
        else:
            kept.append(row)
    return kept, excluded


def expected(tables, pays):
    """Ce que l'onglet <pays> du Sheet doit contenir après la mise à jour, et si l'agent doit prévenir un humain."""
    rows = report(tables, pays, SEMAINE)
    if not rows:  # rien cette semaine : on ne touche pas à l'onglet, on prévient
        return previous(tables, pays), True, "aucune campagne cette semaine"
    kept, excluded = apply_rules(rows)
    bug = [e for e in excluded if "tracking" in e[1]]
    return kept, bool(bug), "; ".join(f"{i} : {raison}" for i, raison in bug)


def previous(tables, pays):
    """Contenu de l'onglet avant la mise à jour (rapport de la semaine précédente, règles appliquées)."""
    return apply_rules(report(tables, pays, SEMAINE_PRECEDENTE))[0]
# --- fin crm_data ---

# COMMAND ----------

tables = generate()
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGUE}.{SCHEMA}")
for nom, lignes in tables.items():
    df = spark.createDataFrame(lignes, schema=SCHEMAS[nom])
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOGUE}.{SCHEMA}.{nom}")
    print(f"✅ {nom} : {df.count()} lignes")

# COMMAND ----------

# Clés primaires / étrangères (contraintes informatives Unity Catalog). Facultatif : une erreur ici ne bloque rien.
for nom, (pk, fks) in CLES.items():
    t = f"{CATALOGUE}.{SCHEMA}.{nom}"
    try:
        spark.sql(f"ALTER TABLE {t} ALTER COLUMN {pk} SET NOT NULL")
        spark.sql(f"ALTER TABLE {t} ADD CONSTRAINT pk_{nom} PRIMARY KEY ({pk})")
    except Exception as e:
        print(f"ℹ️ PK {nom} : {str(e)[:120]}")
for nom, (pk, fks) in CLES.items():
    for col, ref in fks:
        try:
            spark.sql(f"ALTER TABLE {CATALOGUE}.{SCHEMA}.{nom} ADD CONSTRAINT fk_{nom}_{col} "
                      f"FOREIGN KEY ({col}) REFERENCES {CATALOGUE}.{SCHEMA}.{ref}")
        except Exception as e:
            print(f"ℹ️ FK {nom}.{col} : {str(e)[:120]}")
print("✅ contraintes")

# COMMAND ----------

RAPPORT = '# Databricks notebook source\n# MAGIC %md\n# MAGIC # Rapport hebdo des campagnes email — __PAYS__\n# MAGIC Une ligne par campagne envoyée pendant la semaine. Sources : `workspace.decathlon_crm.campagnes`, `envois`, `evenements`, `commandes`.\n\n# COMMAND ----------\n\nPAYS = "__PAYS__"\nSEMAINE = "__SEMAINE__"  # lundi de la semaine du rapport\n\n# COMMAND ----------\n\ndf = spark.sql(f"""\nWITH c AS (\n  SELECT campagne_id, nom, date_envoi FROM workspace.decathlon_crm.campagnes\n  WHERE pays = \'{PAYS}\' AND date_envoi >= DATE\'{SEMAINE}\' AND date_envoi < DATE_ADD(DATE\'{SEMAINE}\', 7)\n),\ne AS (SELECT envoi_id, campagne_id FROM workspace.decathlon_crm.envois WHERE campagne_id IN (SELECT campagne_id FROM c)),\nnb_envois AS (SELECT campagne_id, COUNT(*) AS envois FROM e GROUP BY campagne_id),\nnb_evenements AS (\n  SELECT e.campagne_id,\n         SUM(CASE WHEN ev.type = \'ouverture\' THEN 1 ELSE 0 END) AS ouvertures,\n         SUM(CASE WHEN ev.type = \'clic\' THEN 1 ELSE 0 END) AS clics,\n         SUM(CASE WHEN ev.type = \'desabonnement\' THEN 1 ELSE 0 END) AS desabonnements\n  FROM workspace.decathlon_crm.evenements ev JOIN e ON ev.envoi_id = e.envoi_id\n  GROUP BY e.campagne_id\n),\nnb_commandes AS (\n  SELECT campagne_id, COUNT(*) AS commandes, ROUND(SUM(montant_eur), 2) AS ca_eur\n  FROM workspace.decathlon_crm.commandes WHERE campagne_id IN (SELECT campagne_id FROM c) GROUP BY campagne_id\n)\nSELECT c.campagne_id, c.nom AS campagne, c.date_envoi,\n       COALESCE(n.envois, 0) AS envois, COALESCE(v.ouvertures, 0) AS ouvertures, COALESCE(v.clics, 0) AS clics,\n       COALESCE(v.desabonnements, 0) AS desabonnements, COALESCE(o.commandes, 0) AS commandes,\n       COALESCE(o.ca_eur, 0) AS ca_eur,\n       ROUND(100 * COALESCE(v.ouvertures, 0) / n.envois, 1) AS taux_ouverture,\n       ROUND(100 * COALESCE(v.clics, 0) / n.envois, 1) AS taux_clic\nFROM c\nLEFT JOIN nb_envois n ON c.campagne_id = n.campagne_id\nLEFT JOIN nb_evenements v ON c.campagne_id = v.campagne_id\nLEFT JOIN nb_commandes o ON c.campagne_id = o.campagne_id\nORDER BY c.date_envoi, c.campagne_id\n""")\ndisplay(df)\n\n# COMMAND ----------\n\n# MAGIC %md\n# MAGIC ## Résultat à copier dans le Google Sheet (onglet __PAYS__)\n# MAGIC Texte séparé par des tabulations : à coller en cellule A1, Google Sheets répartit les colonnes tout seul.\n\n# COMMAND ----------\n\nprint(df.toPandas().to_csv(sep="\\t", index=False).strip() or "AUCUNE LIGNE")\n'

import base64
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ImportFormat, Language
w = WorkspaceClient()
dossier = f"/Users/{w.current_user.me().user_name}/show-me-once"
w.workspace.mkdirs(dossier)
for pays in PAYS:
    src = RAPPORT.replace("__PAYS__", pays).replace("__SEMAINE__", SEMAINE)
    w.workspace.import_(path=f"{dossier}/rapport_{pays}", format=ImportFormat.SOURCE, language=Language.PYTHON,
                        content=base64.b64encode(src.encode()).decode(), overwrite=True)
    print(f"📓 {dossier}/rapport_{pays}")

# COMMAND ----------

display(spark.sql(f"""
SELECT c.pays, COUNT(DISTINCT c.campagne_id) AS campagnes, COUNT(e.envoi_id) AS envois
FROM {CATALOGUE}.{SCHEMA}.campagnes c LEFT JOIN {CATALOGUE}.{SCHEMA}.envois e USING (campagne_id)
GROUP BY c.pays ORDER BY c.pays"""))
