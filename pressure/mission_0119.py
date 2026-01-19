import time
import board
import digitalio
import adafruit_dps310
import os
from datetime import datetime

# ==========================================
# 設定
# ==========================================
WAIT_TIME = 120        # 待機時間 (秒)
DROP_THRESHOLD = 10.0  # 10m降下で点灯
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

csv_file = f"{LOG_DIR}/fall_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# LED (D25 = GPIO25)
LED_PIN = board.D25
led = digitalio.DigitalInOut(LED_PIN)
led.direction = digitalio.Direction.OUTPUT
led.value = False

print("--- 10m落下検知 + CSVログ (DPS310@0x77) ---")

# DPS310 (エラーハンドリング追加)
try:
    i2c = board.I2C()  # i2c-1
    dps = adafruit_dps310.DPS310(i2c, address=0x77)
    print("✅ DPS310 初期化成功")
except Exception as e:
    print(f"❌ DPS310エラー: {e}")
    print("i2cdetect -y 1 で確認後、配線/電源再チェック")
    exit(1)

# CSVヘッダー
with open(csv_file, 'w') as f:
    f.write("Time,Pressure_hPa,Altitude_m,Drop_m,LED_Status\n")
print(f"📊 ログ開始: {csv_file}")

# 地上高度基準 (5回平均、安定化)
print("地上高度基準取得中 (5回平均)...")
base_alt = 0
pressures = []
for i in range(5):
    try:
        press = dps.pressure
        alt = 44330 * (1.0 - (press / 1013.25) ** 0.1903)  # ISA高度換算
        pressures.append(press)
        base_alt += alt
        print(f"  基準{i+1}: 気圧={press:.1f}hPa, 高度={alt:.1f}m")
        time.sleep(1.0)  # センサー安定
    except Exception as e:
        print(f"読み取りエラー: {e}")
        time.sleep(1)

base_alt /= len(pressures)
base_press = sum(pressures) / len(pressures)
print(f"📍 基準値: 気圧={base_press:.1f}hPa, 高度={base_alt:.1f}m")

# メインループ
prev_alt = base_alt
print(f"監視開始 (降下{DROP_THRESHOLD}mでLED点灯、{WAIT_TIME}s間隔)")
while True:
    try:
        press = dps.pressure
        alt = 44330 * (1.0 - (press / 1013.25) ** 0.1903)
        drop = base_alt - alt  # 正の降下値
        
        # LED制御
        if drop >= DROP_THRESHOLD:
            led.value = True
            status = "ON"
            print(f"🚨 落下検知! {drop:.1f}m → LED ON")
        else:
            led.value = False
            status = "OFF"
        
        # CSVログ
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(csv_file, 'a') as f:
            f.write(f"{timestamp},{press:.1f},{alt:.1f},{drop:.1f},{status}\n")
        
        print(f"[{timestamp}] 気圧={press:.1f}hPa, 高度={alt:.1f}m, 降下={drop:.1f}m, LED={status}")
        time.sleep(WAIT_TIME)
        
    except KeyboardInterrupt:
        print("\n⏹️ 停止")
        break
    except Exception as e:
        print(f"ループエラー: {e}")
        time.sleep(5)

led.value = False
print("終了")
