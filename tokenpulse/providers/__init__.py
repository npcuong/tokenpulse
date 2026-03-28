from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider

PROVIDER_MAP = {
    "claude": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}


def get_providers(config: dict, storage=None) -> dict:
    providers = {}
    for key, cls in PROVIDER_MAP.items():
        provider_cfg = config.get("providers", {}).get(key, {})
        if not provider_cfg.get("enabled", False):
            continue
        # Providers that need storage access (proxy / manual accumulator)
        if cls in (AnthropicProvider, GeminiProvider):
            providers[key] = cls(provider_cfg, storage=storage)
        else:
            providers[key] = cls(provider_cfg)
    return providers
