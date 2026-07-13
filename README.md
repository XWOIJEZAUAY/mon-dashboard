# ERP Dashboard — Tableau de Bord Intelligente de Gestion d'Entreprise

---

## Table des matieres

1. [Presentation du projet](#1-presentation-du-projet)
2. [Problematique et objectifs](#2-problematique-et-objectifs)
3. [Architecture generale](#3-architecture-generale)
4. [Modele de donnees](#4-modele-de-donnees)
5. [Outils et technologies](#5-outils-et-technologies)
6. [Methodologie de realisation](#6-methodologie-de-realisation)
7. [Fonctionnalites detaillees](#7-fonctionnalites-detaillees)
8. [Moteur de cross-filtering JS](#8-moteur-de-cross-filtering-js)
9. [Intelligence Artificielle — Agent conversationnel](#9-intelligence-artificielle--agent-conversationnel)
10. [Performance et optimisation](#10-performance-et-optimisation)
11. [Securite et authentification](#11-securite-et-authentification)
12. [Deploiement](#12-deploiement)
13. [Difficultes rencontrees et solutions](#13-difficultes-rencontrees-et-solutions)
14. [Resultats et metriques](#14-resultats-et-metriques)
15. [Perspectives d'amelioration](#15-perspectives-damelioration)

---

## 1. Presentation du projet

### Contexte

Ce projet est un **tableau de bord ERP (Enterprise Resource Planning)** concu pour gerer l'ensemble des operations d'une entreprise commerciale : ventes, achats, stock, tresorerie et relation client. Il se veut etre une **alternative open-source aux solutions ERP commerciales** (SAP, Odoo, ERPNext) en offrant une interface moderne, reactive et intelligente.

### Objectif principal

Fournir aux dirigeants et gestionnaires un **outil de pilotage en temps reel** capable de :

- Centraliser les KPIs de toutes les fonctions metier dans une seule interface
- Permettre une analyse interative via le **cross-filtering** (clic sur un graphique met a jour tous les autres)
- Integrer un **agent IA** capable de repondre a des questions sur les donnees de l'entreprise
- Assurer la **confidentialite** des donnees (hebergement local ou prive)

### Portee fonctionnelle

| Domaine | Description |
|---------|-------------|
| **Ventes** | Analyse du CA, marges, produits, regions, methodes de paiement |
| **Clients** | Fidelite, encaisse, delais de paiement, portefeuille |
| **Stock & Achats** | Rotation, alertes, seuils critiques, fournisseurs |
| **Trésorerie** | BFR, previsions, solde, creances, flux financiers |
| **Agent IA** | Chatbot conversationnel analysant les donnees en temps reel |

---

## 2. Problematique et objectifs

### Problematique identifiee

Les PME marocaines font face a plusieurs defis :

1. **Fragmentation des donnees** : les informations sont eparpillees entre Excel, fichiers papier, applications metier isolees
2. **Absence de vision globale** : pas de tableau de bord unifie pour piloter l'entreprise
3. **Temps de reporting** : la production de rapports manuelle prend des heures voire des jours
4. **Coût des solutions ERP** : les solutions commerciales couterent des milliers d'euros/an
5. **Manque d'intelligence predictive** : pas d'aide a la decision integree

### Objectifs SMART

| # | Objectif | Mesure |
|---|----------|--------|
| O1 | Centraliser 15 tables de donnees dans un dashboard unique | 15 feuilles Google Sheets connectees |
| O2 | Afficher 25+ KPIs metier en temps reel | 5 sections, 25+ KPIs calcules |
| O3 | Permettre le cross-filtering interactif sans rechargement | Moteur JS cote client |
| O4 | Integrer un agent IA pour l'analyse conversationnelle | 4 modeles LLM supportes |
| O5 | Atteindre un temps de chargement < 3s pour les navigations | Cache @st.cache_resource |
| O6 | Assurer la securite des donnees | Authentification + Google Sheets API |

---

## 3. Architecture generale

### Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                     NAVIGATEUR WEB                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Streamlit Frontend (Python)                         │  │
│  │  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌────────────┐ │  │
│  │  │ Ventes  │ │ Clients  │ │ Stock  │ │ Trésorerie │ │  │
│  │  └─────────┘ └──────────┘ └────────┘ └────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │  React Cross-Filter Engine (Plotly.js)          │ │  │
│  │  │  ventes-app/dist/index.html (bundle unique)     │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                  │
│                           ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Couche Metier (Python / Pandas)                     │  │
│  │  • build_sales_full() — 4 jointures LEFT JOIN        │  │
│  │  • build_purchases_full() — 3 jointures LEFT JOIN    │  │
│  │  • compute_cost_map() — cout unitaire pondere        │  │
│  │  • in_period() — filtrage temporel                    │  │
│  │  • @st.cache_resource — cache objet (pas de copie)   │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                  │
│                           ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Couche Donnees (gspread + Google Sheets API v4)     │  │
│  │  • 15 feuilles chargees en parallel                   │  │
│  │  • Authentification via service_account.json          │  │
│  │  • Sheet ID: 1kLvCbD-uNMD-ljwZOj8ZtcMu_-irjRp...   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Pattern architectural

Le projet suit un **pattern MVC (Model-View-Controller)** adapte :

- **Model** : Google Sheets (base de donnees) + pandas DataFrames
- **View** : Streamlit (sectionsClients, Stock, Tresorerie) + React (Ventes cross-filter)
- **Controller** : fonctions Python de calcul (KPIs, jointures, filtrage)

### Hybridation Python / React

Une architecture **hybride Streamlit + React** a ete developpee :

- **Streamlit** gere la navigation, les filtres lateraux, les KPIs, et les sections Clients/Stock/Tresorerie
- **React** (via Vite, compile en un seul fichier HTML) gere la section Ventes avec cross-filtering cote client
- Les donnees sont injectees de Python vers React via `st.components.v1.html()` avec un template JS genere dynamiquement

---

## 4. Modele de donnees

### Source unique de verite

Toutes les donnees proviennent d'un **Google Sheet unique** contenant 15 feuilles (onglets). Ce choix permet :

- Un acces partage en temps reel par plusieurs utilisateurs
- Une interface de saisie familiere (Excel-like)
- Pas de serveur de base de donnees a maintenir

### Schema relationnel

```
                    ┌──────────────┐
                    │  Categories  │
                    └──────┬───────┘
                           │ 1:N
┌──────────────┐    ┌──────┴───────┐    ┌──────────────┐
│   Clients    │    │   Products   │    │  Suppliers   │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       │ 1:N               │ 1:N               │ 1:N
       ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    Sales     │    │  SaleItems   │    │  Purchases   │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       │ 1:N               │                   │ 1:N
       ▼                   │                   ▼
┌──────────────┐           │            ┌──────────────┐
│   Payments   │           │            │ PurchaseItems│
└──────┬───────┘           │            └──────────────┘
       │                   │
       │ 1:N               │
       ▼                   ▼
┌──────────────┐    ┌──────────────┐
│PaymentAlloc. │    │   Refunds    │
└──────────────┘    └──────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    Devis     │    │  DevisItems  │    │StockMovements│
└──────────────┘    └──────────────┘    └──────────────┘

┌──────────────┐    ┌──────────────┐
│  CashLogs    │    │ RefundItems  │
└──────────────┘    └──────────────┘
```

### 15 feuilles Google Sheets

| Feuille | Description | Colonnes cles |
|---------|-------------|---------------|
| Products | Catalogue produits | id, name, price, stock, min_stock, category_id |
| Sales | En-tetes de ventes | id, client_id, total, status, created_at |
| SaleItems | Lignes de vente | id, sale_id, product_id, price, quantity, refund_quantity |
| Clients | Base clients | id, name, email, address |
| Categories | Categories produits | id, name |
| Purchases | En-tetes d'achats | id, supplier_id, total, status |
| PurchaseItems | Lignes d'achat | id, purchase_id, product_id, price, quantity |
| Suppliers | Fournisseurs | id, name, phone, address |
| Payments | Paiements recus | id, sale_id, amount, method, status |
| Refunds | Remboursements | id, sale_id, total, reason |
| Devis | Devis/quotes | id, client_id, total, status |
| DevisItems | Lignes de devis | id, devis_id, product_id, quantity, price |
| StockMovements | Mouvements de stock | id, product_id, quantity, type |
| PaymentAllocations | Affectations paiements | id, payment_id, amount_applied |
| CashLogs | Journal de caisse | id, payment_id, action, old_value, new_value |

### Vues jointes precalculees

Deux vues principales sont construites par jointures a chaque chargement :

**`sales_full`** (4 jointures LEFT JOIN) :
```
SaleItems → Sales → Products → Categories → Clients
```

**`purchases_full`** (3 jointures LEFT JOIN) :
```
PurchaseItems → Purchases → Suppliers → Products
```

---

## 5. Outils et technologies

### Stack technique complete

| Couche | Technologie | Version | Role |
|--------|-------------|---------|------|
| **Frontend principal** | Streamlit | >= 1.32 | Framework web Python, navigation, KPIs |
| **Cross-filter React** | React + Vite | 18.3 + 6.0 | Moteur de filtrage cote client |
| **Visualisation** | Plotly.js | >= 5.18 | 20+ types de graphiques interactifs |
| **Traitement donnees** | Pandas | >= 2.0 | DataFrames, jointures, aggregations |
| **Calcul numerique** | NumPy | >= 1.24 | Operations vectorisees, stat |
| **Base de donnees** | Google Sheets API v4 | - | Stockage cloud, acces REST |
| **Auth GSheets** | gspread + google-auth | >= 5.12 | Client Python pour Google Sheets |
| **Reseau** | Requests | >= 2.31 | Appels API (AI Agent) |
| **Build React** | Vite + vite-plugin-singlefile | - | Bundle React en un seul HTML |
| **Animation** | Framer Motion | 12.4 | Transitions UI dans React |
| **Icones** | Lucide React | 1.22 | Icones SVG dans React |

### Donnees geographiques

| Fichier | Contenu | Usage |
|---------|---------|-------|
| `maroc.geojson` | 12 regions du Maroc (geometries GeoJSON) | Carte choropleth |
| `villes.json` | 34 villes mappees aux 12 codes region | Geocodage des adresses clients |

### Justification des choix

| Choix | Alternatives envisagees | Raison du choix |
|-------|------------------------|-----------------|
| Streamlit vs Dash/Flask | Dash, Flask+Bootstrap, Gradio | Rapidite de developpement, widgets natifs, interop Python |
| Google Sheets vs PostgreSQL | PostgreSQL, MongoDB, SQLite | Pas de serveur a maintenir, acces multi-utilisateur, interface de saisie familiere |
| Plotly vs Matplotlib/Bokeh | Matplotlib, Bokeh, Altair | Interactivite native, choropleth, types varies |
| React vs Streamlit pur | Streamlit uniquement | Cross-filter JS impossible en Streamlit pur (chaque clic = rerun serveur) |

---

## 6. Methodologie de realisation

### Approche de developpement

Le projet a suivi une **methodologie Agile iterative** en 4 phases :

### Phase 1 : Fondations (Semaines 1-2)

| Action | Detail |
|--------|--------|
| Conception du modele de donnees | 15 tables, relationnel, normalise |
| Creation du Google Sheet | Schema, headers, donnees de test |
| Script de seed | `seed_full.py` — generation de 500+ clients, 1000+ ventes, donnees reelles |
| Premier dashboard Streamlit | `app.py` — structure de base, 1 section |

### Phase 2 : Sections metier (Semaines 3-5)

| Action | Detail |
|--------|--------|
| Section Ventes | 5 KPIs, 8 graphiques, carte Maroc |
| Section Clients | 5 KPIs, 8 graphiques |
| Section Stock & Achats | 6 KPIs, 8 graphiques |
| Section Tresorerie | 5 KPIs, 8 graphiques, previsions BFR |
| Jointures pandas | `build_sales_full()`, `build_purchases_full()` |

### Phase 3 : Interactivite avancee (Semaines 6-8)

| Action | Detail |
|--------|--------|
| Cross-filtering JS | Moteur `crossfilter.js` — 8 dimensions |
| Integration React | Bundle Vite injecte dans Streamlit via `components.v1.html()` |
| Geocodage | `villes.json` (34 villes) + `maroc.geojson` (12 regions) |
| Carte choropleth | Jointure adresse client → ville → region → GeoJSON |

### Phase 4 : Intelligence et optimisation (Semaines 9-10)

| Action | Detail |
|--------|--------|
| Agent IA | Chatbot OpenRouter (DeepSeek-R1, Llama 3.3, Mixtral, Qwen) |
| Authentification | Secrets Streamlit + service account Google |
| Performance | `@st.cache_resource`, elimination des `.copy()` |
| Deploiement | Docker, Streamlit Cloud, GitHub |

### Diagramme de Gantt simplifie

```
Semaine:  1  2  3  4  5  6  7  8  9  10
Phase 1:  ████████
Phase 2:            ███████████████
Phase 3:                        ███████████████
Phase 4:                                    ████████████
```

---

## 7. Fonctionnalites detaillees

### 7.1 Section Ventes (React + Cross-filter)

**5 KPIs** :
| KPI | Formule | Description |
|-----|---------|-------------|
| Revenu (CA) | `SUM(sale_total)` | Chiffre d'affaires total ( TTC) |
| Croissance | `(CA_cur - CA_prev) / CA_prev x 100` | Variation N vs N-1 |
| Quantites vendues | `SUM(quantity - refund_quantity)` | Unites nettes |
| Marge nette | `SUM((price - unit_cost) x qty_net)` | Marge brute par ligne |
| Taux de marge | `marge_nette / CA x 100` | Rentabilite % |

**8 graphiques** :
- G1 : Ventes par jour (scatter + aire)
- G2 : Ventes & Marge (barres + ligne axe secondaire)
- G3 : Carte du Maroc — CA par region (choropleth)
- G4 : Repartition par categorie (donut)
- G5 : Top 10 produits (barres horizontales)
- G6 : Top 10 jours (barres horizontales)
- G7 : Ventes par mois (heatmap)
- G8 : Methodes de paiement (donut)

### 7.2 Section Clients

**5 KPIs** :
| KPI | Formule |
|-----|---------|
| Total clients | `COUNT(id)` |
| Nouveaux clients | `COUNT(created_at)` dans la periode |
| Clients actifs | `NUNIQUE(client_id)` sur Sales |
| Delai moyen de paiement | `AVG(pay_date - sale_date)` |
| Panier moyen | `SUM(sale_total) / COUNT(DISTINCT sale_id)` |

**8 graphiques** :
- Evolution du portefeuille clients (barres + courbe cumul)
- Fidelite client (pie : fidele/occasionnel/inactif)
- Top 10 clients par CA
- Repartition geographique
- Encourse vs impaye (donut)
- Retours par client (treemap)
- Delai de paiement par client
- Frequence d'achat

### 7.3 Section Stock & Achats

**Systeme d'alertes a 5 niveaux** :
```
stock = 0           → "Rupture" (rouge)
0 < stock <= min    → "Critique" (orange)
min < stock <= sec  → "Securite" (jaune)
sec < stock <= alt  → "Alerte" (bleu clair)
stock > alert       → "OK" (vert)
```

**6 KPIs** :
| KPI | Formule |
|-----|---------|
| References | `COUNT(Products)` |
| Rotation stock | `COGS / Valeur_stock` |
| Stock securite | `COUNT(statut == 'Securite')` |
| Valeur stock | `SUM(stock x price)` |
| Achats periode | `SUM(PurchaseItems.total)` |
| Fournisseurs | `NUNIQUE(supplier_name)` |

**8 graphiques** : Mouvements stock, entrees/sorties par categorie, top 10 par valeur, valeur par categorie, rotation, retours, seuil critique, alertes.

### 7.4 Section Tresorerie

**Ratios financiers calcules** :
- **DSO** (Days Sales Outstanding) : delai moyen d'encaissement
- **DPO** (Days Payables Outstanding) : delai moyen de paiement fournisseurs
- **BFR** (Besoin en Fonds de Roulement) : `(DSO x CA_ann / 365) - (DPO x Achats_ann / 365)`

**5 KPIs** :
| KPI | Formule |
|-----|---------|
| Solde tresorerie | `Encaissements - Decaissements` (cumul) |
| Encaissements mois | `SUM(alloc_amount)` payments approuves |
| Decaissements mois | `SUM(purchase_total)` payes + `SUM(refund.total)` |
| BFR annuel | Formule DSO/DPO (voir ci-dessus) |
| Variation tresorerie | `(solde_cur - solde_prev) / ABS(solde_prev) x 100` |

**8 graphiques** : Evolution solde, enc vs dec, top fournisseurs, repartition flux, BFR mensuel, creances impayees, prevision regression lineaire, jauge.

### 7.5 Section Agent IA

- Chatbot conversationnel via `st.chat_input`
- 4 modeles LLM accessibles (DeepSeek-R1, Llama 3.3, Mixtral, Qwen 2.5)
- Contexte systeme : CSV complet des 15 tables
- Reponse structuree : resume, analyse detaillee, recommandations
- Interface HTML personnalisee (bulles, logo anime, indicateur de frappe)

---

## 8. Moteur de cross-filtering JS

### Principe

Le cross-filtering est le mecanisme central de l'interactivite. Cliquez sur une barre du graphique "Top 10 Produits" et **tous les autres graphiques se mettent a jour instantanement** — sans rechargement du serveur.

### Implementation

Le moteur est implemente en **JavaScript vanilla** (`crossfilter.js`) dans le bundle React :

```javascript
// 8 dimensions de filtrage supportees
export const FILTER_LABELS = {
  region: 'Region',
  mois: 'Mois',
  produit: 'Produit',
  categorie: 'Categorie',
  paiement: 'Paiement',
  date: 'Date',
  city: 'Ville',
  stock_produit: 'Produit (Stock)',
};
```

### Flux de donnees

```
Clic sur Graphique G3 (Carte region "Casablanca-Settat")
        │
        ▼
detectDim('chart-g3') → retourne 'region'
        │
        ▼
filterData(rawData, 'region', 'Casablanca-Settat')
        │
        ▼
Nouveau dataset filtre → tous les graphiques React re-render
        │
        ▼
KPIs recalcules → affichage maj
```

### Avantages vs cross-filter server-side

| Aspect | Cross-filter JS (notre approche) | Cross-filter Streamlit (classique) |
|--------|----------------------------------|-------------------------------------|
| Latence | **< 50ms** (cote client) | 2-10s (round-trip serveur) |
| Rechargement | Aucun | Re-execution du script Python |
| UX | fluide, responsive | saccadee, delai perceptible |
| Bande passante | Zero (donnees deja en memoire) | Re-transmission JSON |

---

## 9. Intelligence Artificielle — Agent conversationnel

### Architecture

```
Utilisateur
    │ st.chat_input("Posez votre question...")
    ▼
Prompt systeme = CSV complet des 15 tables
    │ + instruction d'analyse structurée
    ▼
API OpenRouter (mode gratuit)
    │ DeepSeek-R1 / Llama 3.3 / Mixtral / Qwen
    ▼
Reponse HTML personnalisee
    │ bulles de chat + logo anime
    ▼
Affichage dans Streamlit
```

### Modeles supportes

| Modele | Parametres | Force |
|--------|-----------|-------|
| DeepSeek-R1 | 671B (MoE) | Raisonnement, mathematiques |
| Llama 3.3 70B | 70B | Generaliste, instruction-following |
| Mixtral 8x7B | 46.7B (MoE) | Multilingue, rapidite |
| Qwen 2.5 Coder 32B | 32B | Code, analyse technique |

### Prompt d'analyse

Le systeme envoie les donnees brutes avec une instruction structuree :

```
Tu es un analyste financier expert. Analyse les donnees de l'entreprise
et fournis :
1. Un resume executif (3-5 lignes)
2. Une analyse detaillee par domaine
3. Des recommandations actionnables
4. Des alertes et signaux faibles
```

---

## 10. Performance et optimisation

### Probleme initial

Le changement de section prenait **30 a 60 secondes** a cause de la re-serialisation des DataFrames a chaque rerun.

### Solution : `@st.cache_resource`

| Avant (`@st.cache_data`) | Apres (`@st.cache_resource`) |
|---------------------------|-------------------------------|
| Serialise/deserialise les DataFrames a chaque rerun | Retourne le **meme objet** (pas de copie) |
| Hash du dictionnaire complet (16 DataFrames) | Hash par reference objet (instantane) |
| 30-60s entre sections | **< 1s** |

### 5 fonctions cachees

```python
@st.cache_resource
def load_all_sheets() -> Dict[str, pd.DataFrame]:     # 16 onglets
def build_sales_full(d) -> pd.DataFrame:               # 4 jointures
def build_purchases_full(d) -> pd.DataFrame:           # 3 jointures
def compute_cost_map(d) -> dict:                       # cout unitaire
def load_geo_data():                                   # GeoJSON + villes
```

### Optimisations supplementaires

| Technique | Impact |
|-----------|--------|
| `React.lazy()` + code splitting | Chargement differe des 20+ composants graphiques |
| `vite-plugin-singlefile` | Bundle React = 1 seul fichier HTML (pas de CDN) |
| Elimination des `.copy()` | Reference directe au cache (pas de copie memoire) |
| `compute_cost_map()` partage | Fonction unique au lieu de 2 calculs dupliques |
| `load_geo_data()` centralise | GeoJSON + villes charges 1 fois au lieu de 4 |

---

## 11. Securite et authentification

### Couches de securite

| Couche | Mecanisme |
|--------|-----------|
| **Acces Google Sheets** | Service account JSON (cle privee, pas de mot de passe) |
| **Authentification utilisateur** | `st.secrets` (cles hashees dans `.streamlit/secrets.toml`) |
| **Parametre URL** | `query_params` pour persister la session |
| **Donnees** | Aucune donnee stockee localement — tout est dans Google Sheets |
| **API IA** | Cle OpenRouter dans les secrets (jamais exposee dans le code) |

### Gestion des secrets

```python
# Acces aux secrets Streamlit
st.secrets["google"]["type"]
st.secrets["google"]["private_key"]
st.secrets["auth"]["username"]
```

Le fichier `service_account.json` n'est **jamais commite** dans Git (exclu via `.gitignore`).

---

## 12. Deploiement

### Environnements supportes

| Environnement | Commande | Port |
|---------------|----------|------|
| **Local** | `streamlit run app.py` | 8501 |
| **Docker** | `docker run -p 8501:8501 mon-dashboard` | 8501 |
| **Dev Container** | VS Code + Dev Container extension | 8501 |

### Structure Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py"]
```

### Dev Container

Le dossier `.devcontainer/` configure un environnement de developpement reproductible avec :

- Python 3.11
- Toutes les dependances pre-installees
- Port forwarding automatique (8501)
- Extensions VS Code recommandees

### Deploiement GitHub

```bash
git add app.py villes.json
git commit -m "perf: cache resource pour navigation instantanee"
git push origin master
```

---

## 13. Difficultes rencontrees et solutions

### Difficulte 1 : Carte du Maroc vide (toutes les regions grises)

**Probleme** : La carte choropleth affichait 12 regions vides, sans aucune couleur.

**Cause** : Les noms de regions dans le GeoJSON contenaient des accents (`Tanger-Tetouan-Al Hoceima`) tandis que le code de cross-filter utilisait des noms avec accents different (`Tanger-Tétouan-Al Hoceïma`). De plus, les adresses clients n'etaient pas normalisees.

**Solution** :
1. Ajout d'un extracteur de ville depuis l'adresse : `address.split(",").[-1].strip()`
2. Normalisation Unicode (suppression des accents) pour le matching
3. `villes.json` reduit de 393 a 34 villes majeures (une par region cible)
4. Noms de regions **sans accents** dans tout le pipeline

### Difficulte 2 : Lag de 60 secondes au changement de section

**Probleme** : Chaque clic sur un bouton de navigation declenchait un delai de 30-60 secondes.

**Cause** : `@st.cache_data` serialisait et deserialisait les 16 DataFrames a chaque rerun pour calculer le hash du cache.

**Solution** : Migration vers `@st.cache_resource` qui retourne le meme objet Python (pas de copie, pas de serialisation). Verification qu'aucune mutation in-place n'est effectuee sur les objets caches.

### Difficulte 3 : Cross-filter JS incompatible avec Streamlit

**Probleme** : Streamlit ne supporte pas le cross-filter cote client — chaque interaction declenche un rerun complet du script Python.

**Solution** : Integration d'un bundle React compile en un seul fichier HTML via `vite-plugin-singlefile`. Les donnees sont injectees via `window.__DATA__` et le moteur JS gere le filtrage entierement cote client.

### Difficulte 4 : Format d'adresses clients variable

**Probleme** : Les adressesetaient au format `"42, Rue Hassan Casablanca"` — le split par virgule ne fonctionnait pas pour extraire la ville.

**Solution** : Correction du script de seed (`seed_gs.py`) pour utiliser le format `"42 Rue Hassan, Casablanca"` — la ville est toujours apres la derniere virgule.

---

## 14. Resultats et metriques

### Metriques du dashboard

| Metrique | Valeur |
|----------|--------|
| Lignes de code Python (app.py) | ~5 000 |
| Composants React | 25+ |
| KPIs affiches | 25+ |
| Graphiques interactifs | 32 |
| Dimensions cross-filter | 8 |
| Tables de donnees | 15 |
| Regions couvertes | 12 |
| Villes geocodees | 34 |
| Modeles IA integres | 4 |
| Temps de navigation | < 1s |
| Temps de chargement initial | 3-5s |

### Performance comparative

| Scenario | Avant optimisation | Apres optimisation |
|----------|-------------------|-------------------|
| Changement de section | 30-60s | < 1s |
| Cross-filter (clic) | N/A (impossible) | < 50ms |
| Chargement initial | 15-20s | 3-5s |
| Calcul KPIs | 5-8s | < 200ms |

---

## 15. Perspectives damelioration

| # | Amelioration | Priorite | Effort |
|---|-------------|----------|--------|
| 1 | Migration vers PostgreSQL pour les grosses donnees | Haute | Moyen |
| 2 | Ajout de modeles IA locaux (Ollama, Lemonade) | Haute | Faible |
| 3 | Export PDF/Excel des rapports | Moyenne | Faible |
| 4 | Authentification OAuth2 (Google/GitHub) | Moyenne | Moyen |
| 5 | Notifications d'alertes (email, Telegram) | Moyenne | Faible |
| 6 | Multi-utilisateurs avec roles (admin, viewer) | Haute | Moyen |
| 7 | Mode hors-ligne (PWA) | Basse | Fort |
| 8 | Integration comptable (PCG marocain) | Haute | Fort |
| 9 | Tableaux de bord personnalises par role | Moyenne | Moyen |
| 10 | API REST externe pour tierces applications | Basse | Moyen |

---

## Annexes

### A. Installation et demarrage

```bash
# Cloner le depot
git clone https://github.com/XWOIJEZAUAY/mon-dashboard.git
cd mon-dashboard

# Installer les dependances
pip install -r requirements.txt

# Lancer le dashboard
streamlit run app.py
```

### B. Fichiers cles

| Fichier | Role | Lignes |
|---------|------|--------|
| `app.py` | Dashboard principal | ~5 000 |
| `villes.json` | Mapping villes → regions | 34 entrees |
| `maroc.geojson` | Geometries des 12 regions | GeoJSON |
| `seed_full.py` | Generation de donnees de test | Script |
| `seed_gs.py` | Seed dans Google Sheets | Script |
| `requirements.txt` | Dependances Python | 7 packages |
| `ventes-app/` | Application React (cross-filter) | 25+ composants |
| `.streamlit/` | Configuration Streamlit | Config |
| `.devcontainer/` | Environnement de dev | Docker |

### C. Git — Historique des commits

```
627a8d8 perf: cache resource pour navigation instantanee
8ad9cfa fix: auth persist, formatting < 1K, revenue consistency
4ee02a3 Add 'pending' to valid purchase statuses
540e1ba Remove ttl from load_all_sheets cache
69f5b2c Fix reset_index compat pandas 1.x
62bff8c reduce chart heights for compact Power BI style
7060bff Reduce KPI card height
e827c6b Fix CA calculation, DPO merge bug, BFR supplier payments
eac685d Fix auth: use flat secrets keys
7b1cc3e Add private authentication
c849dd3 Safety check for missing React dist
20365d3 Add React dist, fix .gitignore
bb67c0c Added Dev Container Folder
a6c3562 Initial commit - ERP Dashboard Streamlit
```

---

**Projet realise par l'equipe** — Dashboard ERP intelligent avec cross-filtering et IA
**Stack** : Python (Streamlit) + React (Vite) + Plotly.js + Google Sheets + OpenRouter AI
**Licence** : Projet academique
