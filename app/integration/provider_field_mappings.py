PROVIDER_A_MAPPINGS = {
    "event_id": "event_id",
    "symbol": "ticker", # FK to symbols table
    "event_type": "type", # FK to eventtype table
    "event_date": "date",
    "title": "title",
    "details": "details",
    "event_metadata": "metadata"
}

PROVIDER_B_MAPPINGS = {
    "event_id": "id",
    "symbol": "instrument.symbol", # FK to symbols table
    "event_type": "event.category", # FK to eventtype table
    "event_date": "event.scheduled_at",
    "title": "event.title",
    "details": "details",
    "event_metadata": "provider_metadata",
    "description": "event.description",
    "exchange": "instrument.exchange", # FK to exchange table
}

A_TO_B_MAPPINGS = {
    "earnings": "earnings_release",
    "dividend": "dividend_payment",
    "split": "stock_split",
}
