from fastapi import Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


from app.db.session import sessionmanager
from app.models.photos import Photo, PhotoVariant
from app.utils.image_processing import load_image_bytes, generate_variant, sha256_hash
from app.models.photos import PhotoVariant

class PhotoService:
    def __init__(self, db: AsyncSession = Depends(sessionmanager.get_db)):
        self.db: AsyncSession = db

    async def upload_photo(self, car_id: int, file_bytes: bytes, filename: str, content_type: str):
        # compute hash of original
        file_hash = sha256_hash(file_bytes)

        # PIL image
        img = load_image_bytes(file_bytes)
        fmt = img.format.lower()  # jpeg / png / webp

        photo = Photo(
            car_id=car_id,
            filename=filename,
            content_type=content_type,
            format=fmt,
            hash=file_hash,
            size_bytes=len(file_bytes),
        )

        self.db.add(photo)
        await self.db.flush()  # get photo.id

        # sizes (thumbnail variants)
        for size in (64, 128, 512):
            variant = generate_variant(img, size, fmt)
            pv = PhotoVariant(
                photo_id=photo.id,
                width=variant["width"],
                height=variant["height"],
                data=variant["bytes"],
                size_bytes=variant["size_bytes"],
                content_type=variant["content_type"]
            )
            self.db.add(pv)

        # original image variant
        # store original bytes as a PhotoVariant so the service exposes 4 variants: 64,128,512 and original
        original_width = getattr(img, "width", None)
        original_height = getattr(img, "height", None)
        pv_orig = PhotoVariant(
            photo_id=photo.id,
            width=original_width if original_width is not None else 0,
            height=original_height,
            data=file_bytes,
            size_bytes=len(file_bytes),
            content_type=content_type,
        )
        self.db.add(pv_orig)

        await self.db.commit()
        await self.db.refresh(photo)
        return photo
    
    async def get_photo(self, photo_id: int, size: int | str) -> PhotoVariant:
        """Retrieve a PhotoVariant by numeric width or the keyword 'original'.

        - If `size` is an int: return the variant with matching `width`.
        - If `size` is the string 'original' (case-insensitive): return the largest
          variant by `size_bytes` (assumed to be the original uploaded image).
        """
        # handle 'original' keyword
        if isinstance(size, str):
            if size.lower() == "original":
                result = await self.db.execute(
                    select(PhotoVariant).where(PhotoVariant.photo_id == photo_id).order_by(PhotoVariant.size_bytes.desc()).limit(1)
                )
                variant = result.scalar()
                if not variant:
                    raise HTTPException(404)
                return variant

            # try to coerce numeric strings to int
            try:
                size = int(size)
            except ValueError:
                raise HTTPException(status_code=400, detail="size must be one of 64,128,512 or 'original'")

        result = await self.db.execute(
            select(PhotoVariant).where(PhotoVariant.photo_id == photo_id, PhotoVariant.width == size)
        )
        variant = result.scalar()
        if not variant:
            raise HTTPException(404)
        return variant
