import urllib.parse
from json import JSONDecodeError

import aiohttp

from app.services.exceptions import RequestError, ResponseError
from app.services.schemas import ServiceInfo, ServiceNames, ServiceSettings
from app.settings import settings

wiki_search_settings = ServiceSettings(name=ServiceNames.custom, type="wiki")


async def custom_search_router(service_settings: ServiceSettings, service_info: ServiceInfo):
    match service_settings.type:
        case "wiki":
            response = await run_search(
                service_info.query, "search", extract_field="match"
            )
        case _:
            raise RequestError(f"Unknown external search service type {service_settings.type}")
    return response


async def run_search(query: str, endpoint: str, extract_field: str = None):
    if not settings.CUSTOM_SEARCH_SERVER:
        raise RequestError(f"Custom search server not configured")

    params = {"query": query}
    auth = aiohttp.BasicAuth(settings.CUSTOM_SEARCH_USER, settings.CUSTOM_SEARCH_PASSWORD)

    request_url = f"{settings.CUSTOM_SEARCH_SERVER}/{endpoint}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(request_url, params=params, auth=auth) as response:
                json = await response.json()
    except aiohttp.ClientResponseError as e:
        raise RequestError(f"Custom search request failed with status {e.status}")
    except JSONDecodeError as e:
        raise ResponseError(f"Could not decode custom search response as JSON: {e}")

    return {"text": json[extract_field]}
