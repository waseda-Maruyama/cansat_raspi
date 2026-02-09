import time
import board
import busio
import adafruit_dps310

print("気圧センサ (DPS310) I2C接続テスト")

# I2Cバスの準備 (SDA=GPIO2, SCL=GPIO3)
try:
    i2c = board.I2C()
except Exception as e:
    print(f"❌ I2C初期化エラー: {e}")
    print("ヒント: 'sudo raspi-config' で I2C を有効にしましたか？")
    exit()

# DPS310の初期化
dps = None

# まずアドレス 0x77 (デフォルト) を試す
try:
    dps = adafruit_dps310.DPS310(i2c, address=0x77)
    print("✅ 接続成功 (Address: 0x77)")
except:
    # だめなら 0x76 を試す
    try:
        dps = adafruit_dps310.DPS310(i2c, address=0x76)
        print("✅ 接続成功 (Address: 0x76)")
    except Exception as e:
        print(f"❌ 接続失敗: {e}")
        print("配線を確認してください:")
        print("  - VCC -> 3.3V")
        print("  - GND -> GND")
        print("  - SCL -> GPIO 3 (Pin 5)")
        print("  - SDA -> GPIO 2 (Pin 3)")
        exit()

print("-" * 40)
print("計測開始 (Ctrl+Cで終了)")

# 計測ループ
while True:
    try:
        pressure = dps.pressure
        temp = dps.temperature
        
        # 簡易高度計算 (海面気圧を1013.25hPaと仮定)
        altitude = 44330 * (1.0 - (pressure / 1013.25) ** 0.1903)
        
        print(f"気圧: {pressure:.2f} hPa | 温度: {temp:.2f} C | 推定高度: {altitude:.2f} m")
        
    except Exception as e:
        print(f"読み取りエラー: {e}")
    
    time.sleep(1)
