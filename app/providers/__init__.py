"""Provider registry.

Which class is responsible for an endpoint is decided by the ``provider``
field in the configuration. A new provider is registered here — nothing more
is needed.
"""

from __future__ import annotations

from typing import Callable

from app.config import EndpointConfig
from app.providers.base import (
    ChatNachricht,
    Generierungsanfrage,
    Provider,
    ProviderFehler,
    Stueck,
)
from app.providers.anthropic import AnthropicProvider
from app.providers.mock import MockProvider, mock_endpunkt
from app.providers.openai_kompatibel import OpenAIKompatiblerProvider

_REGISTRY: dict[str, Callable[[EndpointConfig], Provider]] = {
    "openai_compatible": OpenAIKompatiblerProvider,
    "anthropic": AnthropicProvider,
    "mock": MockProvider,
}


def provider_registrieren(
    name: str, bauer: Callable[[EndpointConfig], Provider]
) -> None:
    """Registers an additional provider (possible at runtime too)."""
    _REGISTRY[name] = bauer


def bekannte_provider() -> list[str]:
    return sorted(_REGISTRY)


def provider_bauen(endpunkt: EndpointConfig) -> Provider:
    bauer = _REGISTRY.get(endpunkt.provider)
    if bauer is None:
        raise ProviderFehler(
            f"Unbekannter Anbieter '{endpunkt.provider}' für Endpunkt '{endpunkt.id}'. "
            f"Bekannt sind: {', '.join(bekannte_provider())}"
        )
    return bauer(endpunkt)


__all__ = [
    "ChatNachricht",
    "Generierungsanfrage",
    "Provider",
    "ProviderFehler",
    "Stueck",
    "MockProvider",
    "mock_endpunkt",
    "OpenAIKompatiblerProvider",
    "AnthropicProvider",
    "provider_bauen",
    "provider_registrieren",
    "bekannte_provider",
]
