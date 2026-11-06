#!/usr/bin/env bash
# Installe l'Odoo de test du projet, identique chez chaque membre de l'équipe.
#   - base "hackathon", appli Facturation, plan comptable français (TVA 0 / 5,5 / 10 / 20 %)
#   - société fictive "Atelier Dorn SAS"
#   - compte admin renommé + mot de passe aléatoire, écrits dans prep/.env
# Prérequis : Docker Desktop lancé.
# Usage (depuis prep/odoo) : ./setup_odoo.sh
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="${ENV_FILE:-../.env}"
LOGIN="agent@atelier-dorn.test"

# 1. Fichiers de config privés (jamais sur GitHub)
[ -f "$ENV_FILE" ] || cp ../.env.example "$ENV_FILE"
if [ ! -f odoo.conf ]; then
  sed "s/^admin_passwd = .*/admin_passwd = $(openssl rand -hex 16)/" odoo.conf.example > odoo.conf
  chmod 600 odoo.conf
fi

# 2. Base de données + création de la base Odoo avec Facturation et compta française
echo "→ Démarrage de la base de données…"
docker compose up -d db
sleep 5
echo "→ Création de la base Odoo (2 à 5 min)…"
docker compose run --rm odoo odoo -c /etc/odoo/odoo.conf -d hackathon \
  -i account,l10n_fr_account --without-demo=all --load-language=fr_FR --stop-after-init >/dev/null 2>&1

# 3. Société, plan comptable français, compte admin
PASSWORD="$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | head -c 20)"
echo "→ Configuration de la société et du compte…"
docker compose run --rm -T odoo odoo shell -c /etc/odoo/odoo.conf -d hackathon --no-http >/dev/null 2>&1 <<EOF
c = env.company
c.write({'name': 'Atelier Dorn SAS', 'country_id': env.ref('base.fr').id,
         'street': '12 rue des Lilas', 'zip': '75011', 'city': 'Paris'})
if c.chart_template != 'fr':
    env['res.config.settings'].create({'chart_template': 'fr'}).execute()
env.ref('base.user_admin').write({'login': '$LOGIN', 'password': '$PASSWORD',
                                  'lang': 'fr_FR', 'tz': 'Europe/Paris'})
env.cr.commit()
EOF

# 4. Identifiants dans .env (remplace les lignes existantes)
perl -pi -e "s{^ODOO_LOGIN=.*}{ODOO_LOGIN=$LOGIN}; s{^ODOO_PASSWORD=.*}{ODOO_PASSWORD=$PASSWORD}" "$ENV_FILE"

# 5. Lancement
docker compose up -d db odoo
echo "✅ Odoo prêt : http://localhost:${ODOO_PORT:-8069}"
echo "   Identifiant et mot de passe : lignes ODOO_LOGIN / ODOO_PASSWORD de $ENV_FILE"
echo "   Adresse publique pour l'agent H : docker compose up -d tunnel"
echo "   puis : docker compose logs tunnel | grep trycloudflare  → à copier dans ODOO_URL"
