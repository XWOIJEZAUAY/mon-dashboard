# Questions Probables de Soutenance — ERP Dashboard

---

## CATEGORIE 1 : ARCHITECTURE & CHOIX TECHNIQUES

### Q1 : Pourquoi avoir choisi Streamlit plutot qu'un framework comme Django, Flask ou React complet ?

**Reponse attendue :**
- Streamlit permet de construire un dashboard interactif en **10x moins de code** qu'un framework classique
- Le language Python est le standard du data engineering/pandas — pas besoin de changer de langage
- Les widgets natifs (selectbox, date_input, sidebar) accelerent le developpement
- La limitation : Streamlit re.Execute le script a chaque interaction. D'ou l'integration React pour le cross-filter
- **Compromis** : hybridation Python/React pour combiner la simplicite de Streamlit avec la performance du JS

### Q2 : Expliquez l'architecture hybride Streamlit + React. Pourquoi ne pas avoir tout fait en React ?

**Reponse attendue :**
- Streamlit gere la **navigation**, les **filtres lateraux**, les **KPIs** et 3 sections (Clients, Stock, Tresorerie)
- React gere uniquement la section **Ventes** qui necessite du cross-filter cote client
- React est compile en **un seul fichier HTML** via `vite-plugin-singlefile` — pas de CDN, pas de serveur Node.js
- Les donnees sont injectees de Python vers React via `window.__DATA__` dans le template HTML
- Faire tout en React signifierait de reimplementer les filtres Streamlit, l'auth, la navigation — 3x plus de travail

### Q3 : Pourquoi Google Sheets comme base de donnees et pas PostgreSQL ou MongoDB ?

**Reponse attendue :**
- **Accessibilite** : les utilisateurs cibles (PME) connaissent deja Excel/Sheets
- **Pas de serveur** : pas de maintenance de base de donnees, pas de backup
- **Collaboration** : plusieurs utilisateurs peuvent saisir des donnees en meme temps
- **API REST** : Google Sheets API v4 permet un acces programmatique via gspread
- **Limite** : pas performant au-dela de 100k lignes. Pour une production, on migrerait vers PostgreSQL
- **Choix justifie** : c'est un prototype/dashboard — la simplicite prime sur la scalabilite dans cette phase

### Q4 : Comment le moteur de cross-filtering JS fonctionne-t-il techniquement ?

**Reponse attendue :**
1. Les donnees (JSON) sont injectees dans `window.__DATA__` au chargement
2. A chaque clic sur un graphique, l'evenement Plotly `plotly_click` est intercepte
3. `detectDim(chartId)` identifie la dimension (region, produit, categorie...)
4. `filterData(rawData, dim, val)` filtre le tableau JS avec un simple `.filter()`
5. Tous les graphiques React re-render avec le nouveau dataset
6. Les KPIs sont recalcules dans le meme thread JS
7. **Zero round-trip serveur** — tout se passe dans le navigateur

---

## CATEGORIE 2 : MODELE DE DONNEES & SQL

### Q5 : Expliquez le calcul du cout unitaire d'un produit. Pourquoi c'est complexe ?

**Reponse attendue :**
- `unit_cost = SUM(PurchaseItems.price x PurchaseItems.quantity) / SUM(PurchaseItems.quantity)`
- C'est un **cout moyen pondere** (weighted average cost)
- On ne prend que les achats avec statuts valides : pending, confirmed, received, completed, paid, paye, recu
- **Pourquoi pas le dernier prix d'achat ?** Car les prix varient fournisseur par fournisseur — le WAC lisse les variations
- **Cas limite** : si aucun achat n'existe pour un produit, `unit_cost = 0` et la marge est declaree a 100%

### Q6 : Comment calculez-vous le BFR (Besoin en Fonds de Roulement) ?

