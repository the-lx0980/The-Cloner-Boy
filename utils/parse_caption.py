import logging
from PTT import parse_title

logger = logging.getLogger(__name__)

def extract_caption(title: str) -> str:
    """
    Parse a torrent title using Parsett (PTT).
    Year is optional — if missing, leave blank.
    Format according to your rules.
    """
    if not title or len(title.strip()) < 3:
        return title

    try:
        data = parse_title(title, translate_languages=True)
        name = data.get("title") or ""
        year = data.get("year")  # Keep as-is; don't fetch from API
        seasons = data.get("seasons") or []
        episodes = data.get("episodes") or []

        # Determine type
        type_ = "series" if seasons else "movie"

        # Quality / print / audio
        quality = data.get("quality", "")
        codec = data.get("codec", "")
        audio_list = data.get("audio", [])
        audio = "Dual Audio (" + " + ".join(audio_list) + ")" if len(audio_list) == 2 else \
                "Multi Audio (" + " + ".join(audio_list) + ")" if len(audio_list) > 2 else \
                ", ".join(audio_list)
        resolution = data.get("resolution", "")

        # Format year string
        year_str = f"({year})" if year else ""

        # Format output
        if type_ == "series":
            season_no = seasons[0] if seasons else 1
            if episodes:
                ep_part = f"E{episodes[0]:02d}" if len(episodes) == 1 else f"E{episodes[0]:02d}–E{episodes[-1]:02d}"
            else:
                ep_part = "Complete"

            formatted = f"{name} {year_str} S{season_no:02d} {ep_part} {resolution} {quality} {codec} {audio}".strip()

        else:
            formatted = f"{name} {year_str} {resolution} {quality} {codec} {audio}".strip()

        # Clean multiple spaces
        formatted = " ".join(formatted.split())
        return formatted

    except Exception as e:
        logger.exception(f"Caption extraction failed: {e}")
        return title
