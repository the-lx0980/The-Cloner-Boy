import logging
import re
from PTT import parse_title
from .database import get_or_fetch_series_year, get_or_fetch_movie_year

logger = logging.getLogger(__name__)

def extract_caption(title: str) -> str:
    """
    Parse torrent title using Parsett (PTT) with corrected resolution/source override priority.
    Fetches missing year from database if not present in title.
    """
    if not title or len(title.strip()) < 3:
        return title

    try:
        data = parse_title(title, translate_languages=True)
        name = data.get("title") or ""
        year = data.get("year")
        seasons = data.get("seasons") or []
        episodes = data.get("episodes") or []
        type_ = "series" if seasons else "movie"

        # Fetch year if missing
        if not year:
            if type_ == "series":
                season_no = seasons[0] if seasons else 1
                year = get_or_fetch_series_year(name, season_no)
            else:
                year = get_or_fetch_movie_year(name)

        # Base values from PTT
        resolution = data.get("resolution", "")
        quality = data.get("quality", "")
        codec = (data.get("codec", "") or "").lower()
        bit_depth = data.get("bit_depth", "")
        channels_list = data.get("channels", [])
        channels = ", ".join(channels_list)

        t_lower = title.lower()

        # ✅ 1. Resolution Manual Fix (takes priority)
        match_res = re.search(r"(480p|720p|1080p|2160p|4k)", t_lower)
        if match_res:
            resolution = match_res.group(1)

        # ✅ 2. Source Detection (NF / AMZN / WEBRip / HDRip / BluRay / DS4K)
        source_tags = [
            ("ds4k", "DS4K"),
            ("nf", "NF"),
            ("amzn", "AMZN"),
            ("web-dl", "WEB-DL"),
            ("webrip", "WEBRip"),
            ("hdrip", "HDRip"),
            ("bluray", "BluRay"),
            ("bdrip", "BDRip")
        ]
        source = ""
        for tag, name_ in source_tags:
            if tag in t_lower:
                source = name_
                break

        # ✅ 3. Combine source + quality properly
        quality_final = source if source else ""
        if quality and source.lower() not in quality.lower():
            quality_final = f"{quality_final} {quality}".strip()

        # --- Audio + Language Formatting ---
        audio_list = data.get("audio", [])
        languages = data.get("languages", [])

        def clean_audio_name(name: str) -> str:
            name = name.replace("Dolby Digital Plus", "DD+")
            name = name.replace("Dolby Digital", "DD")
            name = name.replace("Dolby TrueHD", "TrueHD")
            name = name.replace("Dolby Atmos", "Atmos")
            name = name.replace("DTS-HD MA", "DTS HD MA")
            return name.strip()

        audio_list = [clean_audio_name(a) for a in audio_list]

        # Audio format priority
        audio_fmt = ""
        for fmt in ["Atmos", "TrueHD", "DD+", "DD", "DTS HD MA", "AAC", "FLAC"]:
            if any(fmt.lower() in a.lower() for a in audio_list):
                audio_fmt = fmt
                break

        # Add channels
        if channels_list:
            ch_info = channels_list[0]
            if audio_fmt:
                audio_fmt = f"{audio_fmt} {ch_info}"

        # --- Language Format ---
        if languages:
            lang_text = " + ".join(languages)
            audio_lang = f"Multi Audio ({lang_text})" if len(languages) > 1 else languages[0]
        else:
            audio_lang = ""

        # --- Year format ---
        year_str = f"({year})" if year else ""

        # --- Final caption ---
        if type_ == "series":
            season_no = seasons[0] if seasons else 1
            if episodes:
                ep_part = f"E{episodes[0]:02d}" if len(episodes) == 1 else f"E{episodes[0]:02d}–E{episodes[-1]:02d}"
            else:
                ep_part = "Complete"
            formatted = f"{name} {year_str} S{season_no:02d} {ep_part} {resolution} {quality_final} {bit_depth} {codec} {audio_fmt} {audio_lang}"
        else:
            formatted = f"{name} {year_str} {resolution} {quality_final} {bit_depth} {codec} {audio_fmt} {audio_lang}"

        # ✅ Ensure correct extension
        if not re.search(r"\.(mkv|mp4|avi|mov)$", formatted, re.I):
            formatted += " .mkv"

        return " ".join(formatted.split())

    except Exception as e:
        logger.exception(f"Caption extraction failed: {e}")
        return title
