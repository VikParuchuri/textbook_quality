import urllib.parse
from json import JSONDecodeError

import aiohttp

from app.services.exceptions import RequestError, ResponseError
from app.services.schemas import ServiceInfo, ServiceNames, ServiceSettings
from app.settings import settings

serply_pdf_search_settings = ServiceSettings(name=ServiceNames.serply, type="pdf")


async def serply_router(service_settings: ServiceSettings, service_info: ServiceInfo):
    match service_settings.type:
        case "google":
            response = await run_search(service_info.query, "search")
        case "pdf":
            response = await run_search(
                service_info.query, "search", "&as_filetype=pdf"
            )
        case _:
            raise RequestError(f"Unknown Serply service type {service_settings.type}")
    return response


async def run_search(query: str, endpoint: str, query_params: str = ""):
    encoded = urllib.parse.quote_plus(query)

    request_url = f"https://api.serply.io/v1/{endpoint}/q={encoded}&num=10&safe=active{query_params}"
    headers = {"X-Api-Key": settings.SERPLY_KEY, "X-Proxy-Location": "US"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(request_url) as response:
                json = await response.json()
    except (aiohttp.ClientResponseError, aiohttp.ClientOSError) as e:
        raise RequestError(f"Request failed with status {e.status}")
    except JSONDecodeError as e:
        raise ResponseError(f"Could not decode response as JSON: {e}")

    if json["total"] == 0:
        raise ResponseError("Nothing found")

    return json
