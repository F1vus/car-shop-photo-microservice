from fastapi import APIRouter, UploadFile, Depends,Response, File

from app.services.photo_service import PhotoService
from app.models.photos import PhotoVariant


router = APIRouter()

@router.post("/cars/{car_id}/photos")
async def upload_car_photos(
    car_id: int,
    files: list[UploadFile] = File(...),
    service: PhotoService = Depends(PhotoService)
):
    result = []

    for file in files:
        data = await file.read()

        photo = await service.upload_photo(
            car_id=car_id,
            file_bytes=data,
            filename=file.filename,
            content_type=file.content_type,
        )

        result.append({
            "id": photo.id,
            "url": f"/photos/{photo.id}/"
        })

    return result


@router.get("/photos/{photo_id}/{size}")
async def get_photo_variant(
    photo_id: int,
    size: str,
    service: "PhotoService" = Depends(PhotoService)
):
    # Accept numeric sizes ("64", "128", "512") or the literal "original"
    parsed_size: int | str
    try:
        parsed_size = int(size)
    except ValueError:
        parsed_size = size.lower()

    photo_variant: PhotoVariant = await service.get_photo(photo_id, parsed_size)
    return Response(
        content=photo_variant.data,
        media_type=photo_variant.content_type,
        headers={"Cache-Control": "public, max-age=31536000"}
    )
