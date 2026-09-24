from hashlib import sha256
from uuid import UUID

import httpx
from pydantic import BaseModel
from sqlalchemy import Connection, text

from cce.core.config import Settings
from cce.modules.contributions.images import MAX_AVATAR_BYTES, VerifiedImage
from cce.modules.contributions.repository import ContributionError, read_one, record_event
from cce.modules.contributions.schemas import Submission
from cce.modules.identity.domain import Actor


class AvatarAsset(BaseModel):
    id: UUID
    submission_id: UUID
    upload_key: UUID
    object_name: str
    sha256: str
    status: str


def read_asset(connection: Connection, asset_id: UUID) -> AvatarAsset:
    row = (
        connection.execute(
            text("select * from public.avatar_assets where id=:id"), {"id": asset_id}
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ContributionError(404, "Avatar bulunamadı")
    return AvatarAsset.model_validate(row)


def reserve_avatar(
    connection: Connection,
    actor: Actor,
    submission_id: UUID,
    expected: int,
    upload_key: UUID,
    image: VerifiedImage,
) -> AvatarAsset:
    connection.execute(
        text("select pg_advisory_xact_lock(hashtextextended(:actor,0))"),
        {"actor": str(actor.user_id)},
    )
    existing = (
        connection.execute(
            text("select * from public.avatar_assets where user_id=:actor and upload_key=:key"),
            {"actor": actor.user_id, "key": upload_key},
        )
        .mappings()
        .one_or_none()
    )
    if existing:
        asset = AvatarAsset.model_validate(existing)
        if asset.submission_id != submission_id or asset.sha256 != image.sha256:
            raise ContributionError(409, "Aynı yükleme kimliği farklı dosyayla kullanılamaz")
        return asset
    item = read_one(connection, submission_id, lock=True)
    if item.status != "DRAFT" or item.version != expected:
        raise ContributionError(409, "Avatar yalnız güncel taslağa eklenebilir; sayfayı yenile")
    counts = connection.execute(
        text(
            "select count(*), count(*) filter (where created_at > now()-interval '1 day') "
            "from public.avatar_assets where user_id=:actor"
        ),
        {"actor": actor.user_id},
    ).one()
    if counts[0] >= 100 or counts[1] >= 20:
        raise ContributionError(429, "Avatar yükleme limiti doldu")
    asset_id = connection.execute(
        text(
            "insert into public.avatar_assets "
            "(submission_id,user_id,upload_key,sha256,byte_size,width,height) "
            "values (:id,:actor,:key,:hash,:size,:width,:height) returning id"
        ),
        {
            "id": item.id,
            "actor": actor.user_id,
            "key": upload_key,
            "hash": image.sha256,
            "size": len(image.content),
            "width": image.width,
            "height": image.height,
        },
    ).scalar_one()
    return read_asset(connection, asset_id)


def attach_avatar(
    connection: Connection, actor: Actor, asset: AvatarAsset, expected: int
) -> Submission:
    item = read_one(connection, asset.submission_id, lock=True)
    # Successful retry returns current state and never replays a draft change.
    if item.avatar_id == asset.id:
        return item
    if item.status != "DRAFT" or item.version != expected:
        raise ContributionError(409, "Başvuru değişmiş; dosya mevcut revizyona uygulanmadı")
    connection.execute(
        text("update public.avatar_assets set status='READY' where id=:id"), {"id": asset.id}
    )
    connection.execute(
        text(
            "update public.character_submissions set avatar_id=:avatar,version=version+1 "
            "where id=:id"
        ),
        {"avatar": asset.id, "id": item.id},
    )
    changed = read_one(connection, item.id)
    record_event(connection, actor, changed, "SAVE", "Avatar attached")
    return changed


class AvatarStorage:
    def __init__(self, config: Settings, authorization: str) -> None:
        if config.supabase_publishable_key is None:
            raise ContributionError(503, "Avatar Storage yapılandırılmadı")
        self.origin = config.storage_url.rstrip("/")
        self.headers = {
            "apikey": config.supabase_publishable_key.get_secret_value(),
            "Authorization": authorization,
        }

    def read(self, asset: AvatarAsset) -> bytes:
        try:
            with httpx.Client(timeout=8, follow_redirects=False) as client:
                with client.stream(
                    "GET",
                    f"{self.origin}/storage/v1/object/authenticated/"
                    f"cce-avatars/{asset.object_name}",
                    headers=self.headers,
                ) as response:
                    if response.status_code != 200:
                        raise ContributionError(503, "Avatar okunamadı; tekrar dene")
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_AVATAR_BYTES:
                            raise ContributionError(502, "Avatar boyutu doğrulanamadı")
            if sha256(content).hexdigest() != asset.sha256:
                raise ContributionError(409, "Storage içeriği doğrulanmış avatarla eşleşmiyor")
            return bytes(content)
        except httpx.HTTPError:
            raise ContributionError(503, "Avatar Storage erişilemiyor") from None

    def store(self, asset: AvatarAsset, image: VerifiedImage) -> None:
        if asset.status != "READY":
            try:
                response = httpx.post(
                    f"{self.origin}/storage/v1/object/cce-avatars/{asset.object_name}",
                    headers={**self.headers, "Content-Type": "image/png", "x-upsert": "false"},
                    content=image.content,
                    timeout=8,
                    follow_redirects=False,
                )
                if response.status_code not in {200, 201, 400, 409}:
                    raise ContributionError(
                        503, "Avatar yüklemesi tamamlanamadı; aynı işlemle tekrar dene"
                    )
            except httpx.HTTPError:
                raise ContributionError(503, "Avatar Storage erişilemiyor") from None
        # Existing-object/retry responses are not success until exact bytes have been verified.
        self.read(asset)
