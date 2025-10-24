import logging
import re
from PTT import parse_title
from .database import get_or_fetch_series_year, get_or_fetch_movie_year

logger = logging.getLogger(__name__)

async def extract_caption(title: str) -> str:
    if not title or len(title.strip()) < 3:
        return title

    try:
        data = parse_title(title, translate_languages=True)
        name = data.get("title", "")
        year = data.get("year")
        seasons = data.get("seasons", [])
        episodes = data.get("episodes", [])
        type_ = "series" if seasons else "movie"

        # --- Fetch missing year ---
        if not year:
            if type_ == "series":
                season_no = seasons[0] if seasons else 1
                year = await get_or_fetch_series_year(name, season_no)
            else:
                year = await get_or_fetch_movie_year(name)

        # --- Resolution & Quality & Codec (from parsed data) ---
        resolution = data.get("resolution", "")
        quality = data.get("quality", "")
        codec_raw = (data.get("codec", "") or "").lower()
        codec_map = {"hevc": "x265", "avc": "x264"}
        codec = codec_map.get(codec_raw, codec_raw)

        # --- Bit depth ---
        bit_depth = data.get("bit_depth", "")
        if bit_depth:
            bit_depth = f"{bit_depth}"

        # --- Audio ---
        channels_list = data.get("channels", [])
        audio_list = data.get("audio", [])

        def clean_audio_name(n):
            return (n.replace("Dolby Digital Plus", "DD+")
                     .replace("Dolby Digital", "DD")
                     .replace("Dolby TrueHD", "TrueHD")
                     .replace("Dolby Atmos", "Atmos")
                     .replace("DTS-HD MA", "DTS HD MA")
                     .strip())

        audio_list = [clean_audio_name(a) for a in audio_list]
        audio_fmt = next(
            (fmt for fmt in ["Atmos", "TrueHD", "DD+", "DD", "DTS HD MA", "AAC", "FLAC"]
             if any(fmt.lower() in a.lower() for a in audio_list)),
            ""
        )
        if channels_list:
            audio_fmt = f"{audio_fmt} {channels_list[0]}".strip()

        # --- Languages ---
        languages = data.get("languages", [])
        if languages:
            lang_text = " + ".join(languages)
            if len(languages) == 1:
                audio_lang = f"{languages[0]} Audio"
            elif len(languages) == 2:
                audio_lang = f"Dual Audio ({lang_text})"
            else:
                audio_lang = f"Multi Audio ({lang_text})"
        else:
            audio_lang = ""

        # --- Compose final caption ---
        year_str = f"({year})" if year else ""
        ext = data.get("container", "mkv")
        components = [resolution, quality, bit_depth, codec, audio_fmt, audio_lang]
        components_clean = " ".join(dict.fromkeys(filter(None, components)))  # deduplicate

        if type_ == "series":
            season_no = seasons[0] if seasons else 1
            if episodes:
                ep_part = (f"E{episodes[0]:02d}" if len(episodes) == 1
                           else f"E{episodes[0]:02d} – E{episodes[-1]:02d}")
            else:
                ep_part = "Complete"             
            formatted = f"{name} {year_str} S{season_no:02d} {ep_part} {components_clean}"
        else:
            formatted = f"{name} {year_str} {components_clean}"

        formatted = re.sub(r"\s+", " ", formatted.strip())
        if not formatted.endswith(f".{ext}"):
            formatted += f".{ext}"

        return formatted

    except Exception as e:
        logger.exception("Error extracting caption")
        return title
