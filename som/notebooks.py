"""Construit le notebook Databricks de setup (databricks/01_setup_crm.py) à partir de som/crm_data.py.

À importer dans Databricks (Workspace > Import > fichier) puis « Run all » une seule fois : il crée
le schéma, les 5 tables reliées (avec clés primaires/étrangères) et les 10 notebooks rapport_<PAYS>.
"""
from pathlib import Path

from .config import ROOT

CATALOGUE, SCHEMA = "workspace", "decathlon_crm"
CELL = "\n\n# COMMAND ----------\n\n"

RAPPORT = '''# Databricks notebook source
# MAGIC %md
# MAGIC # Rapport hebdo des campagnes email — __PAYS__
# MAGIC Une ligne par campagne envoyée pendant la semaine. Sources : `__CAT__.campagnes`, `envois`, `evenements`, `commandes`.

# COMMAND ----------

PAYS = "__PAYS__"
SEMAINE = "__SEMAINE__"  # lundi de la semaine du rapport

# COMMAND ----------

df = spark.sql(f"""
WITH c AS (
  SELECT campagne_id, nom, date_envoi FROM __CAT__.campagnes
  WHERE pays = '{PAYS}' AND date_envoi >= DATE'{SEMAINE}' AND date_envoi < DATE_ADD(DATE'{SEMAINE}', 7)
),
e AS (SELECT envoi_id, campagne_id FROM __CAT__.envois WHERE campagne_id IN (SELECT campagne_id FROM c)),
nb_envois AS (SELECT campagne_id, COUNT(*) AS envois FROM e GROUP BY campagne_id),
nb_evenements AS (
  SELECT e.campagne_id,
         SUM(CASE WHEN ev.type = 'ouverture' THEN 1 ELSE 0 END) AS ouvertures,
         SUM(CASE WHEN ev.type = 'clic' THEN 1 ELSE 0 END) AS clics,
         SUM(CASE WHEN ev.type = 'desabonnement' THEN 1 ELSE 0 END) AS desabonnements
  FROM __CAT__.evenements ev JOIN e ON ev.envoi_id = e.envoi_id
  GROUP BY e.campagne_id
),
nb_commandes AS (
  SELECT campagne_id, COUNT(*) AS commandes, ROUND(SUM(montant_eur), 2) AS ca_eur
  FROM __CAT__.commandes WHERE campagne_id IN (SELECT campagne_id FROM c) GROUP BY campagne_id
)
SELECT c.campagne_id, c.nom AS campagne, c.date_envoi,
       COALESCE(n.envois, 0) AS envois, COALESCE(v.ouvertures, 0) AS ouvertures, COALESCE(v.clics, 0) AS clics,
       COALESCE(v.desabonnements, 0) AS desabonnements, COALESCE(o.commandes, 0) AS commandes,
       COALESCE(o.ca_eur, 0) AS ca_eur,
       ROUND(100 * COALESCE(v.ouvertures, 0) / n.envois, 1) AS taux_ouverture,
       ROUND(100 * COALESCE(v.clics, 0) / n.envois, 1) AS taux_clic
FROM c
LEFT JOIN nb_envois n ON c.campagne_id = n.campagne_id
LEFT JOIN nb_evenements v ON c.campagne_id = v.campagne_id
LEFT JOIN nb_commandes o ON c.campagne_id = o.campagne_id
ORDER BY c.date_envoi, c.campagne_id
""")
display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Résultat à copier dans le Google Sheet (onglet __PAYS__)
# MAGIC Texte séparé par des tabulations : à coller en cellule A1, Google Sheets répartit les colonnes tout seul.

# COMMAND ----------

print(df.toPandas().to_csv(sep="\\t", index=False).strip() or "AUCUNE LIGNE")
'''


