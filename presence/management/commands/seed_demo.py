"""
画面確認用のダミーメンバーを作る（架空の名前）。本番では使わない。

    python manage.py seed_demo          # 追加
    python manage.py seed_demo --clear  # ダミーを削除
"""
import random

from django.core.management.base import BaseCommand

from presence.models import Member, Source, Status

DEMO_TAG = "[demo]"
GRADES = [("教員", 1), ("M2", 7), ("M1", 8), ("B4", 14), ("B3", 14)]
NAMES = ["青木", "石田", "上田", "江口", "大野", "加藤", "木村", "久保", "小松", "斉藤",
         "島田", "鈴木", "高橋", "田中", "千葉", "辻", "中村", "西田", "野口", "橋本",
         "平野", "福田", "本田", "前田", "松井", "三浦", "村上", "森", "山口", "横山",
         "吉田", "渡辺", "秋山", "井上", "内田", "遠藤", "岡本", "川口", "北村", "工藤",
         "後藤", "佐野", "杉山", "関口"]


class Command(BaseCommand):
    help = "画面確認用のダミーメンバーを作る"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true")

    def handle(self, *args, clear=False, **options):
        Member.objects.filter(note=DEMO_TAG).delete()
        if clear:
            self.stdout.write("ダミーを削除しました")
            return
        names = iter(NAMES)
        order = 0
        for grade, n in GRADES:
            for _ in range(n):
                order += 1
                m = Member.objects.create(display_name=next(names), grade=grade,
                                          sort_order=order, note=DEMO_TAG)
                st = random.choices([Status.IN_LAB, Status.ON_CAMPUS, Status.HOME], [4, 2, 5])[0]
                m.apply_status(st, Source.CARD, note=DEMO_TAG)
        self.stdout.write(self.style.SUCCESS(f"{order}人のダミーを作りました"))
