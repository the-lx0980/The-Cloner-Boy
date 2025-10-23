import logging
import re
from PTT import parse_title
import asyncio
from .database import (
    get_or_fetch_series_year,
    get_or_fetch_movie_year
)

logger = logging.getLogger(__name__)


async def extract_caption(title: str) -> str:
    """
    Parse torrent title using Parsett (PTT) with:
    - Correct resolution/source override
    - Auto fetch release year if missing
    - TMDb for movies, TMDb for series, AniList for anime
    """
    if not title or len(title.strip()) < 3:
        return title.strip()

    try:
        data = parse_title(title, translate_languages=True)
        name = data.get("title", "").strip()
        year = data.get("year")
        seasons = data.get("seasons") or []
        episodes = data.get("episodes") or []
        resolution = data.get("resolution", "")
        quality = data.get("quality", "")
        codec = (data.get("codec") or "").lower()
        bit_depth = data.get("bit_depth", "")
        channels_list = data.get("channels", [])
        audio_list = data.get("audio", [])
        languages = data.get("languages", [])

        # Determine type (anime / series / movie)
        lower_name = name.lower()
        if seasons:
            type_ = "series"
        else:
            type_ = "movie"

        # --- Auto fetch missing year ---
        if not year:
            if type_ == "anime":
                season_no = seasons[0] if seasons else 1
                year = await get_or_fetch_anime_year(name, season_no)
            elif type_ == "series":
                season_no = seasons[0] if seasons else 1
                year = await get_or_fetch_series_year(name, season_no)
            else:
                year = await get_or_fetch_movie_year(name)

        year_str = f"({year})" if year else ""

        # --- Resolution ---
        t_lower = title.lower()
        match_res = re.search(r"(480p|720p|1080p|2160p|4k)", t_lower)
        if match_res:
            resolution = match_res.group(1)

        # --- Source Detection ---
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
        source = next((name_ for tag, name_ in source_tags if tag in t_lower), "")
        quality_final = " ".join(filter(None, [source, quality]))

        # --- Audio Formatting ---
        def clean_audio_name(name: str) -> str:
            replacements = {
                "Dolby Digital Plus": "DD+",
                "Dolby Digital": "DD",
                "Dolby TrueHD": "TrueHD",
                "Dolby Atmos": "Atmos",
                "DTS-HD MA": "DTS HD MA"
            }
            for k, v in replacements.items():
                name = name.replace(k, v)
            return name.strip()

        audio_list = [clean_audio_name(a) for a in audio_list]
        audio_fmt = next((fmt for fmt in ["Atmos", "TrueHD", "DD+", "DD", "DTS HD MA", "AAC", "FLAC"]
                          if any(fmt.lower() in a.lower() for a in audio_list)), "")

        if channels_list and audio_fmt:
            audio_fmt = f"{audio_fmt} {channels_list[0]}"

        if languages:
            lang_text = " + ".join(languages)
            audio_lang = f"Multi Audio ({lang_text})" if len(languages) > 1 else languages[0]
        else:
            audio_lang = ""

        # --- Final Caption Format ---
        if type_ in ["series", "anime"]:
            season_no = seasons[0] if seasons else 1
            if episodes:
                ep_part = (
                    f"E{episodes[0]:02d}" if len(episodes) == 1
                    else f"E{episodes[0]:02d}–E{episodes[-1]:02d}"
                )
            else:
                ep_part = "Complete"
            formatted = (
                f"{name} {year_str} S{season_no:02d} {ep_part} "
                f"{resolution} {quality_final} {bit_depth} {codec} {audio_fmt} {audio_lang}"
            )
        else:
            formatted = (
                f"{name} {year_str} {resolution} {quality_final} "
                f"{bit_depth} {codec} {audio_fmt} {audio_lang}"
            )

        # Append file extension if missing
        if not re.search(r"\.(mkv|mp4|avi|mov)$", formatted, re.I):
            formatted += " .mkv"

        return " ".join(formatted.split())

    except Exception as e:
        logger.exception(f"❌ Caption extraction failed: {e}")
        return title
