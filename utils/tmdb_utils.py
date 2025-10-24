import tmdbsimple as tmdb
import logging

logger = logging.getLogger(__name__)
tmdb.API_KEY = "b043bef236e1b972f25dcb382ef1af76"  # Set via env or config

def fetch_year_from_tmdb(title: str, type_: str = "movie") -> str:
    """
    Fetch release year from TMDb if missing.
    """
    try:
        search = tmdb.Search()
        if type_ == "movie":
            response = search.movie(query=title)
            if response['results']:
                date = response['results'][0].get('release_date', '')
                return date.split("-")[0] if date else "Unknown"
        elif type_ == "series":
            response = search.tv(query=title)
            if response['results']:
                date = response['results'][0].get('first_air_date', '')
                return date.split("-")[0] if date else "Unknown"
    except Exception as e:
        logger.warning(f"TMDb fetch failed for {title}: {e}")
    return "Unknown"
