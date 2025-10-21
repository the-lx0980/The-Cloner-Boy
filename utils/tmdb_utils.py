import tmdbsimple as tmdb
import logging

logger = logging.getLogger(__name__)
tmdb.API_KEY = "b043bef236e1b972f25dcb382ef1af76"  # Set via env or config

def fetch_year_from_tmdb(title: str, type_: str = "movie") -> str:
    """
    Fetch release year from TMDb for a movie or series if missing.
    """
    try:
        if type_ == "movie":
            search = tmdb.Search()
            response = search.movie(query=title)
            if response['results']:
                release_date = response['results'][0].get('release_date', '')
                return release_date.split("-")[0] if release_date else "Unknown"
        elif type_ == "series":
            search = tmdb.Search()
            response = search.tv(query=title)
            if response['results']:
                first_air_date = response['results'][0].get('first_air_date', '')
                return first_air_date.split("-")[0] if first_air_date else "Unknown"
    except Exception as e:
        logger.warning(f"TMDb fetch failed for {title}: {e}")
    return "Unknown"
