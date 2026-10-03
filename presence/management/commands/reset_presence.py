"""
在室・学内のままの人を「学外・帰宅」に戻す（退室時のかざし忘れ対策）。
深夜に1日1回、cron（Linux）やタスクスケジューラ（Windows）で実行する。

    python manage.py reset_presence
"""
from django.core.management.base import BaseCommand

from presence.models import Member, Source, Status


class Command(BaseCommand):
    help = "在室・学内のメンバーを「学外・帰宅」にリセットする"

    def handle(self, *args, **options):
        count = 0
        for m in Member.objects.filter(is_active=True).exclude(status=Status.HOME):
            if m.apply_status(Status.HOME, Source.SYSTEM, note=""):
                count += 1
        self.stdout.write(self.style.SUCCESS(f"{count}人をリセットしました"))
