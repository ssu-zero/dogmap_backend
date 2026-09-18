"""S3 프로필 이미지 업로드용 presigned URL 발급.

프론트가 이 presigned URL로 S3에 직접 PUT 업로드하고, 반환된 image_url을
POST /dogs 또는 PATCH /dogs/me 요청의 image_url 필드에 그대로 넣는다.
버킷은 퍼블릭 읽기로 설정되어 있어야 image_url이 별도 서명 없이 바로 접근 가능하다.
"""

import uuid
from dataclasses import dataclass

import boto3

from app.core.config import settings

_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

_s3_client = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    # region_name만 넘기면 boto3가 리전 없는 글로벌 엔드포인트(s3.amazonaws.com)로 서명해서
    # PUT 요청이 307 리다이렉트를 받고 그대로 실패한다. endpoint_url을 명시해 리전 엔드포인트로
    # 직접 서명하게 한다.
    endpoint_url=f"https://s3.{settings.AWS_REGION}.amazonaws.com",
)


@dataclass
class PresignedUpload:
    upload_url: str
    image_url: str


def create_presigned_upload(*, folder: str, owner_id: int, file_extension: str) -> PresignedUpload:
    """folder(예: "signup", "profile")와 owner_id(kakao_id 또는 dog_id)별로 겹치지 않는
    키를 만들어 5분짜리 PUT presigned URL을 발급한다.
    """
    extension = file_extension.lower().lstrip(".")
    if extension not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"지원하지 않는 확장자입니다: {file_extension}")

    key = f"dogs/{folder}/{owner_id}/{uuid.uuid4()}.{extension}"

    upload_url = _s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
        ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS,
    )
    image_url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    return PresignedUpload(upload_url=upload_url, image_url=image_url)