def build() -> Path:
    gen = (ROOT / "som" / "crm_data.py").read_text(encoding="utf-8")
    cat = f"{CATALOGUE}.{SCHEMA}"
    cells = [
        "# Databricks notebook source\n"
        "# MAGIC %md\n"
        "# MAGIC # Show me once — setup de la base CRM fictive\n"
        f"# MAGIC Crée `{cat}` : 5 tables reliées (clients, campagnes, envois, evenements, commandes)\n"
        "# MAGIC et les 10 notebooks `rapport_<PAYS>` dans ton dossier `show-me-once`. À lancer une seule fois (Run all).\n"
        "# MAGIC Données 100 % fictives, générées avec une graine fixe : identiques à la vérité terrain du repo.",
        f'CATALOGUE, SCHEMA = "{CATALOGUE}", "{SCHEMA}"',
        gen.strip(),
        # écriture des tables
        'tables = generate()\n'
        'spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGUE}.{SCHEMA}")\n'
        'for nom, lignes in tables.items():\n'
        '    df = spark.createDataFrame(lignes, schema=SCHEMAS[nom])\n'
        '    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOGUE}.{SCHEMA}.{nom}")\n'
        '    print(f"✅ {nom} : {df.count()} lignes")',
        # contraintes (bonus : schéma relationnel visible dans Catalog Explorer)
        '# Clés primaires / étrangères (contraintes informatives Unity Catalog). Facultatif : une erreur ici ne bloque rien.\n'
        'for nom, (pk, fks) in CLES.items():\n'
        '    t = f"{CATALOGUE}.{SCHEMA}.{nom}"\n'
        '    try:\n'
        '        spark.sql(f"ALTER TABLE {t} ALTER COLUMN {pk} SET NOT NULL")\n'
        '        spark.sql(f"ALTER TABLE {t} ADD CONSTRAINT pk_{nom} PRIMARY KEY ({pk})")\n'
        '    except Exception as e:\n'
        '        print(f"ℹ️ PK {nom} : {str(e)[:120]}")\n'
        'for nom, (pk, fks) in CLES.items():\n'
        '    for col, ref in fks:\n'
        '        try:\n'
        '            spark.sql(f"ALTER TABLE {CATALOGUE}.{SCHEMA}.{nom} ADD CONSTRAINT fk_{nom}_{col} "\n'
        '                      f"FOREIGN KEY ({col}) REFERENCES {CATALOGUE}.{SCHEMA}.{ref}")\n'
        '        except Exception as e:\n'
        '            print(f"ℹ️ FK {nom}.{col} : {str(e)[:120]}")\n'
        'print("✅ contraintes")',
        # notebooks par pays
        f'RAPPORT = {RAPPORT.replace("__CAT__", cat)!r}\n\n'
        'import base64\n'
        'from databricks.sdk import WorkspaceClient\n'
        'from databricks.sdk.service.workspace import ImportFormat, Language\n'
        'w = WorkspaceClient()\n'
        'dossier = f"/Users/{w.current_user.me().user_name}/show-me-once"\n'
        'w.workspace.mkdirs(dossier)\n'
        'for pays in PAYS:\n'
        '    src = RAPPORT.replace("__PAYS__", pays).replace("__SEMAINE__", SEMAINE)\n'
        '    w.workspace.import_(path=f"{dossier}/rapport_{pays}", format=ImportFormat.SOURCE, language=Language.PYTHON,\n'
        '                        content=base64.b64encode(src.encode()).decode(), overwrite=True)\n'
        '    print(f"📓 {dossier}/rapport_{pays}")',
        # contrôle
        'display(spark.sql(f"""\n'
        'SELECT c.pays, COUNT(DISTINCT c.campagne_id) AS campagnes, COUNT(e.envoi_id) AS envois\n'
        'FROM {CATALOGUE}.{SCHEMA}.campagnes c LEFT JOIN {CATALOGUE}.{SCHEMA}.envois e USING (campagne_id)\n'
        'GROUP BY c.pays ORDER BY c.pays"""))',
    ]
    out = ROOT / "databricks" / "01_setup_crm.py"
    out.parent.mkdir(exist_ok=True)
    out.write_text(CELL.join(cells) + "\n", encoding="utf-8")
    (ROOT / "databricks" / "rapport_TEMPLATE.py").write_text(RAPPORT.replace("__CAT__", cat), encoding="utf-8")
    build_sheet_script()
    return out


def build_sheet_script() -> Path:
    """sheets/dashboard.gs = modèle + données de la semaine précédente (état « avant » de la démo)."""
    import json
    from .crm_data import COLONNES_RAPPORT, PAYS, generate, previous
    t = generate()
    data = {p: [[r[c] for c in COLONNES_RAPPORT] for r in previous(t, p)] for p in PAYS}
    tpl = (ROOT / "sheets" / "dashboard.template.gs").read_text(encoding="utf-8")
    out = ROOT / "sheets" / "dashboard.gs"
    out.write_text(tpl.replace("/*__PRECEDENTE__*/{}", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
    return out
