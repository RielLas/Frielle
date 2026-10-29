"""
cogs/_ai_search.py
Web search intent heuristics, query distillation, and DuckDuckGo search
for Frielle's live fact-grounding pipeline.
"""

import asyncio
import logging
import re
import warnings
from typing import List, Optional

_AsyncDDGS = None
_DDGS = None
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from ddgs import AsyncDDGS as _AsyncDDGS, DDGS as _DDGS
except ImportError:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from duckduckgo_search import AsyncDDGS as _AsyncDDGS, DDGS as _DDGS
    except ImportError:
        pass

_CONVERSATIONAL_MARKERS = (
    "how are you", "how's it going", "hows it going", "how r u", "how are u",
    "what's up", "whats up", "what are you doing", "how do you feel",
    "how's your day", "hows your day", "how was your day", "how are things",
    "you ok", "you okay", "u ok", "wyd", "wassup", "sup",
)

_FACT_PHRASES = (
    "capital of", "population of", "meaning of", "definition of",
    "difference between", "who is", "who's", "what is", "what's",
    "when is", "when's", "where is", "where's", "why is", "why's",
    "tell me about", "explain", "define", "latest news", "news about",
    "how to", "what happened", "is it", "are there", "how does", "how do",
)

_WH_OPENERS = ("what", "who", "when", "where", "why", "how", "which")


def _strip_leading_mention(low: str) -> str:
    return re.sub(r"^@\S+\s*", "", low).strip()


_PERSONAL_QUESTION_PATTERNS = (
    r"\b(?:so\s+)?you(?:['’]d|['’]re|['’]ll|['’]ve)?\b",
    r"\b(?:are|do|did|would|could|will|can|have)\s+you\b",
    r"\bwhy\s+(?:do|are|would|did)\s+you\b",
    r"\bwhat\s+do\s+you\s+(?:think|feel|like|want)\b",
    r"\b(?:with|about|to|for)\s+me\b",
    r"\bchatting\s+with\s+me\b",
    r"\bstay\s+here\b",
    r"\bremember\s+me\b",
)


def looks_fact_based(text: str) -> bool:
    low = (text or "").lower().strip()
    low = _strip_leading_mention(low)
    if len(low) < 8 or len(low) > 300:
        return False
    if any(re.search(rf"\b{re.escape(marker)}\b", low) for marker in _CONVERSATIONAL_MARKERS):
        return False
    if any(re.search(pat, low) for pat in _PERSONAL_QUESTION_PATTERNS) and not any(f in low for f in ("capital of", "population of", "meaning of", "definition of", "latest news", "news about")):
        return False
    first_word = low.split()[0].rstrip("?!.,;:") if low.split() else ""
    if low.endswith("?") or first_word in _WH_OPENERS:
        return True
    return any(phrase in low for phrase in _FACT_PHRASES)


_SEARCH_COMMAND_WORDS = ("search", "google", "lookup")
_SEARCH_COMMAND_PHRASES = ("look up", "search for", "search up", "google search", "google up")
_QUERY_FILLER_PREFIXES = (
    "what is", "what's", "whats", "who is", "who's", "whos", "which is",
    "tell me about", "tell me", "explain", "define", "can you tell me",
    "can u tell me", "do you know", "do u know", "i want to know",
    "i wanna know", "wanna know", "about", "the",
)


def is_explicit_search(text: str) -> bool:
    low = (text or "").lower().strip()
    if not low:
        return False
    low = _strip_leading_mention(low)
    if not low:
        return False
    first = low.split()[0].rstrip("?!.,;:")
    if first in _SEARCH_COMMAND_WORDS:
        return True
    return low.startswith(_SEARCH_COMMAND_PHRASES)


def distill_query(text: str) -> str:
    low = (text or "").strip().lower()
    low = _strip_leading_mention(low)
    prefixes = _SEARCH_COMMAND_PHRASES + _SEARCH_COMMAND_WORDS + _QUERY_FILLER_PREFIXES
    while True:
        for prefix in prefixes:
            if low == prefix or low.startswith(prefix + " "):
                low = low[len(prefix):].strip()
                break
        else:
            break
    low = re.sub(r"[?.!,;:\s]+$", "", low).strip()
    return low[:200]


_WEB_SNIPPET_JUNK_REGEX = re.compile(
    r'(?i)\b(?:we use cookies|accept (?:all )?cookies|cookie policy|privacy policy|'
    r'all rights reserved|terms of (?:service|use)|subscribe to (?:our )?newsletter|'
    r'sign up for free|enable javascript|skip to main content|click here to|'
    r'advertisement|sponsored content)\b.*?[.!?\n]',
    re.DOTALL
)


def clean_web_search_snippet(text: str) -> str:
    if not text:
        return ""
    cleaned = _WEB_SNIPPET_JUNK_REGEX.sub(" ", text)
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    return cleaned.strip()


WEB_SEARCH_SUMMARY_MAX_CHARS = 700


async def _ddg_search(query: str, max_results: int = 3) -> list:
    if _AsyncDDGS is not None:
        try:
            return await _AsyncDDGS().text(query, max_results=max_results)
        except Exception:
            pass
    if _DDGS is not None:
        def _fetch_sync():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return list(_DDGS().text(query, max_results=max_results))
        return await asyncio.to_thread(_fetch_sync)
    return []


async def web_search_summary(query: str) -> str:
    try:
        results = await _ddg_search(query, max_results=3)
        if not results:
            return ""

        lines = []
        for r in results:
            title = clean_web_search_snippet(r.get("title", ""))
            body = clean_web_search_snippet(r.get("body", ""))
            if body:
                lines.append(f"{title}: {body}")

        text = "\n".join(lines)
        return text[:WEB_SEARCH_SUMMARY_MAX_CHARS] if text else ""
    except Exception as search_err:
        logging.warning(f"Web search grounding failed: {search_err}")
        return ""
