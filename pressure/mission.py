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
DROP_THRESHOLD = 10.0  # 15m降下で点灯
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

# CSVファイル
csv_file = f"{LOG_DIR}/fall_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# LED
LED_PIN = board.D25
led = digitalio.DigitalInOut(LED_PIN)
led.direction = digitalio.Direction.OUTPUT
led.value = False

print("--- 10m落下検知 + CSVログ ---")

# DPS310
i2c = board.I2C()
dps = adafruit_dps310.DPS310(i2c, address=0x77)

# CSVヘッダー書き込み
with open(csv_file, 'w') as f:
    f.write("Time,Pressure_hPa,Altitude_m,Drop_m,LED_Status\n")
print(f"📊 ログ開始: {csv_file}")

# 地上高度基準 (3回平均)
print("地上高度基準取得...")
base_alt = 0
for i in range(3):
    press = dps.pressure
    alt = 44330 * (1.0 - (press / 1013.25) ** 0.1903)
    base_alt += alt
    print(f"  基準{i+1}: 気圧={press:.1f}hPa, 高度={alt:.1f}m")
    time.sleep(0.5)
base_alt /= 3
print(f"✅ 基準高度: {base_alt:.1f}m")

print(f"待機 {WAIT_TIME}s...")
time.sleep(WAIT_TIME)

print("🚀 落下監視開始 (15mでLED点灯)")

# CSVデータ書き込み関数
def log_data(press, alt, drop, led_on):
    with open(csv_file, 'a') as f:
        f.write(f"{time.time()},{press:.2f},{alt:.2f},{drop:.2f},{int(led_on)}\n")

try:
    while True:
        press = dps.pressure
        alt = 44330 * (1.0 - (press / 1013.25) ** 0.1903)
        drop = base_alt - alt
        
        led_on = led.value
        
        # ログ保存 (全データ)
        log_data(press, alt, drop, led_on)
        
        # リアルタイム表示
        status = "🔴" if led_on else "⚪"
        print(f"{status} 気圧:{press:.1f}hPa 高:{alt:.1f}m 降下:{drop:.1f}m", end='\r')
        
        # 落下判定
        if drop >= DROP_THRESHOLD and not led_on:
            print(f"\n🚀 15m落下検知! (降下{drop:.1f}m)")
            led.value = True
            log_data(press, alt, drop, True)  # トリガー記録
        
        time.sleep(0.1)

except KeyboardInterrupt:
    led.value = False
    print(f"\n\n⏹️ 終了 | ログ: {csv_file}")
