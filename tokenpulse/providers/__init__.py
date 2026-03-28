from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider

PROVIDER_MAP = {
    "claude": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}


def get_providers(config: dict) -> dict:
    providers = {}
    for key, cls in PROVIDER_MAP.items():
        provider_cfg = config.get("providers", {}).get(key, {})
        if provider_cfg.get("enabled", False):
            providers[key] = cls(provider_cfg)
    return providers
