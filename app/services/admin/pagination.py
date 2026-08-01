def build_page_urls(
    *,
    base_path: str,
    limit: int,
    offset: int,
    total: int,
    query_suffix: str = "",
) -> tuple[str | None, str | None]:
    next_url: str | None = None
    previous_url: str | None = None
    separator = "&" if "?" in base_path else "?"
    suffix = f"&{query_suffix}" if query_suffix else ""

    if offset + limit < total:
        next_url = f"{base_path}{separator}limit={limit}&offset={offset + limit}{suffix}"

    if offset > 0:
        previous_offset = max(offset - limit, 0)
        previous_url = f"{base_path}{separator}limit={limit}&offset={previous_offset}{suffix}"

    return next_url, previous_url
