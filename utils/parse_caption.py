import logging
from PTT import parse_title
from .tmdb_utils import fetch_year_from_tmdb

logger = logging.getLogger(__name__)

def extract_caption(title: str) -> str:
    """
    Parse a torrent title using Parsett (PTT).
    If year is missing, fetch from TMDb.
    Format according to your rules.
    """
    if not title or len(title.strip()) < 3:
        return title

    try:
        data = parse_title(title, translate_languages=True)
        name = data.get("title")
        year = data.get("year")
        seasons = data.get("seasons") or []
        episodes = data.get("episodes") or []

        # Determine type
        type_ = "series" if seasons else "movie"
        if not year and name:
            year = fetch_year_from_tmdb(name, type_=type_)

        # Quality / print / audio
        quality = data.get("quality", "")
        codec = data.get("codec", "")
        audio = ", ".join(data.get("audio", []))
        resolution = data.get("resolution", "")

        # Format output
        if type_ == "series":
            season_no = seasons[0] if seasons else 1
            ep_part = ""
            if episodes:
                if len(episodes) == 1:
                    ep_part = f"E{episodes[0]:02d}"
                else:
                    ep_part = f"E{episodes[0]:02d}–E{episodes[-1]:02d}"
            else:
                ep_part = "Complete"

            formatted = f"{name} ({year}) S{season_no:02d} {ep_part} {resolution} {quality} {codec} {audio}".strip()

        else:
            formatted = f"{name} ({year}) {resolution} {quality} {codec} {audio}".strip()

        return formatted

    except Exception as e:
        logger.exception(f"Caption extraction failed: {e}")
        return title