**Reponse attendue :**
```
BFR = (DSO x CA_annuel / 365) - (DPO x Achats_annuels / 365)
```
- **DSO** (Days Sales Outstanding) : delai moyen entre la facture et l'encaissement = `AVG(pay_date - sale_date)`
- **DPO** (Days Payables Outstanding) : delai moyen entre la reception et le paiement fournisseur
- **Interpretation** :
  - BFR > 0 : l'entreprise a besoin de financer le decalage (elle paie avant d'etre payee)
  - BFR < 0 : l'entreprise finance son activite grace aux delais fournisseurs
- **Source** : jointure Sales → PaymentAllocations → Payments pour le DSO

### Q7 : Pourquoi le statut "pending" a-t-il ete ajoute aux statuts d'achat valides ?

**Reponse attendue :**
- Initialement, seuls `confirmed, received, completed, paid, paye, recu` etaient considers
- **Probleme** : les achats en attente de livraison (`pending`) etaient exclus du calcul du cout
- Si un produit n'a que des achats `pending`, le `unit_cost = 0` — ce qui fausse la marge
- **Solution** : ajouter `pending` aux statuts valides pour inclure les achats commandes mais pas encore recus
- **Compromis** : le prix est connu (commande payee ou non) meme si la marchandise n'est pas encore arrivee

### Q8 : Comment normalisez-vous les adresses clients pour la geolocalisation ?

**Reponse attendue :**
1. Extraction de la ville : `address.split(",").str[-1].str.strip()` — la ville est toujours en dernier
2. Normalisation Unicode : suppression des accents avec `str.normalize("NFKD").str.encode("ascii", "ignore")`
3. Minuscules : `str.lower()` pour le matching insensible a la casse
4. Lookup dans `villes.json` : 34 villes mappees aux 12 codes de regions
5. Jointure avec `maroc.geojson` pour les geometries GeoJSON
6. **Difficulte** : les adresses originales etaient au format `"42, Rue Hassan Casablanca"` — le split ne marchait pas. Correction du seed en `"42 Rue Hassan, Casablanca"`

---

## CATEGORIE 3 : PERFORMANCE & OPTIMISATION

### Q9 : Expliquez la difference entre `@st.cache_data` et `@st.cache_resource`. Pourquoi le changement ?

**Reponse attendue :**
- **`@st.cache_data`** : serialise le retour en pickle, le deserialise a chaque appel, calcule le hash des arguments
  - Pour un DataFrame de 50k lignes : ~2-3 secondes de serialisation a chaque rerun
  - Pour 16 DataFrames dans un dict : ~30-60 secondes de hash total
- **`@st.cache_resource`** : retourne le **meme objet Python** — zero copie, zero serialisation
  - Le hash est base sur l'identite de l'objet (pointeur memoire) — instantane
  - **Risque** : si le code modifie l'objet en place, le cache est corrompu
  - **Verification** : aucune mutation in-place dans le code (filtrage = nouvelle copie, jamais `.loc[...] = ...`)
- **Resultat** : navigation de 60s → < 1s

### Q10 : Comment le code se comporte-t-il avec de grosses donnees (100k+ lignes) ?

**Reponse attendue :**
- Le cross-filter React charge **toutes les donnees en memoire** du navigateur (via `window.__DATA__`)
- Pour 100k lignes x 20 colonnes = ~20 Mo de JSON — acceptable pour un navigateur moderne
- Les `React.lazy()` et code splitting evitent de charger tous les composants d'un coup
- **Limite reelle** : Google Sheets API (quota de 300 requetes/minute, limite de 10M cellules)
- **Solution de scale** : migration vers PostgreSQL + pagination des requetes

### Q11 : Pourquoi le bundle React est compile en un seul fichier HTML ?

**Reponse attendue :**
- `vite-plugin-singlefile` inline tous les JS, CSS, et assets dans un seul fichier HTML
- **Avantage** : Streamlit peut injecter ce fichier via `st.components.v1.html()` sans avoir besoin d'un serveur CDN
- **Pas de dependance externe** : le dashboard fonctionne meme hors-ligne (apres le premier chargement)
- **Taille** : ~500 Ko gzipped — acceptable
- **Alternatives** : CDN (dependance internet), serveur Node.js (surcoût de maintenance)

