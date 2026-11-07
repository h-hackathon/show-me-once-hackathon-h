# Databricks notebook source
# MAGIC %md
# MAGIC # Rapport hebdo des campagnes email — __PAYS__
# MAGIC Une ligne par campagne envoyée pendant la semaine. Sources : `workspace.decathlon_crm.campagnes`, `envois`, `evenements`, `commandes`.

# COMMAND ----------

PAYS = "__PAYS__"
SEMAINE = "__SEMAINE__"  # lundi de la semaine du rapport

# COMMAND ----------

df = spark.sql(f"""
WITH c AS (
  SELECT campagne_id, nom, date_envoi FROM workspace.decathlon_crm.campagnes
  WHERE pays = '{PAYS}' AND date_envoi >= DATE'{SEMAINE}' AND date_envoi < DATE_ADD(DATE'{SEMAINE}', 7)
),
e AS (SELECT envoi_id, campagne_id FROM workspace.decathlon_crm.envois WHERE campagne_id IN (SELECT campagne_id FROM c)),
nb_envois AS (SELECT campagne_id, COUNT(*) AS envois FROM e GROUP BY campagne_id),
nb_evenements AS (
  SELECT e.campagne_id,
         SUM(CASE WHEN ev.type = 'ouverture' THEN 1 ELSE 0 END) AS ouvertures,
         SUM(CASE WHEN ev.type = 'clic' THEN 1 ELSE 0 END) AS clics,
         SUM(CASE WHEN ev.type = 'desabonnement' THEN 1 ELSE 0 END) AS desabonnements
  FROM workspace.decathlon_crm.evenements ev JOIN e ON ev.envoi_id = e.envoi_id
  GROUP BY e.campagne_id
),
nb_commandes AS (
  SELECT campagne_id, COUNT(*) AS commandes, ROUND(SUM(montant_eur), 2) AS ca_eur
  FROM workspace.decathlon_crm.commandes WHERE campagne_id IN (SELECT campagne_id FROM c) GROUP BY campagne_id
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

print(df.toPandas().to_csv(sep="\t", index=False).strip() or "AUCUNE LIGNE")
