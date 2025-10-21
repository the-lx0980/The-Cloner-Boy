import logging
from PTT import parse_title

logger = logging.getLogger(__name__)

def extract_caption(title: str) -> str:
    """
    Parse a torrent title using Parsett (PTT).
    Adds proper language info, Dolby/DD formatting like 'DD 5.1', and ensures '.mkv' at the end.
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
        channels_list = data.get("channels", [])
        channels = ", ".join(channels_list)
        extension = data.get("extension", "").lower()

        # --- Audio + Language Formatting ---
        audio_list = data.get("audio", [])
        languages = data.get("languages", [])

        # Clean and normalize Dolby/DTS names
        def clean_audio_name(name: str) -> str:
            name = name.replace("Dolby Digital Plus", "DD+")
            name = name.replace("Dolby Digital", "DD")
            name = name.replace("Dolby TrueHD", "TrueHD")
            name = name.replace("Dolby Atmos", "Atmos")
            name = name.replace("DTS-HD MA", "DTS HD MA")
            return name.strip()

        audio_list = [clean_audio_name(a) for a in audio_list]

        # Detect best audio format
        audio_fmt = ""
        if any("Atmos" in a for a in audio_list):
            audio_fmt = "Atmos"
        elif any("TrueHD" in a for a in audio_list):
            audio_fmt = "TrueHD"
        elif any("DD+" in a for a in audio_list):
            audio_fmt = "DD+"
        elif any("DD" in a for a in audio_list):
            audio_fmt = "DD"
        elif any("DTS" in a for a in audio_list):
            audio_fmt = "DTS HD MA"
        elif any("AAC" in a for a in audio_list):
            audio_fmt = "AAC"
        elif any("FLAC" in a for a in audio_list):
            audio_fmt = "FLAC"

        # Add channel info
        ch_info = ""
        if channels_list:
            ch_info = channels_list[0]
        if audio_fmt and ch_info:
            audio_fmt = f"{audio_fmt} {ch_info}"

        # --- Language text ---
        if languages:
            lang_text = " + ".join(languages)
            if len(languages) > 1:
                audio_lang = f"Multi Audio ({lang_text})"
            else:
                audio_lang = lang_text
        else:
            audio_lang = ""

        # --- Year formatting ---
        year_str = f"({year})" if year else ""

        # --- Final caption format ---
        if type_ == "series":
            season_no = seasons[0] if seasons else 1
            if episodes:
                ep_part = f"E{episodes[0]:02d}" if len(episodes) == 1 else f"E{episodes[0]:02d}–E{episodes[-1]:02d}"
            else:
                ep_part = "Complete"
            formatted = f"{name} {year_str} S{season_no:02d} {ep_part} {resolution} {quality} {bit_depth} {codec} {audio_fmt} {audio_lang}".strip()

        else:
            formatted = f"{name} {year_str} {resolution} {quality} {bit_depth} {codec} {audio_fmt} {audio_lang}".strip()

        # Add .mkv at end (only if no other extension present)
        if not any(formatted.lower().endswith(ext) for ext in [".mkv", ".mp4", ".avi", ".mov"]):
            formatted += ".mkv"

        # Clean spaces
        formatted = " ".join(formatted.split())
        return formatted.strip()

    except Exception as e:
        logger.exception(f"Caption extraction failed: {e}")
        return title