---

## CATEGORIE 4 : INTELLIGENCE ARTIFICIELLE

### Q12 : Comment l'agent IA utilise-t-il les donnees de l'entreprise ?

**Reponse attendue :**
1. A chaque question, les 15 tables sont converties en CSV (`df.to_csv()`)
2. Le CSV est injecte dans le **prompt systeme** de l'API OpenRouter
3. Le modele LLM recoit : "Tu es un analyste financier expert. Voici les donnees..."
4. La reponse est structuree : resume executif, analyse detaillee, recommandations
5. **Limite** : si les donnees sont trop volumineuses (> 100k lignes), le contexte depasse la fenetre du modele
- **Solution** : envoyer uniquement les aggregates pertinents (pas les donnees brutes)

### Q13 : Pourquoi 4 modeles LLM differents ? Quels sont les cas d'usage ?

**Reponse attendue :**
| Modele | Force | Cas d'usage |
|--------|-------|-------------|
| DeepSeek-R1 | Raisonnement mathematique | Calculs financiers, previsions |
| Llama 3.3 70B | Generaliste | Analyse narrative, recommandations |
| Mixtral 8x7B | Multilingue, rapide | Questions simples, traduction |
| Qwen 2.5 Coder | Code, technique | Audit de donnees, detection d'anomalies |

- L'utilisateur choisit le modele selon sa question
- **OpenRouter** permet d'acceder a tous les modeles via une seule API
- **Mode gratuit** : les 4 modeles ont un tier gratuit avec rate limiting

### Q14 : L'agent IA peut-il prendre des actions automatiques (pas seulement repondre) ?

**Reponse attendue :**
- Actuellement **non** — l'agent est **analytique** (lecture seule)
- Il analyse les donnees et fournit des recommandations, mais ne modifie rien
- **Perspectives** : integration avec l'API Google Sheets pour :
  - Creer automatiquement des commandes fournisseur quand le stock est critique
  - Envoyer des alertes email aux clients en retard de paiement
  - Generer des devis pre-remplis
- **Risque** : un agent IA autonome qui modifie des donnees financieres necessite une validation humaine

---

## CATEGORIE 5 : SECURITE & DEPLOIEMENT

### Q15 : Comment securisez-vous les donnees sensibles de l'entreprise ?

**Reponse attendue :**
| Couche | Mecanisme |
|--------|-----------|
| Acces Google Sheets | Service account JSON (cle SSH, pas de mot de passe) |
| Auth utilisateur | `st.secrets` (hashe, pas en dur dans le code) |
| Secrets API | Cle OpenRouter dans `.streamlit/secrets.toml` |
| Git | `service_account.json` dans `.gitignore` — jamais commite |
| Transport | HTTPS (Google Sheets API oblige) |
| Stockage | Aucune donnee locale — tout est dans Google Sheets |

### Q16 : Le dashboard peut-il etre deploie en production pour une vraie entreprise ?

**Reponse attendue :**
- **Oui, avec des conditions** :
  - Migration vers PostgreSQL pour la performance (> 100k lignes)
  - Auth OAuth2 (Google/GitHub) au lieu de auth par mot de passe
  - Multi-utilisateurs avec roles (admin, viewer, editor)
  - Backup automatique de la base de donnees
  - Monitoring et alertes
  - HTTPS (reverse proxy nginx/caddy)
- **Non, dans l'etat actuel** :
  - Google Sheets a des quotas (300 req/min, 10M cellules)
  - Pas de journalisation des actions (audit trail)
  - Pas de gestion des concurrences (deux utilisateurs modifiant la meme donnee)

### Q17 : Comment geriez-vous la montee en charge (10x utilisateurs, 10x donnees) ?

**Reponse attendue :**
| Probleme | Solution |
|----------|----------|
| Google Sheets lent | Migration PostgreSQL + connection pooling |
| 100k+ lignes | Pagination, lazy loading, aggregation cote serveur |
| 10+ utilisateurs simultanes | Queue Redis + workers Celery |
| Temps de reponse | Cache Redis pour les KPIs, CDN pour les assets |
| Cross-filter | WebSocket au lieu de polling |

