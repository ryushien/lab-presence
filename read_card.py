"""
RC-S300 で学生証などのICカードのID（IDm / UID）を読み取るテスト。
使い方:  python read_card.py   → カードをかざす。終了は Ctrl+C
"""
import hashlib
import time

from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.System import readers
from smartcard.util import toHexString

# PC/SC 共通コマンド: カードのID（FeliCaならIDm、MIFAREならUID）を取得する
GET_ID = [0xFF, 0xCA, 0x00, 0x00, 0x00]


def card_id(card) -> str | None:
    conn = card.createConnection()
    try:
        conn.connect()
        data, sw1, sw2 = conn.transmit(GET_ID)
        if (sw1, sw2) == (0x90, 0x00):
            return toHexString(data).replace(" ", "")
        print(f"  読み取り失敗 (status {sw1:02X} {sw2:02X})")
        return None
    finally:
        conn.disconnect()


class Printer(CardObserver):
    def update(self, observable, actions):
        added, removed = actions
        for card in added:
            try:
                cid = card_id(card)
            except Exception as e:  # かざすのが速すぎた場合など
                print(f"  エラー: {e}")
                continue
            if cid:
                digest = hashlib.sha256(cid.encode()).hexdigest()[:16]
                print(f"[{time.strftime('%H:%M:%S')}] ID={cid}  (ハッシュ: {digest}...)")
        for _ in removed:
            print("  カードが離れました")


def main():
    rs = readers()
    if not rs:
        print("リーダーが見つかりません。USB接続とドライバーを確認してください。")
        return
    print("見つかったリーダー:", *rs, sep="\n  ")
    print("カードをかざしてください（Ctrl+Cで終了）")

    monitor = CardMonitor()
    observer = Printer()
    monitor.addObserver(observer)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.deleteObserver(observer)


if __name__ == "__main__":
    main()
