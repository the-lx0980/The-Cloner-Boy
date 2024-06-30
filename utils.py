import re

def extract_movie_details(caption):
    # Movie name patterns
    name_patterns = [
        r"^(.*?)\s\(\d{4}\)",  # Pattern 1: Movie name followed by (year)
        r"^(.*?)\s\d{4}",  # Pattern 2: Movie name followed by year
        r"^(.*?)\s\d{3,4}p",  # Pattern 3: Movie name followed by quality
        r"^(.*?)(?=\s\d{4})",  # Pattern 4: Movie name until a space followed by 4 digits (year)
    ]

    # Year patterns
    year_patterns = [
        r"\((\d{4})\)",  # Pattern 1: (year)
        r"\b(\d{4})\b",  # Pattern 2: year not within parentheses
    ]

    # Quality patterns
    quality_patterns = [
        r"\d{3,4}p",  # Pattern 1: 3 or 4 digits followed by 'p'
        r"\b(4|8|10)K\b",  # Pattern 2: 4K, 8K, 10K
        r"\b(FHD|HD|SD)\b",  # Pattern 3: FHD, HD, SD
    ]

    # Print patterns
    print_patterns = [
        "PreDVDRip", "CAM-Rip", "HDTS", "CAMRip", "HQ S-Print", "PreDvD", "DVD-Scr", "PreDVD-Rip"
    ]

    movie_name = "Unknown"
    year = "Unknown"
    quality = "Unknown"
    movie_print = None

    # Extract movie name
    for name_pattern in name_patterns:
        movie_name_match = re.search(name_pattern, caption)
        if movie_name_match:
            movie_name = movie_name_match.group(1).strip()
            break

    # Extract year
    for year_pattern in year_patterns:
        year_match = re.search(year_pattern, caption)
        if year_match:
            year = year_match.group(1)
            break

    # Remove the extracted year and other potential non-name parts from the movie name if included
    if movie_name != "Unknown" and year != "Unknown":
        movie_name = re.sub(r"\s*\(\d{4}\)|\d{4}", "", movie_name).strip()

    # Extract quality
    for quality_pattern in quality_patterns:
        quality_match = re.search(quality_pattern, caption)
        if quality_match:
            quality = quality_match.group()
            break

    # Extract print if present
    for print_pattern in print_patterns:
        if print_pattern in caption:
            movie_print = print_pattern
            break

    if movie_print:
        #quality = f"{quality} {movie_print}"
        return movie_name, year, quality
    else:
        return movie_name, year, quality
