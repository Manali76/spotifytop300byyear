# 🎶 GPT “Top Spotify par Année” — API FastAPI (Top 300 “max coverage”)

Ce projet permet de déployer une **API FastAPI** qui fournit le **Top 300 des chansons Spotify** pour une année donnée, basé sur la **popularité globale (`track.popularity`)**.  
L’API exploite au maximum la Search API de Spotify (~1000 titres par année, limite technique), filtre les doublons, trie et met en cache.

---

## 🚀 Fonctionnalités

- Récupère jusqu’à **1000 titres max** par année (limite de l’API Spotify).  
- Trie par **popularité globale** puis par titre (déterministe).  
- Supprime les doublons (ID + combinaison titre/artistes).  
- Retourne un **Top N** (par défaut 300, configurable jusqu’à 500).  
- Mise en cache (1h par défaut) pour rapidité et éviter les rate limits.  
- Gestion des erreurs Spotify (401, 429, etc.).  
- **Authentification simple par clé API** (`X-Api-Key`).  

---

## 📦 Fichiers inclus

- `app.py` → serveur FastAPI (logique complète).  
- `requirements.txt` → dépendances Python.  
- `Dockerfile` → conteneurisation.  
- `render.yaml` → déploiement Render (Blueprint).  
- `.github/workflows/docker.yml` → CI GitHub Actions (build + push sur GHCR).  
- `README.md` → ce guide.  

---

## 🛠️ Étape 1 — Créer ton app Spotify

1. Va sur [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).  
2. Clique **Create an app**.  
   - Donne un nom et une description (peu importe).  
   - Ajoute une Redirect URI factice (ex. `http://localhost:8888/callback`).  
3. Récupère :  
   - **Client ID**  
   - **Client Secret**  
4. ⚠️ **Ne partage jamais ces infos publiquement** (comme un mot de passe).  

---

## 🖥️ Étape 2 — Déploiement Render (méthode recommandée)

### Option A — Blueprint (`render.yaml`)
1. Pousse ce projet sur un repo GitHub.  
2. Sur Render → **New → Blueprint**.  
3. Choisis ton repo → Render détecte `render.yaml`.  
4. Renseigne les variables d’environnement :  
   - `SPOTIFY_CLIENT_ID`  
   - `SPOTIFY_CLIENT_SECRET`  
   - `ACTION_API_KEY` (clé secrète que tu inventes, ex. `ma-super-cle-123`)  
   - (optionnels) `DEFAULT_LIMIT`, `MAX_LIMIT`, `CACHE_TTL_SECONDS`  
5. Déploie → Render fournit une URL, ex.  
   ```
   https://top-spotify.onrender.com
   ```
6. Vérifie :  
   - `GET /health` → `{"ok":true}`  
   - `GET /top?year=2010&limit=300` avec header `X-Api-Key: ma-super-cle-123`.  

### Option B — Bouton “Deploy to Render”
Dans ton `README`, clique :  

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/OWNER/REPO)

⚠️ Remplace `OWNER/REPO` par ton dépôt GitHub public.

---

## 🐳 Étape 3 — Lancer en local avec Docker

```bash
# Build
docker build -t top-spotify-year .

# Run avec variables d’environnement
docker run -p 8000:8000   -e SPOTIFY_CLIENT_ID=xxx   -e SPOTIFY_CLIENT_SECRET=yyy   -e ACTION_API_KEY=ma-super-cle-123   top-spotify-year

# Test
curl -H "X-Api-Key: ma-super-cle-123" "http://localhost:8000/top?year=2010&limit=300"
```

---

## 🤖 Étape 4 — Intégration avec Custom GPT (Actions)

1. Dans ChatGPT → **Create a GPT** → *Configure* → **Actions** → *Import from schema*.  
2. Colle le schéma OpenAPI suivant (⚠️ adapte l’URL de ton Render) :

```yaml
openapi: 3.1.0
info:
  title: Top Spotify by Year (Max Coverage)
  version: "1.0.0"
servers:
  - url: https://top-spotify.onrender.com
paths:
  /top:
    get:
      operationId: getTop
      summary: Top Spotify par année (popularité globale) avec balayage maximal (~1000 pistes)
      security:
        - apiKeyAuth: []
      parameters:
        - in: query
          name: year
          required: true
          schema: { type: integer, minimum: 1900, maximum: 2100 }
        - in: query
          name: limit
          required: false
          schema: { type: integer, minimum: 1, maximum: 500, default: 300 }
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  year: { type: integer }
                  limit: { type: integer }
                  scanned_candidates: { type: integer }
                  results:
                    type: array
                    items:
                      type: object
                      properties:
                        rank: { type: integer }
                        title: { type: string }
                        artists: { type: array, items: { type: string } }
                        popularity: { type: integer }
                        album: { type: string }
                        release_date: { type: string }
                        spotify_url: { type: string }
components:
  securitySchemes:
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-Api-Key
```

3. Dans **Authentication** :  
   - Type : API Key  
   - Header : `X-Api-Key`  
   - Valeur : `ACTION_API_KEY` (exactement la même que sur Render)  

---

## ⚙️ Étape 5 — CI/CD GitHub Actions

Le fichier `.github/workflows/docker.yml` :  
- **Build** l’image Docker à chaque push/PR.  
- **Push** vers GitHub Container Registry (GHCR) lors des pushs sur `main`.  

Badge CI à ajouter en haut du README (remplace `OWNER/REPO`) :  

```markdown
[![CI](https://github.com/OWNER/REPO/actions/workflows/docker.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/docker.yml)
```

---

## 🛠️ Dépannage

- **401 Unauthorized** → mauvaise `X-Api-Key` (doit correspondre à `ACTION_API_KEY`).  
- **500 Server Error** → clés Spotify manquantes ou invalides.  
- **429 Too Many Requests** → rate limit Spotify ; le serveur attend `Retry-After` et retente.  
- **Moins de 300 résultats** → normal si année ancienne ou beaucoup de doublons ; l’API renvoie le max unique dispo.  
- **Lenteur au premier appel** → normal (scan complet ~1000 pistes). Les appels suivants sont instantanés (cache 1h).  

---

## ✅ Résumé rapide

1. Crée une app Spotify → récupère Client ID & Secret.  
2. Déploie avec Render (`render.yaml` ou bouton Deploy).  
3. Ajoute tes clés comme variables d’environnement.  
4. Teste `/top` avec clé API.  
5. Branche à ton Custom GPT via OpenAPI.  
6. (Optionnel) Active CI/CD pour builds automatiques Docker.  

---
