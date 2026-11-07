# Sportiva — outils internes (démo)

Une seule app Python, sans dépendance : **Sportiva Admin** (`/admin`), **Parcelia Pro** (`/parcelia`), **Sportiva Care** (`/care`).
Marques et données 100 % fictives (marketplace de démonstration).

## Lancer en local
```bash
python server.py
```
→ http://localhost:8080

## Déployer sur Railway
1. New Project ▸ Deploy from GitHub repo (ou `railway up` depuis ce dossier).
2. Settings ▸ **Root Directory** = `app` (si le repo contient tout le projet).
3. Variables : `SECRET_KEY` = une chaîne aléatoire (signe les cookies de connexion).
4. Settings ▸ Networking ▸ **Generate Domain** → l'URL publique, à mettre dans `OUTILS_URL` du `.env` du projet.

Railway détecte Python grâce à `requirements.txt` et lance `python server.py` (Procfile). Le port vient de `$PORT`.

## Comptes de test
| Outil | Identifiant | Mot de passe |
|---|---|---|
| Sportiva Admin | `ops@sportiva.test` | `Sportiva-Ops-2026` |
| Parcelia Pro | `SPORTIVA-PRO` | `Parcelia-2026` |
| Sportiva Care | `agent@sportiva.test` | `Care-2026` |

Les données (`data.json`) sont régénérées par `python -m som outils` à la racine du projet.
