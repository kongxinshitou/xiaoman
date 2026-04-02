from typing import List, Dict, Any


async def _get_search_config() -> Dict[str, str]:
    """Read search provider config from DB system_settings."""
    try:
        from app.database import AsyncSessionLocal
        from app.models.system_setting import SystemSetting
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(SystemSetting).where(
                SystemSetting.key.in_(["search_provider", "search_api_key"])
            ))
            settings = {s.key: s.value for s in result.scalars().all()}
            return settings
    except Exception:
        return {}


async def _search_tavily(query: str, api_key: str, max_results: int) -> List[Dict[str, Any]]:
    """Search using Tavily API."""
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in data.get("results", [])
            if r.get("title") or r.get("content")
        ]


async def _search_duckduckgo(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Search using DuckDuckGo (free, may be blocked in some regions)."""
    from duckduckgo_search import DDGS
    import asyncio

    def _sync_search():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    results = await asyncio.get_event_loop().run_in_executor(None, _sync_search)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
        }
        for r in results
        if r.get("title") or r.get("body")
    ]


async def search_web(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search the web. Tries Tavily first if configured, falls back to DuckDuckGo.
    Returns list of {title, url, snippet}.
    """
    try:
        config = await _get_search_config()
        provider = config.get("search_provider", "duckduckgo")
        api_key = config.get("search_api_key", "")

        if provider == "tavily" and api_key:
            return await _search_tavily(query, api_key, max_results)
        else:
            return await _search_duckduckgo(query, max_results)
    except ImportError:
        return []
    except Exception:
        return []
