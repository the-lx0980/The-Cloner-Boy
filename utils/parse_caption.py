from PTT import parser  # Parser from your link
from .tmdb_utils import fetch_year_from_tmdb

async def extract_caption_parser(caption: str) -> str:
    """
    Parse caption using PTT parser, add TMDb year if missing.
    """
    if not caption or len(caption.strip()) < 3:
        return caption

    try:
        result = parser.parse_caption(caption)  # PTT parser returns dict
        # Example result: {"name": "Venom", "year": None, "season": None, "episode": None, "quality": "1080p"}
        if not result.get("year"):
            type_ = "series" if result.get("season") else "movie"
            result["year"] = fetch_year_from_tmdb(result["name"], type_=type_)

        # Build formatted caption
        if result.get("season"):
            # Series
            ep_part = f"E{result['episode']:02d}" if result.get("episode") else "Complete"
            formatted = f"{result['name']} ({result['year']}) S{result['season']:02d} {ep_part} {result.get('quality','')} {result.get('print','')} {result.get('audio','')}".strip()
        else:
            # Movie
            formatted = f"{result['name']} ({result['year']}) {result.get('quality','')} {result.get('print','')} {result.get('audio','')}".strip()

        return formatted

    except Exception as e:
        logger.exception(f"Caption parser failed: {e}")
        return caption
