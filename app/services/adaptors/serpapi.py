import urllib.parse
from json import JSONDecodeError

import aiohttp

from app.services.exceptions import RequestError, ResponseError
from app.services.schemas import ServiceInfo, ServiceNames, ServiceSettings
from app.settings import settings

serpapi_pdf_search_settings = ServiceSettings(name=ServiceNames.serpapi, type="pdf")


async def serpapi_router(service_settings: ServiceSettings, service_info: ServiceInfo):
    match service_settings.type:
        case "google":
            response = await run_search(
                service_info.query, "search.json", query_params="&engine=google"
            )
        case "pdf":
            query = f"{service_info.query} filetype:pdf"
            response = await run_search(
                query, "search.json", query_params="&engine=google&gl=us&hl=en"
            )
        case _:
            raise RequestError(f"Unknown serpapi service type {service_settings.type}")
    return response


async def run_search(query: str, endpoint: str, query_params: str):
    encoded = urllib.parse.quote_plus(query)

    request_url = f"https://serpapi.com/{endpoint}?q={encoded}{query_params}&safe=active&api_key={settings.SERPAPI_KEY}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(request_url) as response:
                json = await response.json()
    except aiohttp.ClientResponseError as e:
        raise RequestError(f"Serpapi request failed with status {e.status}")
    except JSONDecodeError as e:
        raise ResponseError(f"Could not decode Serpapi response as JSON: {e}")

    return json