---

## CATEGORIE 6 : METHODOLOGIE & GESTION DE PROJET

### Q18 : Quelle methodologie avez-vous utilisee et pourquoi ?

**Reponse attendue :**
- **Agile iterative** en 4 phases de 2-3 semaines
- Chaque phase produit un livrable fonctionnel :
  - Phase 1 : Dashboard basique avec 1 section
  - Phase 2 : 4 sections completes
  - Phase 3 : Cross-filter React
  - Phase 4 : Agent IA + optimisations
- **Pourquoi Agile** : les exigences evoluaient (ajout de sections, changement de design)
- **Outils** : Git pour le versionnage, GitHub pour la collaboration
- **14 commits** sur la duree du projet — chaque commit correspond a une fonctionnalite ou un fix

### Q19 : Avez-vous fait du testing ? Comment validez-vous la qualite ?

**Reponse attendue :**
- **Tests manuels** : verification de chaque KPI avec des donnees de test connues
- **Scripts de verification** : `verify_sheet.py` et `verify_sheet2.py` valident la coherence des donnees
- **py_compile** : verification syntaxique a chaque commit
- **Tests visuels** : comparaison des graphiques avec les valeurs attendues
- **Limite** : pas de tests unitaires automatises (pytest)
- **Amelioration future** : ajouter des tests unitaires pour les fonctions de calcul (KPIs, BFR, marge)

### Q20 : Qu'avez-vous appris de ce projet ?

**Reponse attendue (personnaliser) :**
- **Technique** : architecture hybride Python/React, optimisation de cache, geocodage
- **Metier** : KPIs financiers (BFR, DSO, DPO), gestion de stock (rotation, seuils)
- **Gestion** : importance du modele de donnees avant le code
- **IA** : prompt engineering pour l'analyse de donnees
- **Communication** : documenter pour des experts (ce README)

---

## CATEGORIE 7 : QUESTIONS PIEGES

### Q21 : Quelle est la principale faiblesse de votre projet ?

**Reponse attendue (ne pas eviter) :**
- La **dependance a Google Sheets** comme base de donnees — c'est un point de faille pour la production
- Les quotas API (300 req/min) limiteront la montee en charge
- Pas de tests unitaires automatises
- L'agent IA envoie les donnees brutes au LLM — risque de depassement de contexte pour de gros volumes

### Q22 : Si vous deviez recommencer, qu'est-ce que vous changeriez ?

**Reponse attendue :**
- **Base de donnees** : PostgreSQL des le depart (pas de quota, SQL natif, meilleur performance)
- **Frontend** : React complet (pas de Streamlit) pour un meilleur controle UI
- **Tests** : pytest des le premier jour
- **CI/CD** : pipeline GitHub Actions pour les tests et le deploiement automatique

### Q23 : Comment votre projet se compare-t-il a Odoo ou ERPNext ?

**Reponse attendue :**
| Critere | Notre projet | Odoo/ERPNext |
|---------|-------------|--------------|
| Cout | Gratuit | Gratuit (community) / Payant (enterprise) |
| Complexeite | Faible (1 fichier Python) | Forte (100k+ lignes, PostgreSQL) |
| Fonctionnalites | 5 sections, 25 KPIs | 30+ modules, 1000+ fonctions |
| Personnalisation | Totale (open source) | Modules, themes |
| IA integree | Oui (4 modeles LLM) | Non (modules tierces) |
| Cross-filter | Oui (React) | Non |
| Courbe d'apprentissage | 0 (tout est la) | Forte |
| Production | Prototype | Enterprise-ready |

- **Notre force** : simplicite, IA integree, cross-filter, cout zero
- **Notre faiblesse** : pas de gestion des droits, pas d'audit trail, pas de multi-societe

### Q24 : Les donnees de test sont-elles reelles ? Comment les avez-vous generees ?

