import os, time, base64, logging, random, requests
from typing import List, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException, Header, Query

# =========================
# Variables d'environnement
# =========================
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
ACTION_API_KEY = os.getenv("ACTION_API_KEY", "")

# Top par défaut + bornes
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "300"))
MAX_LIMIT = int(os.getenv("MAX_LIMIT", "500"))

# Cache résultats (en secondes)
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

# Spotify Search (limites maximales)
SEARCH_PAGE_SIZE = 50        # max autorisé par Spotify
SEARCH_MAX_OFFSET = 1000     # offset max autorisé → ~1000 items max
HARD_MAX_CANDIDATES = 1000   # viser le maximum pour un Top 300 plus sûr

# =========================
# Logging & app
# =========================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("top-by-year-max")
app = FastAPI(title="Top by Year (Spotify popularity, max coverage)")

_session = requests.Session()
_token_cache: Dict[str, Any] = {"access_token": None, "exp": 0.0}
# cache des listes filtrées/triées par année (post-traitement complet)
_results_cache: Dict[int, Dict[str, Any]] = {}

# =========================
# Utilitaires
# =========================
def _sleep_with_jitter(seconds: float) -> None:
    time.sleep(max(0.5, seconds) + random.uniform(0.0, 0.5))

def _get_token() -> str:
    """Client Credentials avec cache + gestion 429."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["exp"]:
        return _token_cache["access_token"]
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise HTTPException(500, "SPOTIFY_CLIENT_ID/SECRET manquants.")

    auth = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    r = _session.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    if r.status_code == 429:
        retry = int(r.headers.get("Retry-After", "1") or "1")
        _sleep_with_jitter(retry)
        return _get_token()
    r.raise_for_status()
    data = r.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["exp"] = now + int(data.get("expires_in", 3600)) - 30
    return _token_cache["access_token"]

def _search_year_max(year: int) -> List[Dict[str, Any]]:
    """Balaye jusqu'à ~1000 pistes (limite API) pour maximiser la couverture."""
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    items: List[Dict[str, Any]] = []
    collected = 0

    # offsets 0, 50, 100, ..., < 1000
    for offset in range(0, SEARCH_MAX_OFFSET, SEARCH_PAGE_SIZE):
        remaining = HARD_MAX_CANDIDATES - collected
        if remaining <= 0:
            break
        page_limit = min(SEARCH_PAGE_SIZE, remaining)
        params = {"q": f"year:{year}", "type": "track", "limit": page_limit, "offset": offset}
        r = _session.get("https://api.spotify.com/v1/search", headers=headers, params=params, timeout=15)
        if r.status_code == 429:
            retry = int(r.headers.get("Retry-After", "1") or "1")
            _sleep_with_jitter(retry)
            continue
        r.raise_for_status()
        batch = (r.json().get("tracks") or {}).get("items") or []
        if not batch:
            break
        items.extend(batch)
        collected += len(batch)
        if len(batch) < page_limit:
            break  # plus d'items dispo pour cette requête

    return items

def _canonical_title(name: str) -> str:
    """Normalisation légère (évite faux doublons sans supprimer des versions distinctes)."""
    s = (name or "").casefold()
    for tag in [" - remaster", " - remastered", " - live", " - radio edit", " - single version"]:
        s = s.replace(tag, "")
    return s.strip()

def _filter_and_rank(tracks: List[Dict[str, Any]], year: int) -> List[Dict[str, Any]]:
    """Filtre année exacte si connue, dédup (id puis combo titre+artistes), tri par popularité DESC puis titre."""
    seen_ids, seen_combo, filtered = set(), set(), []
    for t in tracks:
        tid = t.get("id") or ""
        name = t.get("name") or ""
        artists = t.get("artists") or []
        album = t.get("album") or {}
        release_date = (album.get("release_date") or "")

        # Filtrage année stricte si date dispo
        if release_date[:4] and release_date[:4] != str(year):
            continue

        # Dédup prioritaire par id
        if tid and tid in seen_ids:
            continue

        # Dédup secondaire par combo (titre normalisé + ids artistes triés)
        combo = (_canonical_title(name), tuple(sorted(a.get("id") or "" for a in artists)))
        if combo in seen_combo:
            continue

        if tid:
            seen_ids.add(tid)
        seen_combo.add(combo)
        filtered.append(t)

    # Tri déterministe : popularité DESC puis titre
    filtered.sort(key=lambda x: (x.get("popularity", 0), (x.get("name") or "").casefold()), reverse=True)
    return filtered

def _format(tracks: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, t in enumerate(tracks[:limit], start=1):
        album = t.get("album") or {}
        out.append({
            "rank": i,
            "title": t.get("name") or "",
            "artists": [a.get("name") or "" for a in (t.get("artists") or [])],
            "popularity": int(t.get("popularity", 0)),
            "album": album.get("name") or "",
            "release_date": album.get("release_date") or "",
            "spotify_url": (t.get("external_urls") or {}).get("spotify", ""),
            "id": t.get("id") or "",
            "uri": t.get("uri") or "",
        })
    return out

def _compute_ranked_max(year: int) -> List[Dict[str, Any]]:
    """Retourne la liste filtrée+triée pour l'année, en balayant systématiquement jusqu'à 1000 candidats (cache TTL)."""
    now = time.time()
    cached = _results_cache.get(year)
    if cached and now - cached["at"] < CACHE_TTL:
        return cached["results"]

    candidates = _search_year_max(year)
    ranked = _filter_and_rank(candidates, year)
    _results_cache[year] = {"at": now, "results": ranked}
    return ranked

def compute_top(year: int, limit: int) -> List[Dict[str, Any]]:
    if not (1900 <= year <= 2100):
        raise HTTPException(400, "Année invalide (1900–2100).")
    if not (1 <= limit <= MAX_LIMIT):
        raise HTTPException(400, f"'limit' invalide (1–{MAX_LIMIT}).")
    ranked = _compute_ranked_max(year)
    return _format(ranked, limit)

# =========================
# Endpoints
# =========================
@app.get("/top")
def top(
    year: int = Query(..., description="Année ex: 2010"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description=f"Taille du Top renvoyé (défaut {DEFAULT_LIMIT}, max {MAX_LIMIT})"),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
):
    # Auth simple via clé API
    if ACTION_API_KEY and x_api_key != ACTION_API_KEY:
        raise HTTPException(401, "Clé API invalide.")
    try:
        results = compute_top(year, limit)
        return {
            "year": year,
            "limit": limit,
            "scanned_candidates": 1000,  # cible max (informative)
            "results": results
        }
    except HTTPException:
        raise
    except Exception:
        log.exception("Erreur serveur interne")
        raise HTTPException(500, "Erreur serveur interne.")

@app.get("/health")
def health():
    return {"ok": True}
