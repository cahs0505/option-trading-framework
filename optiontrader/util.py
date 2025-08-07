import datetime

"""
All date should be in ISO 8601 format (YYYY-MM-DD)
"""
def validate_date(date_text):
    try:
        datetime.date.fromisoformat(date_text)
    except ValueError:
        raise ValueError(f"Incorrect data format : {date_text}, should be YYYY-MM-DD")