import logging
import requests
from database import save_anime, get_anime_year

ANILIST_API_URL = "https://graphql.anilist.co"

def get_anime_year(title: str, season_number: int):
    str_title = title
    str_sesion = season_number
    base_variations = [
        f"{title} Season {season_number}",
        f"{title} Part {season_number}",
        f"{title} {season_number}",
        f"{title} {season_number}th Season",
        f"{title} Final Season",
        f"{title} Arc {season_number}",
        f"{title} TV Season {season_number}",
        f"{title} Special Season {season_number}",
    ]

    variations = []
    for v in base_variations:
        variations += [v, v.lower(), v.upper(), v.title()]

    query = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { romaji native }
        synonyms
      }
    }
    '''
    variables = {"search": title}
    try:
        response = requests.post(ANILIST_API_URL, json={"query": query, "variables": variables})
        response.raise_for_status()
        data = response.json().get("data", {}).get("Media", {})
        if data:
            titles_to_add = []
            romaji = data.get("title", {}).get("romaji")
            native = data.get("title", {}).get("native")
            synonyms = data.get("synonyms", [])

            for t in [romaji, native] + synonyms:
                if t:
                    titles_to_add += [
                        f"{t} Season {season_number}",
                        f"{t} Part {season_number}",
                        f"{t} {season_number}",
                        f"{t} Final Season",
                        f"{t} Arc {season_number}",
                        f"{t} TV Season {season_number}",
                        f"{t} Special Season {season_number}"
                    ]
            for t in titles_to_add:
                variations += [t, t.lower(), t.upper(), t.title()]

    except requests.RequestException as e:
        logger.warning(f"Error fetching AniList titles for '{title}': {e}")

    return list(dict.fromkeys(variations))


def get_anime_season_year(title: str, season_number: int) -> int | None:
    search_titles = generate_search_titles(title, season_number)
    query = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { romaji }
        startDate { year }
      }
    }
    '''
    for search_title in search_titles:
        variables = {"search": search_title}
        try:
            response = requests.post(ANILIST_API_URL, json={"query": query, "variables": variables})
            response.raise_for_status()
            media = response.json().get("data", {}).get("Media")
            if media:
                year = media.get("startDate", {}).get("year")
                if year:
                    title_out = media['title']['romaji']
                    if "Final Season" in title_out:
                        logger.info(f"✅ {title_out} ({year})")
                    else:
                        logger.info(f"✅ {title_out} Season {season_number}: {year}")
                    save_anime(str_title, str_sesion, year)
                    return year
        except requests.RequestException:
            continue

    logger.warning(f"❌ No data found for '{title}' Season {season_number}")
    return None

async def get_or_fetch_anime_year(title: str, season: int) -> int | None:
    """
    1. Check MongoDB first.
    2. If missing, get year
    3. Store result automatically.
    """
    year = get_anime_year(title, season)
    if year:
        logger.info(f"📦 Found in DB: {title} S{season} → {year}")
        return year

    logger.info(f"🔍 Year missing for {title} S{season}, fetching via AI...")
    return await get_anime_year(title, season)
