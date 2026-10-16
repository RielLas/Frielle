"""
raziel_core/ai_engine.py
Gemini Flash-Lite multi-key resilient AI synthesis engine for Project Raziel.
Mirrors the high-throughput, token-efficient architecture of Ciel.
"""

import re
import time
import asyncio
import logging
from typing import List, Optional, Any, Dict
from config import DEFAULT_MODEL, FALLBACK_MODELS, GEMINI_API_KEYS

logger = logging.getLogger("Raziel.AI")

_KEY_COOLDOWNS: Dict[str, float] = {}
_CLIENT_CACHE: Dict[str, Any] = {}


def clean_discord_output(text: str) -> str:
    """Strips thinking blocks, stage directions/asterisks roleplay, and quotes while preserving markdown formatting."""
    if not text:
        return ""
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
    text = re.sub(r"```thinking.*?```", "", text, flags=re.DOTALL)
    # Strip parenthesized stage directions like *(smiles)* or *(chuckles)*
    text = re.sub(r"\*\([^)]+\)\*", "", text)
    # Strip unparenthesized roleplay actions (e.g. *smiles*, *laughs*, *sighs*) while preserving single italicized words
    roleplay_verbs = r"(?:smiles|chuckles|laughs|sighs|grins|winks|nods|pauses|shrugs|waves|rolls eyes|leans in)"
    text = re.sub(rf"^\*{roleplay_verbs}[^*]*\*\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(rf"\s*\*{roleplay_verbs}[^*]*\*$", "", text, flags=re.IGNORECASE)
    text = text.strip()
    # Strip surrounding quotation marks if dialogue is quoted
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip formal trailing period on casual single-line messages to sound like authentic Discord texting
    if "\n" not in text and text.endswith(".") and not text.endswith(".."):
        text = text[:-1].strip()
    return text.strip()


def is_rate_limited(err: Any) -> bool:
    """Checks if an error signals a quota exhaustion or rate limit (429)."""
    if not err:
        return False
    msg = str(err).lower()
    return any(
        token in msg
        for token in ("429", "resource_exhausted", "quota", "rate limit", "too many requests", "tokens per day")
    )


class GeminiEngine:
    """
    Resilient generation client cycling through Gemini Flash-Lite models
    and available API keys with exponential backoff.
    """

    def __init__(
        self,
        api_keys: Optional[List[str]] = None,
        default_model: str = DEFAULT_MODEL,
        fallback_models: Optional[List[str]] = None
    ):
        self.api_keys = api_keys or GEMINI_API_KEYS
        self.model = default_model
        self.fallback_models = fallback_models or FALLBACK_MODELS
        # Pre-warm client cache to prevent Gateway heartbeat lag on first call
        for k in self.api_keys:
            self._get_client(k)

    def _get_active_keys(self) -> List[str]:
        now = time.time()
        fresh = [k for k in self.api_keys if _KEY_COOLDOWNS.get(k, 0) <= now]
        cooling = [k for k in self.api_keys if _KEY_COOLDOWNS.get(k, 0) > now]
        return fresh + cooling

    def _get_client(self, api_key: str) -> Optional[Any]:
        if not api_key:
            return None
        if api_key not in _CLIENT_CACHE:
            try:
                from google import genai
                _CLIENT_CACHE[api_key] = genai.Client(api_key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google GenAI Client: {e}")
                return None
        return _CLIENT_CACHE.get(api_key)

    async def generate(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.8
    ) -> str:
        """
        Generates content using candidate Gemini Flash-Lite models.
        Automatically cycles keys and fallbacks if rate limits occur.
        """
        keys = self._get_active_keys()
        if not keys:
            return "looks like my connection's momentarily unplugged, give me a second."

        candidate_models = [self.model] + [m for m in self.fallback_models if m != self.model]

        for key in keys:
            client = self._get_client(key)
            if not client:
                continue

            for model_name in candidate_models:
                try:
                    from google.genai import types  # type: ignore
                    config = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=temperature,
                    )
                except Exception:
                    config = {"system_instruction": system_instruction, "temperature": temperature}

                try:
                    async def _call():
                        if hasattr(client, "aio") and hasattr(client.aio, "models"):
                            call_res = client.aio.models.generate_content(
                                model=model_name,
                                contents=[prompt],
                                config=config
                            )
                            if hasattr(call_res, "__await__"):
                                return await call_res
                            return call_res
                        elif hasattr(client, "models"):
                            # Protect Discord Gateway heartbeat by offloading sync call to thread pool
                            loop = asyncio.get_running_loop()
                            return await loop.run_in_executor(
                                None,
                                lambda: client.models.generate_content(
                                    model=model_name,
                                    contents=[prompt],
                                    config=config
                                )
                            )
                        else:
                            loop = asyncio.get_running_loop()
                            return await loop.run_in_executor(
                                None,
                                lambda: client.generate_content(
                                    model=model_name,
                                    contents=[prompt],
                                    config=config
                                )
                            )

                    res = await asyncio.wait_for(_call(), timeout=9.0)
                    try:
                        raw_text = getattr(res, "text", "") or ""
                    except Exception:
                        raw_text = ""

                    cleaned = clean_discord_output(raw_text)
                    if cleaned:
                        return cleaned

                except asyncio.TimeoutError:
                    logger.warning(f"Model '{model_name}' timed out after 9.0s. Trying next fallback.")
                    continue
                except Exception as err:
                    if is_rate_limited(err):
                        logger.warning(f"Key ending in ...{key[-4:]} hit rate limit on '{model_name}'. Cooling down 60s.")
                        _KEY_COOLDOWNS[key] = time.time() + 60.0
                        break  # Try next key
                    else:
                        logger.warning(f"Model '{model_name}' failed with error: {err}. Trying next fallback.")
                        continue

        return "my connection lagged for a sec, my bad. what was that?"
