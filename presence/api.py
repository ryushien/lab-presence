from datetime import datetime, timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from ninja.security import APIKeyHeader, django_auth

from .models import Card, Device, Member, Source, Status

api = NinjaAPI(title="Lab Presence API")

# 同じカードを続けて読んだときに無視する時間（二度読み・連打対策）
TAP_COOLDOWN = timedelta(seconds=5)


# ---------- 認証 ----------

class DeviceAuth(APIKeyHeader):
    """カードリーダー端末からのリクエストは X-Device-Key ヘッダーで認証する。"""

    param_name = "X-Device-Key"

    def authenticate(self, request, key):
        device = Device.find_by_key(key) if key else None
        if device:
            Device.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
        return device


device_auth = DeviceAuth()


# ---------- スキーマ ----------

class MemberOut(Schema):
    id: int
    display_name: str
    grade: str
    status: str
    status_label: str
    note: str
    status_source: str
    status_updated_at: datetime


class StatusIn(Schema):
    status: Status
    note: str | None = None


class TapIn(Schema):
    card_id: str  # リーダーが読んだIDm / UID（16進文字列）


class TapOut(Schema):
    result: str  # "entered" / "left" / "ignored" / "unregistered"
    message: str
    member: MemberOut | None = None


class LogOut(Schema):
    status: str
    source: str
    note: str
    created_at: datetime


def to_out(m: Member) -> dict:
    return {
        "id": m.id,
        "display_name": m.display_name,
        "grade": m.grade,
        "status": m.status,
        "status_label": m.get_status_display(),
        "note": m.note,
        "status_source": m.status_source,
        "status_updated_at": m.status_updated_at,
    }


# ---------- エンドポイント ----------

@api.get("/members", response=list[MemberOut], auth=[django_auth, device_auth])
def list_members(request):
    """全員の状態一覧。Web画面とドア前の表示で使う。"""
    return [to_out(m) for m in Member.objects.filter(is_active=True)]


@api.put("/members/me/status", response=MemberOut, auth=django_auth)
def update_my_status(request, payload: StatusIn):
    """ログイン中の本人が、自分の状態をWebから変更する。"""
    member = getattr(request.user, "member", None)
    if member is None:
        raise HttpError(404, "このユーザーはメンバーに登録されていません")
    member.apply_status(payload.status, Source.WEB, payload.note)
    return to_out(member)


@api.get("/members/{member_id}/logs", response=list[LogOut], auth=django_auth)
def member_logs(request, member_id: int, limit: int = 50):
    member = get_object_or_404(Member, pk=member_id)
    return list(member.logs.all()[: min(limit, 200)])


@api.post("/card/tap", response=TapOut, auth=device_auth)
def card_tap(request, payload: TapIn):
    """
    カードがかざされたときに呼ぶ。
    - 在室中なら「学外・帰宅」に、それ以外なら「在室」に切り替える。
    - 未登録のカードは記録だけして、管理画面で持ち主を設定してもらう。
    """
    card_id = payload.card_id.strip()
    if not card_id or len(card_id) > 64:
        raise HttpError(400, "card_id が不正です")

    now = timezone.now()
    id_hash = Card.hash_id(card_id)

    with transaction.atomic():
        card, created = Card.objects.select_for_update().get_or_create(
            id_hash=id_hash, defaults={"first_seen_at": now, "last_seen_at": now}
        )
        previous_seen = card.last_seen_at
        card.last_seen_at = now
        card.save(update_fields=["last_seen_at"])

        member = card.member
        if member is None or not member.is_active:
            return {"result": "unregistered",
                    "message": "未登録のカードです。管理者に登録を依頼してください"}

        member = Member.objects.select_for_update().get(pk=member.pk)
        if not created and now - previous_seen < TAP_COOLDOWN:
            return {"result": "ignored", "message": "読み取り済みです", "member": to_out(member)}

        if member.status == Status.IN_LAB:
            member.apply_status(Status.HOME, Source.CARD, note="")
            return {"result": "left", "message": f"{member.display_name}さん 退室",
                    "member": to_out(member)}

        member.apply_status(Status.IN_LAB, Source.CARD, note="")
        return {"result": "entered", "message": f"{member.display_name}さん 入室",
                "member": to_out(member)}


class ActivityOut(Schema):
    member_name: str
    status: str
    status_label: str
    source: str
    created_at: datetime


@api.get("/activity", response=list[ActivityOut], auth=[django_auth, device_auth])
def recent_activity(request, limit: int = 8):
    """最近の入退室。ドア前の表示で使う。"""
    from .models import StatusLog

    logs = StatusLog.objects.select_related("member").filter(member__is_active=True)[: min(limit, 30)]
    return [
        {
            "member_name": log.member.display_name,
            "status": log.status,
            "status_label": log.get_status_display(),
            "source": log.source,
            "created_at": log.created_at,
        }
        for log in logs
    ]
