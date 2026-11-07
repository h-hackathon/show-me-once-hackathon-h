# Show me once — Hackathon H Company × 42AI (7–8 nov 2026)

> « Vos équipes n'ont pas besoin d'apprendre à automatiser. Elles font la tâche une fois, l'agent fait les 500 suivantes. »

## Thèse
Un agent computer-use ne sait pas comment *toi* tu fais ton travail (règles implicites, exceptions).
Résultat : il hésite, se trompe, consomme des étapes. La solution n'est pas un meilleur prompt :
c'est de **te regarder faire une fois**.

## Organisation du repo
Trois projets **indépendants** : chacun a son `pyproject.toml`, son `uv.lock`, son `.venv` et son `.env`
(modèle dans `.env.example`). On lance les commandes depuis le dossier du projet, et aucun projet n'importe le code d'un autre.

| Dossier | Quoi | Quand |
|---|---|---|
| [`prep/`](prep/) | Préparation : tests des API, factures de test, Odoo, docs sponsors, journal | avant le sam. 7 nov 10h30 |
| [`comptarex/`](comptarex/) | Comptarex, faux logiciel de cabinet comptable (web + desktop) : cible de la démo et du benchmark | hackathon |
| [`smo/`](smo/) | Le produit : le pipeline Show me once | hackathon |

Le code du produit (`smo/`, `comptarex/`) s'écrit pendant le hackathon : l'historique des commits le montre au jury.

## Le pipeline (`smo/`)
Un humain fait la tâche une fois en commentant à voix haute ; SMO en tire un agent custom H, avec sa Skill et un tool déterministe.
```
capture ─► transcribe ─► frames ─► understand ─► enrich ─► skill ─► review ─► replay ─► provision ─► compile ─► upgrade
```
- **Voix et images** : Gladia (transcription horodatée), ffmpeg (une image par phrase)
- **Compréhension** : Holo relie chaque phrase à l'écran → procédure et règles implicites
- **Vérification** : Linkup vérifie les règles dites par l'humain
- **Skill H** : écrite à partir de la procédure, relue et corrigée par l'humain
- **Replay** : l'agent H refait la tâche, guidé phrase par phrase ; sa trace nourrit la compilation
- **Compilation** : Devin écrit le tool déterministe (PR) ; l'agent H supervise, vérifie à l'écran et reprend en computer use si l'interface change

## Grille de jugement (référence : brief H pour Eugenia)
| Critère | Poids | Notre réponse |
|---|---|---|
| Usage du computer use | 25 % | Écran central à l'apprentissage ET à l'exécution |
| Fiabilité | 25 % | Benchmark : chaque tâche lancée plusieurs fois |
| Utilité | 20 % | DAF de PME, cabinets comptables |
| Originalité | 15 % | Apprentissage par démonstration |
| UX & contrôle | 10 % | Skill éditable, pause/stop, validation humaine |
| Démo & Q&A | 5 % | Pitch 4 min + vidéo de secours |

## Benchmark (le chiffre qui gagne)
Même lot de 10 factures, 2 conditions × 3 runs :
- **A** : agent seul, prompt classique
- **B** : agent + Skill apprise de la démo

Colonnes de log (format du brief H) : voir `prep/benchmark_log_template.csv`.
Slide cible : « A : x/10 → B : y/10, z× moins d'étapes ».

## Rôles (4 personnes)
1. **Capture** : enregistrement écran + Gladia
2. **Skill builder** : prompt Holo4, format Skill, UI d'édition
3. **Runner** : sessions parallèles, answer_schema, benchmark
4. **Front & pitch** : dashboard supervision (Devin pour coder), vidéo de secours, post LinkedIn

## Planning
- **Sam 10h30–13h** : chacun sa brique en isolé, interfaces fixées dès le départ
- **Sam 18h** : boucle complète sur 1 facture ✅
- **Sam soir** : parallélisation + benchmark A/B
- **Dim 8h–12h** : fiabilisation, gel des fonctionnalités, vidéo de secours
- **Dim 12h–14h** : README final, slides, répétition → **dépôt 14h00**

## Livrables
- Démo live (vidéo de secours si le site lâche), vrais résultats, pas de maquettes
- 1 slide « ce que l'agent a trouvé »
- Pitch 4 min : problème → qui paie → ce qu'on a construit
- Repo + README que quelqu'un d'autre peut suivre

## Prix visés
Podium · Best Use of Gladia (1 000 €) · Best Use of Devin (1 000 €) · Best LinkedIn Post (500 €)
