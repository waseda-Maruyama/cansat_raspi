import time
import board
import busio
import digitalio
import adafruit_vl53l1x

# --- 設定 (config.pyより) ---
# XSHUTピン定義
XSHUT_FRONT_PIN = board.D19  # Front (GPIO 19)
XSHUT_REAR_PIN  = board.D26  # Rear (GPIO 26)

# I2Cアドレス定義
ADDR_FRONT = 0x30
ADDR_REAR  = 0x29

print("ToFセンサ (VL53L1X x2) テスト開始")

# 1. I2Cバスの準備
i2c = board.I2C()

# 2. XSHUTピンの初期化 (一旦Lowにしてリセット/停止状態にする)
xshut_front = digitalio.DigitalInOut(XSHUT_FRONT_PIN)
xshut_front.direction = digitalio.Direction.OUTPUT
xshut_front.value = False

xshut_rear = digitalio.DigitalInOut(XSHUT_REAR_PIN)
xshut_rear.direction = digitalio.Direction.OUTPUT
xshut_rear.value = False

time.sleep(0.1)

try:
    # --- 前方センサ (Front) のセットアップ ---
    print("Frontセンサを起動中...")
    xshut_front.value = True  # ONにする
    time.sleep(0.1)
    
    # デフォルトアドレス(0x29)で認識させ、0x30に変更する
    tof_front = adafruit_vl53l1x.VL53L1X(i2c)
    tof_front.set_address(ADDR_FRONT)
    print(f"Frontセンサ設定完了 (Addr: 0x{ADDR_FRONT:02X})")
    
    # --- 後方センサ (Rear) のセットアップ ---
    print("Rearセンサを起動中...")
    xshut_rear.value = True   # ONにする
    time.sleep(0.1)
    
    # デフォルトアドレス(0x29)で認識させる
    tof_rear = adafruit_vl53l1x.VL53L1X(i2c)
    print(f"Rearセンサ設定完了 (Addr: 0x{ADDR_REAR:02X})")

    # 距離計測モード開始 (Short: 〜1.3m, Long: 〜4m)
    tof_front.start_ranging()
    tof_rear.start_ranging()

    print("-" * 40)
    print("計測開始 (Ctrl+Cで終了)")

    while True:
        if tof_front.data_ready and tof_rear.data_ready:
            # 距離を取得 (cm単位に変換)
            dist_f = tof_front.distance
            dist_r = tof_rear.distance
            
            # None (計測不能) のケア
            dist_f_str = f"{dist_f} cm" if dist_f is not None else "---"
            dist_r_str = f"{dist_r} cm" if dist_r is not None else "---"

            print(f"Front: {dist_f_str}  |  Rear: {dist_r_str}")
            
            # 読み取り完了を通知（これをしないと次のデータが来ない）
            tof_front.clear_interrupt()
            tof_rear.clear_interrupt()
            
        time.sleep(0.1)

except Exception as e:
    print(f"エラー発生: {e}")
    print("配線(特にXSHUTピン)を確認してください。")

finally:
    # 終了時はセンサを停止させる推奨マナー
    try:
        tof_front.stop_ranging()
        tof_rear.stop_ranging()
    except:
        pass
