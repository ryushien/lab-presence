import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class Status(models.TextChoices):
    IN_LAB = "in_lab", "在室"
    ON_CAMPUS = "on_campus", "学内"
    HOME = "home", "学外・帰宅"


class Source(models.TextChoices):
    CARD = "card", "カード"
    WEB = "web", "Web"
    SYSTEM = "system", "自動"


class Member(models.Model):
    """研究室メンバーと、その現在の状態。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="member",
    )
    display_name = models.CharField("表示名", max_length=50)
    grade = models.CharField("学年", max_length=10, blank=True)
    sort_order = models.PositiveSmallIntegerField("表示順", default=0)
    is_active = models.BooleanField("有効", default=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.HOME)
    note = models.CharField("ひとこと", max_length=100, blank=True)
    status_source = models.CharField(max_length=10, choices=Source.choices, default=Source.WEB)
    status_updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.display_name

    def apply_status(self, status: str, source: str, note: str | None = None) -> bool:
        """状態を変更し、変化があればログを残す。変化したらTrueを返す。"""
        new_note = self.note if note is None else note
        if status == self.status and new_note == self.note:
            return False
        self.status = status
        self.note = new_note
        self.status_source = source
        self.status_updated_at = timezone.now()
        self.save(update_fields=["status", "note", "status_source", "status_updated_at"])
        StatusLog.objects.create(member=self, status=status, source=source, note=new_note)
        return True


class StatusLog(models.Model):
    """状態変化の履歴。滞在時間の集計などに使う。"""

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="logs")
    status = models.CharField(max_length=20, choices=Status.choices)
    source = models.CharField(max_length=10, choices=Source.choices)
    note = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class Card(models.Model):
    """
    ICカード（学生証など）。カードのID（IDm）はそのまま保存せず、
    SECRET_KEY を使った HMAC だけを保存する。
    未登録のカードがかざされると member=None で記録され、管理画面で持ち主を設定する。
    """

    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, null=True, blank=True, related_name="cards",
        verbose_name="持ち主",
    )
    id_hash = models.CharField(max_length=64, unique=True, editable=False)
    label = models.CharField("メモ", max_length=50, blank=True, help_text="例: 学生証")
    first_seen_at = models.DateTimeField("初回読み取り", default=timezone.now)
    last_seen_at = models.DateTimeField("最終読み取り", default=timezone.now)

    def __str__(self):
        owner = self.member.display_name if self.member else "未登録"
        return f"{owner} / …{self.id_hash[-8:]}"

    @staticmethod
    def hash_id(raw_id: str) -> str:
        normalized = raw_id.strip().upper().encode()
        return hmac.new(settings.SECRET_KEY.encode(), normalized, hashlib.sha256).hexdigest()


class Device(models.Model):
    """カードリーダーをつないだPCなどの端末。APIキーはハッシュだけを保存する。"""

    name = models.CharField(max_length=50)
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def issue_key(self) -> str:
        """新しいキーを発行して保存し、生のキーを返す（表示はこの一度だけ）。"""
        raw = secrets.token_urlsafe(32)
        self.key_hash = self.hash_key(raw)
        self.save()
        return raw

    @classmethod
    def find_by_key(cls, raw_key: str):
        return cls.objects.filter(key_hash=cls.hash_key(raw_key), is_active=True).first()
