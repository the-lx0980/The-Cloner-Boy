import logging
import re
from PTT import parse_title

logger = logging.getLogger(__name__)

def extract_caption(title: str) -> str:
    """
    Parse torrent title using Parsett (PTT) and correct resolution/source parsing.
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

        # Extract fields
        resolution = data.get("resolution", "")
        quality = data.get("quality", "")
        codec = (data.get("codec", "") or "").lower()
        bit_depth = data.get("bit_depth", "")
        channels_list = data.get("channels", [])
        channels = ", ".join(channels_list)

        # --- Manual recheck from title text (for missing or wrong detection) ---
        t_lower = title.lower()

        # ✅ Resolution Fix
        if not resolution:
            match = re.search(r"(480p|720p|1080p|2160p|4k)", t_lower)
            if match:
                resolution = match.group(1)

        # ✅ Source Fix (WEBRip / WEB-DL / HDRip / BluRay / DS4K / NF / AMZN)
        source_tags = {
            "webrip": "WEBRip",
            "web-dl": "WEB-DL",
            "hdrip": "HDRip",
            "bluray": "BluRay",
            "bdrip": "BDRip",
            "ds4k": "DS4K",
            "nf": "NF",
            "amzn": "AMZN"
        }
        source = ""
        for tag, name_ in source_tags.items():
            if tag in t_lower:
                source = name_
                break

        if source and source not in quality:
            quality = (source + " " + quality).strip()

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

        # --- Audio format selection ---
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

        # --- Languages ---
        if languages:
            lang_text = " + ".join(languages)
            if len(languages) > 1:
                audio_lang = f"Multi Audio ({lang_text})"
            else:
                audio_lang = f"{languages[0]}"
        else:
            audio_lang = ""

        # --- Year formatting ---
        year_str = f"({year})" if year else ""

        # --- Caption format ---
        if type_ == "series":
            season_no = seasons[0] if seasons else 1
            if episodes:
                ep_part = f"E{episodes[0]:02d}" if len(episodes) == 1 else f"E{episodes[0]:02d}–E{episodes[-1]:02d}"
            else:
                ep_part = "Complete"
            formatted = f"{name} {year_str} S{season_no:02d} {ep_part} {resolution} {quality} {bit_depth} {codec} {audio_fmt} {audio_lang}"

        else:
            formatted = f"{name} {year_str} {resolution} {quality} {bit_depth} {codec} {audio_fmt} {audio_lang}"

        # Add .mkv at end (if not already)
        if not re.search(r"\.(mkv|mp4|avi|mov)$", formatted, re.I):
            formatted += " .mkv"

        formatted = " ".join(formatted.split())
        return formatted.strip()

    except Exception as e:
        logger.exception(f"Caption extraction failed: {e}")
        return title
