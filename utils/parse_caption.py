import logging
from PTT import parse_title

logger = logging.getLogger(__name__)

def extract_caption(title: str) -> str:
    """
    Parse a torrent title using Parsett (PTT).
    Adds proper language info and formats Dolby terms.
    """
    if not title or len(title.strip()) < 3:
        return title

    try:
        data = parse_title(title, translate_languages=True)
        name = data.get("title") or ""
        year = data.get("year")
        seasons = data.get("seasons") or []
        episodes = data.get("episodes") or []

        # Detect type
        type_ = "series" if seasons else "movie"

        # Extract details
        quality = data.get("quality", "")
        codec = (data.get("codec", "") or "").lower()
        resolution = data.get("resolution", "")
        bit_depth = data.get("bit_depth", "")
        channels = ", ".join(data.get("channels", []))

        # --- Audio + Language Formatting ---
        audio_list = data.get("audio", [])
        languages = data.get("languages", [])

        # Handle Dolby / DTS names
        def clean_audio_name(name: str) -> str:
            name = name.replace("Dolby Digital", "D D")
            name = name.replace("Dolby TrueHD", "TrueHD")
            name = name.replace("Dolby Atmos", "Atmos")
            name = name.replace("DTS-HD MA", "DTS HD MA")
            return name.strip()

        audio_list = [clean_audio_name(a) for a in audio_list]

        # Combine audio + language info
        if len(audio_list) == 2:
            audio_lang = f"Dual Audio ({' + '.join(languages)})" if languages else f"Dual Audio ({' + '.join(audio_list)})"
        elif len(audio_list) > 2:
            audio_lang = f"Multi Audio ({' + '.join(languages)})" if languages else f"Multi Audio ({' + '.join(audio_list)})"
        else:
            if languages:
                audio_lang = ", ".join(languages)
            else:
                audio_lang = ", ".join(audio_list)

        # --- Year formatting ---
        year_str = f"({year})" if year else ""

        # --- Final caption format ---
        if type_ == "series":
            season_no = seasons[0] if seasons else 1
            if episodes:
                ep_part = f"E{episodes[0]:02d}" if len(episodes) == 1 else f"E{episodes[0]:02d}–E{episodes[-1]:02d}"
            else:
                ep_part = "Complete"
            formatted = f"{name} {year_str} S{season_no:02d} {ep_part} {resolution} {quality} {bit_depth} {codec} {audio_lang} {channels}"

        else:
            formatted = f"{name} {year_str} {resolution} {quality} {bit_depth} {codec} {audio_lang} {channels}"

        # Clean spaces
        formatted = " ".join(formatted.split())
        return formatted.strip()

    except Exception as e:
        logger.exception(f"Caption extraction failed: {e}")
        return title