**Reponse attendue :**
- Les donnees sont **simulees** (script `seed_full.py`)
- 500+ clients, 1000+ ventes, 100+ produits, 50+ fournisseurs
- **Noms reels** : villes marocaines, categories de produits realistes
- **Montants reels** : fourchettes de prix cohérentes (10-5000 MAD)
- **Dates reelles** : reparties sur 2 ans pour tester les comparaisons N/N-1
- **Adresses reelles** : rues de Casablanca, Rabat, Marrakech, etc.
- **Pourquoi simulees** : les donnees d'une vraie entreprise sont confidentielles

### Q25 : Comment garantissez-vous l'integrite des donnees ?

**Reponse attendue :**
- **Google Sheets** : pas de contraintes de schema (risque de donnees incoherentes)
- **Pandas** : `_coerce()` convertit les types (dates, nombres) et remplace les erreurs par NaN
- **Validation** : `verify_sheet.py` verifie la coherence post-ecriture
- **KPIs** : les calculs utilisent `fillna(0)` et `errors="coerce"` pour eviter les plantages
- **Limite** : pas de validation cote base (pas de CHECK constraints, pas de FOREIGN KEYS)
- **Amelioration** : migration vers PostgreSQL avec schema contraint

---

## CATEGORIE 8 : QUESTIONS SPECIFIQUES PAR SECTION

### Q26 : (Ventes) Comment la carte choropleth Maroc fonctionne-t-elle ?

**Reponse attendue :**
1. `maroc.geojson` contient les 12 regions avec leurs geometries
2. `villes.json` mappe 34 villes aux codes de regions (1-12)
3. Pour chaque vente, on extrait la ville de l'adresse client
4. Normalisation Unicode + lookup dans villes.json → code region
5. Plotly `go.Choropleth` avec `locations=region_codes` et `geojson=maroc_geojson`
6. Gradient de couleur = CA par region

### Q27 : (Tresorerie) Comment la prevision de tresorerie par regression lineaire fonctionne-t-elle ?

**Reponse attendue :**
```
solde(t) = slope * t + intercept
projection(6 mois) = solde_actuel + slope * 6
```
- `np.polyfit(mois, soldes, 1)` calcule la pente et l'intercept
- La droite de regression montre la **tendance** historique
- **Limite** : regression lineaire = hypothese de linearite (pas de saisonnalite)
- **Amelioration** : ARIMA ou Prophet pour capturer la saisonnalite

### Q28 : (Stock) Comment detectez-vous les produits en rupture de stock ?

**Reponse attendue :**
```python
np.select([
    (stock == 0)                        → "Rupture",
    (0 < stock <= min_stock)            → "Critique",
    (min_stock < stock <= security_stock) → "Securite",
    (security_stock < stock <= alert_stock) → "Alerte",
    (stock > alert_stock)               → "OK"
], default="Non defini")
```
- Les seuils (`min_stock`, `security_stock`, `alert_stock`) sont definis **par produit** dans la table Products
- Le graphique "Alertes Reapprovisionnement" liste tous les produits non-OK
- **Action** : en production, cela declencherait des commandes automatiques

---

## CONSEILS POUR LA SOUTENANCE

### Structure de la presentation (15-20 min)

1. **Introduction** (2 min) — Contexte et problematique
2. **Architecture** (3 min) — Diagramme, choix techniques
3. **Demo live** (5 min) — Naviguer dans les 5 sections, montrer le cross-filter
4. **Aspect technique** (3 min) — Cross-filter JS, cache_resource, jointures
5. **IA** (2 min) — Agent conversationnel en direct
6. **Conclusion** (2 min) — Resultats, perspectives

### Regles d'or

- **Ne pas improviser** — les experts detectent immediatement les reponses floues
- **Admettre les faiblesses** — montrer la maturite technique
- **Citer des chiffres** — "50k lignes en < 1s", "32 graphiques", "14 commits"
- **Montrer le code** — pointer les fichiers cles (crossfilter.js, cache_resource)
- **Faire une demo** — rien de plus convaincant qu'un dashboard qui fonctionne en direct
