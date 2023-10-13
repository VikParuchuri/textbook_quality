import hashlib

from app.db.session import get_session
from app.services.adaptors.custom_search import custom_search_router
from app.services.adaptors.serpapi import serpapi_router
from app.services.adaptors.serply import serply_router
from app.services.dependencies import get_service_response_model
from app.services.models import ServiceResponse
from app.services.schemas import ServiceInfo, ServiceNames, ServiceSettings


async def get_service_response(
    service_settings: ServiceSettings,
    service_info: ServiceInfo,
    cache=True,
) -> dict:
    hash = hashlib.sha512()
    # Turn dict into list, sort keys, then hash.  This ensures consistent order.
    service_info_str = str(sorted(service_info.dict().items())).encode("utf-8")
    hash.update(service_info_str)
    hex = hash.hexdigest()

    if cache:
        # Break if we've already run this query
        service_model = await get_service_response_model(service_settings.name, hex)

        if service_model is not None:
            return service_model.response

    match service_settings.name:
        case ServiceNames.serply:
            response = await serply_router(service_settings, service_info)
        case ServiceNames.serpapi:
            response = await serpapi_router(service_settings, service_info)
        case ServiceNames.custom:
            response = await custom_search_router(service_settings, service_info)
        case _:
            raise NotImplementedError("This Service type is not currently supported.")

    if cache:
        async with get_session() as db:
            # Save the response to the DB
            service_model = ServiceResponse(
                hash=hex,
                request=service_info.dict(),
                response=response,
                name=service_settings.name,
            )
            db.add(service_model)
            await db.commit()

    return response
