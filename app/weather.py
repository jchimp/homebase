import httpx


async def geocode_city(city: str) -> tuple[float, float] | None:
    """Return (latitude, longitude) for a city via Open-Meteo geocoding API.

    Accepts plain city names or "City, State/Country" formats. If the full string
    returns no results, retries with just the city portion before the first comma.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        candidates = [city]
        if "," in city:
            candidates.append(city.split(",", 1)[0].strip())

        for name in candidates:
            r = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": name, "count": 1, "language": "en", "format": "json"},
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            if results:
                return results[0]["latitude"], results[0]["longitude"]

    return None
