from abc import ABC, abstractmethod
from typing import Any

from app.settings.settings import PROVIDER_A_API_KEY, PROVIDER_B_API_KEY
from providers import provider_a, provider_b

from app.integration.provider_field_mappings import PROVIDER_A_MAPPINGS, PROVIDER_B_MAPPINGS
from app.utils.utils import get_nested_dict_value


class Provider(ABC):
    @abstractmethod
    async def fetch_events(self, symbols: list[str], days_ahead: int = 30) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_event(self, event_id: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def adapter(self, event: dict) -> dict:
        pass


class ProviderA(Provider):
    def __init__(self, api_key: str = PROVIDER_A_API_KEY):
        self.api_key = api_key
        self.client = provider_a.ProviderA(api_key=api_key)

    async def fetch_events(self, symbols: list[str], days_ahead: int = 30) -> list[dict[str, Any]]:
        events = await self.client.fetch_events(symbols=symbols, days_ahead=days_ahead)
        return [self.adapter(event) for event in events]

    async def get_event(self, event_id: str) -> dict[str, Any] | None:
        event = await self.client.get_event(event_id=event_id)
        return self.adapter(event) if event else None

    def adapter(self, event: dict) -> dict:
        provider_dict = {key: event.get(value) for key, value in PROVIDER_A_MAPPINGS.items()}
        provider_dict["description"] = None
        provider_dict["exchange"] = None
        if event.get("event_time"):
            provider_dict["event_date"] = f'{provider_dict["event_date"]}T{event["event_time"]}Z'
        else:
            provider_dict["event_date"] = f'{provider_dict["event_date"]}T00:00:00Z'
        return provider_dict


class ProviderB(Provider):
    def __init__(self, api_key: str = PROVIDER_B_API_KEY):
        self.api_key = api_key
        self.client = provider_b.ProviderB(api_key=api_key)

    async def fetch_events(self, symbols: list[str], days_ahead: int = 30) -> list[dict[str, Any]]:
        events = await self.client.fetch_events(symbols=symbols, days_ahead=days_ahead)
        return [self.adapter(event) for event in events]

    async def get_event(self, event_id: str) -> dict[str, Any] | None:
        event = await self.client.get_event(event_id=event_id)
        return self.adapter(event) if event else None

    def adapter(self, event: dict) -> dict:
        provider_dict = {key: get_nested_dict_value(event, value.split(".")) for key, value in PROVIDER_B_MAPPINGS.items()}
        event_details_key = str(provider_dict.get("event_type")).split("_")[-1].lower() + "_data"
        provider_dict["details"] = event.get(event_details_key)
        return provider_dict


class ProviderFactory:
    @staticmethod
    def get_provider(provider_name: str) -> Provider:
        if provider_name == "provider_a":
            return ProviderA(api_key=PROVIDER_A_API_KEY)
        elif provider_name == "provider_b":
            return ProviderB(api_key=PROVIDER_B_API_KEY)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
