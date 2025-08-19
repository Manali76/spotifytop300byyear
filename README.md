# 🎶 GPT “Top Spotify par Année” — API FastAPI (Top 300 “max coverage”)

Ce projet déploie une API FastAPI que ton **Custom GPT** peut appeler pour obtenir le **Top 300** des titres d'une année,
basé sur la **popularité globale Spotify** (`track.popularity`). L’API balaie **au maximum** la Search API Spotify (~1000 titres),
filtre les dates, déduplique et trie par popularité.

## Étapes rapides
1) Crée une app sur https://developer.spotify.com/dashboard et récupère **Client ID** + **Client Secret**.
2) Mets ces valeurs comme **variables d’environnement** (Render/Docker), jamais dans le code.
3) Déploie sur Render (Blueprint) ou via Docker.
4) Teste `/health` puis `/top?year=2010&limit=300` avec le header `X-Api-Key`.

## Déploiement Render (Blueprint)
- `render.yaml` présent.
- Variables à définir : `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `ACTION_API_KEY`.
- Start: `uvicorn app:app --host 0.0.0.0 --port 8000`

## Schéma OpenAPI (Actions Custom GPT)
Voir dans le README détaillé précédent ou re-demande-moi de te le redonner ici.
