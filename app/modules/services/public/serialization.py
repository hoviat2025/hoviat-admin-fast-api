"""Public read boundary. Never reuse the admin aggregate serializer here."""

from app.models.service import Service
from app.modules.services.media_urls import public_cover_image_url
from app.modules.services.schemas.category_responses import CategorySummaryResponse
from app.modules.services.schemas.public_service_responses import (
    PublicServiceCategoryResponse,
    PublicServiceContactResponse,
    PublicServiceResponse,
)


def to_public_service(service: Service) -> PublicServiceResponse:
    # show_owner alone cannot authorize revealing a personal account. Owner
    # associations stay private until an owner view applies account privacy too.
    return PublicServiceResponse(
        id=service.id,
        name=service.name,
        description=service.description,
        cover_image_url=public_cover_image_url(getattr(service, "cover_image_path", None)),
        persian_owned=service.persian_owned,
        persian_provider=service.persian_provider,
        persian_language=service.persian_language,
        persian_service=service.persian_service,
        address=service.address,
        postal_code=service.postal_code,
        city=service.city,
        state=service.state,
        country_code=service.country_code,
        latitude=service.latitude,
        longitude=service.longitude,
        created_at=service.created_at,
        updated_at=service.updated_at,
        contacts=[
            PublicServiceContactResponse.model_validate(contact)
            for contact in service.contacts
            if contact.is_visible is True
        ],
        categories=[
            PublicServiceCategoryResponse(
                category_id=link.category_id,
                is_primary=link.is_primary,
                category=CategorySummaryResponse.model_validate(link.category),
            )
            for link in service.category_links
            if link.category is not None and link.category.is_active is True
        ],
    )
