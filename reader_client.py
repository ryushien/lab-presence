"""
カードリーダー端末側のプログラム（Windows / Linux 共通）。
カードをかざすと、DjangoサーバーにIDを送って在室・退室を切り替える。

準備:
    py -m pip install pyscard        （Windows。Linuxは pip install pyscard）
    環境変数を設定してから実行する:
        PowerShell:  $env:PRESENCE_SERVER="http://127.0.0.1:8000"
                     $env:PRESENCE_DEVICE_KEY="管理画面で発行したキー"
                     py reader_client.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.System import readers
from smartcard.util import toHexString

SERVER = os.environ.get("PRESENCE_SERVER", "http://127.0.0.1:8000").rstrip("/")
DEVICE_KEY = os.environ.get("PRESENCE_DEVICE_KEY", "")
GET_ID = [0xFF, 0xCA, 0x00, 0x00, 0x00]


def read_card_id(card) -> str | None:
    conn = card.createConnection()
    try:
        conn.connect()
        data, sw1, sw2 = conn.transmit(GET_ID)
        if (sw1, sw2) == (0x90, 0x00):
            return toHexString(data).replace(" ", "")
        return None
    finally:
        conn.disconnect()


def send_tap(card_id: str) -> dict:
    req = urllib.request.Request(
        f"{SERVER}/api/card/tap",
        data=json.dumps({"card_id": card_id}).encode(),
        headers={"Content-Type": "application/json", "X-Device-Key": DEVICE_KEY},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read())


class TapHandler(CardObserver):
    def update(self, observable, actions):
        added, _removed = actions
        for card in added:
            now = time.strftime("%H:%M:%S")
            try:
                card_id = read_card_id(card)
            except Exception:
                print(f"[{now}] 読み取りに失敗しました。もう一度かざしてください")
                continue
            if not card_id:
                print(f"[{now}] IDを取得できないカードです")
                continue
            try:
                result = send_tap(card_id)
                print(f"[{now}] {result['message']}")
            except urllib.error.HTTPError as e:
                print(f"[{now}] サーバーエラー {e.code}: {e.read().decode(errors='ignore')[:200]}")
            except urllib.error.URLError as e:
                print(f"[{now}] サーバーに接続できません: {e.reason}")


def main():
    if not DEVICE_KEY:
        sys.exit("環境変数 PRESENCE_DEVICE_KEY が設定されていません")
    if not readers():
        sys.exit("カードリーダーが見つかりません")
    print(f"サーバー: {SERVER}")
    print("カードをかざしてください（Ctrl+Cで終了）")

    monitor = CardMonitor()
    handler = TapHandler()
    monitor.addObserver(handler)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.deleteObserver(handler)


if __name__ == "__main__":
    main()
