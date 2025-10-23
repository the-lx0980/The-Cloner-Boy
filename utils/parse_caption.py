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

        # Placeholder for fetching missing year
        if not year:
            if type_ == "series":
                season_no = seasons[0] if seasons else 1
                year = await get_or_fetch_series_year(name, season_no)
            else:
                year = await get_or_fetch_movie_year(name)

        t_lower = title.lower()

        # --- Resolution ---
        match_res = re.search(r"(480p|720p|1080p|2160p|4k|uhd)", t_lower)
        resolution = match_res.group(1) if match_res else data.get("resolution", "")

        # --- Source / Quality ---
        source_tags = [
            ("ds4k", "DS4K"),
            ("nf", "NF"),
            ("amzn", "AMZN"),
            ("web-dl", "WEB-DL"),
            ("webrip", "WEBRip"),
            ("hdrip", "HDRip"),
            ("bluray", "BluRay"),
            ("bdrip", "BDRip"),
        ]
        source_list = [name_ for tag, name_ in source_tags if tag in t_lower]
        source = " ".join(dict.fromkeys(filter(None, source_list)))  # deduplicate

        # Bit depth
        bit_depth = data.get("bit_depth", "")
        if bit_depth and bit_depth not in t_lower:
            bit_depth = f"{bit_depth}"

        # --- Codec normalization ---
        codec = (data.get("codec", "") or "").lower()
        codec_map = {"hevc": "x265", "avc": "x264"}
        codec = codec_map.get(codec, codec.upper())

        # Detect codec from title if missing
        if not codec or codec.upper() in ["HEVC", "X265", "X264"]:
            if re.search(r"\bHEVC\b", title, re.IGNORECASE):
                codec = "x265"
            elif re.search(r"\bX265\b", title, re.IGNORECASE):
                codec = "x265"
            elif re.search(r"\bX264\b", title, re.IGNORECASE):
                codec = "x264"

        # --- Audio ---
        channels_list = data.get("channels", [])
        if not channels_list:
            ch_match = re.search(r"(\d\.\d)", title)
            if ch_match:
                channels_list = [ch_match.group(1)]

        def clean_audio_name(n):
            return (n.replace("Dolby Digital Plus", "DD+")
                     .replace("Dolby Digital", "DD")
                     .replace("Dolby TrueHD", "TrueHD")
                     .replace("Dolby Atmos", "Atmos")
                     .replace("DTS-HD MA", "DTS HD MA")
                     .strip())

        audio_list = [clean_audio_name(a) for a in data.get("audio", [])]
        audio_fmt = next((fmt for fmt in ["Atmos", "TrueHD", "DD+", "DD", "DTS HD MA", "AAC", "FLAC"]
                          if any(fmt.lower() in a.lower() for a in audio_list)), "")
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

        year_str = f"({year})" if year else ""
        is_hevc = "HEVC" if 'hevc' in title.lower() else ""
        ext = data.get("container", "mkv")

        # --- Compose final caption ---
        components = [resolution, is_hevc, source, bit_depth, codec, audio_fmt, audio_lang]
        components_clean = " ".join(dict.fromkeys(filter(None, components)))  # deduplicate

        if type_ == "series":
            season_no = seasons[0] if seasons else 1
            if episodes:
                ep_part = f"E{episodes[0]:02d}" if len(episodes) == 1 else f"E{episodes[0]:02d} – E{episodes[-1]:02d}"
            else:
                ep_part = "Complete"
            formatted = f"{name} {year_str} S{season_no:02d} {ep_part} {components_clean}"
        else:
            formatted = f"{name} {year_str} {components_clean}"

        formatted = re.sub(r"\s+", " ", formatted.strip())
        if not formatted.endswith(f".{ext}"):
            formatted += f" .{ext}"

        return formatted

    except Exception as e:
        print("Error extracting caption:", e)
        return title
        
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
