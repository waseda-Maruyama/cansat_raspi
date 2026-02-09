import time
import board
import digitalio
import adafruit_dps310
import os
import sys
from datetime import datetime

# ==========================================
# 設定
# ==========================================
OFFSET_FILE = "/home/yuki/cansat_raspi/pressure/offset.txt"  # system_calibrate.py で作ったファイルを読みます
TARGET_ALTITUDE = 5.0       # この高さ「以下」で光らせる境界線
WAIT_TIME = 0.1             # ループ間隔(秒)

# ログ設定
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)
csv_file = f"{LOG_DIR}/flight_low_active_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# LED設定 (GPIO 21)
LED_PIN = board.D21
led = digitalio.DigitalInOut(LED_PIN)
led.direction = digitalio.Direction.OUTPUT
led.value = True # 起動直後は一旦点灯させておく（安全側）

print("--- フライトシステム (低高度 点灯モード) ---")
print("動作: 高度5m以下でON / 5mより上でOFF")

# 1. 基準値(オフセット)の読み込み
base_altitude = 0.0
if os.path.exists(OFFSET_FILE):
    try:
        with open(OFFSET_FILE, "r") as f:
            content = f.read().strip()
            base_altitude = float(content)
        print(f"✅ 設定ファイルを読み込みました: 基準 = {base_altitude:.2f} m")
    except ValueError:
        print("⚠️ 設定ファイルが破損しています。基準 = 0.0m で開始します。")
else:
    print("⚠️ 設定ファイル(offset.txt)が見つかりません。")
    print("   基準 = 0.0m (海抜0m想定) で開始します。")
    print("   現地で system_calibrate.py を実行してください。")

# 2. センサ初期化
try:
    i2c = board.I2C()
    # test_pressure.py に基づき 0x77 を指定
    dps = adafruit_dps310.DPS310(i2c, address=0x77)
except Exception as e:
    print(f"❌ センサエラー: {e}")
    # エラー時は激しく点滅
    while True:
        led.value = not led.value
        time.sleep(0.1)

# CSVヘッダー
with open(csv_file, 'w') as f:
    f.write("Time,Pressure_hPa,Abs_Alt_m,Rel_Alt_m,LED_Status\n")

print("監視を開始します...")

# 3. メインループ
try:
    while True:
        try:
            press = dps.pressure
            # 現在の絶対高度
            abs_alt = 44330 * (1.0 - (press / 1013.25) ** 0.1903)
            
            # 相対高度 (現在 - 基準)
            rel_alt = abs_alt - base_altitude
            
            # === 判定ロジック変更箇所 ===
            # 「5m より低い」場合に ON
            if rel_alt < TARGET_ALTITUDE:
                led.value = True
                status = "ON (Low Alt)"
            else:
                # 「5m 以上」なら OFF
                led.value = False
                status = "OFF (High Alt)"
            # ==========================
            
            # ログ保存
            timestamp = datetime.now().strftime('%H:%M:%S')
            with open(csv_file, 'a') as f:
                f.write(f"{datetime.now()},{press:.2f},{abs_alt:.2f},{rel_alt:.2f},{status}\n")
            
            # コンソール表示 (状態が見やすいように整形)
            print(f"[{timestamp}] 高度: {rel_alt:6.2f}m | LED: {status}")
            
            time.sleep(WAIT_TIME)
            
        except OSError:
            continue

except KeyboardInterrupt:
    print("\n停止")
    led.value = False
finally:
    led.value = False
