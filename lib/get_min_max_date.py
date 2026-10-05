import pandas as pd

def min_max_date_string(gdf, date_column):
    photo_series = gdf[date_column].astype(str).str.strip()
    parsed_photo_dates = []

    for value in photo_series:
        if value in {"", "nan", "NaN", "None", "none", "NULL", "null", "<NA>"}:
            parsed_photo_dates.append(pd.NaT)
            continue

        try:
            parsed_photo_dates.append(pd.to_datetime(value, errors="raise"))
        except (TypeError, ValueError):
            try:
                normalized = value.replace("/", "-")
                parsed_photo_dates.append(pd.to_datetime(normalized, errors="raise"))
            except (TypeError, ValueError):
                parsed_photo_dates.append(pd.NaT)

    photo_dates = pd.Series(parsed_photo_dates)
    valid_photo_dates = photo_dates.dropna()

    if not valid_photo_dates.empty:
        oldest_date = valid_photo_dates.min().strftime("%d %B %Y")
        newest_date = valid_photo_dates.max().strftime("%d %B %Y")
    else:
        oldest_date = "N/A"
        newest_date = "N/A"

    return oldest_date, newest_date