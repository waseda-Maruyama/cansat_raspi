import time
import board
import busio
import digitalio
import adafruit_vl53l1x

# --- 設定エリア ---
# XSHUTピンのGPIO番号 (実際の配線に合わせて変更してください)
# 例: Front=17, Rear=27 など
XSHUT_FRONT_PIN = board.D27
XSHUT_REAR_PIN  = board.D17

# I2Cアドレスの設定 (Frontを変更し、Rearはデフォルトのままにする)
ADDR_DEFAULT = 0x29
ADDR_FRONT   = 0x30  # 変更後のアドレス
ADDR_REAR    = 0x29  # デフォルトのまま

# --- 便利な関数: VL53L1Xのアドレスを変更する ---
def change_address(sensor, new_address):
    """VL53L1XのI2Cアドレスを変更する（Adafruitライブラリ対応版）"""
    print(f"アドレス変更前: {hex(sensor.i2c_device.device_address)}")
    
    # VL53L1Xのアドレス変更レジスタ (0x0001) に書き込み
    buf = bytearray([0x00, 0x01, new_address & 0x7F])
    sensor.i2c_device.write(buf, end=3, stop=False)
    
    # Python側の通信アドレスも更新
    sensor.i2c_device.device_address = new_address & 0x7F
    print(f"アドレス変更完了: {hex(sensor.i2c_device.device_address)}")


# 1. I2Cバスの準備
i2c = busio.I2C(board.SCL, board.SDA)

# 2. XSHUTピンの初期化 (両方Lowにしてリセット状態=OFFにする)
print("センサをリセット中...")
xshut_front = digitalio.DigitalInOut(XSHUT_FRONT_PIN)
xshut_front.direction = digitalio.Direction.OUTPUT
xshut_front.value = False

xshut_rear = digitalio.DigitalInOut(XSHUT_REAR_PIN)
xshut_rear.direction = digitalio.Direction.OUTPUT
xshut_rear.value = False

time.sleep(0.1) # しっかりOFFにする待機時間

try:
    # --- 前方センサ (Front) のセットアップ ---
    print("Frontセンサを設定中...")
    xshut_front.value = True  # FrontだけONにする
    time.sleep(0.1)           # 起動待ち
    
    # まずデフォルトアドレス(0x29)で捕まえる
    tof_front = adafruit_vl53l1x.VL53L1X(i2c)
    # アドレスを 0x30 に変更する
    change_address(tof_front, ADDR_FRONT)
    print(f"Frontセンサ設定完了 (Addr: 0x{ADDR_FRONT:02X})")
    
    # --- 後方センサ (Rear) のセットアップ ---
    print("Rearセンサを設定中...")
    xshut_rear.value = True   # RearもONにする
    time.sleep(0.1)           # 起動待ち
    
    # Rearはデフォルトアドレス(0x29)で捕まえる (Frontはもう0x30にいるので衝突しない)
    tof_rear = adafruit_vl53l1x.VL53L1X(i2c)
    print(f"Rearセンサ設定完了 (Addr: 0x{ADDR_REAR:02X})")

    # 距離計測モード開始 (1=Short, 2=Long)
    tof_front.distance_mode = 2
    tof_rear.distance_mode = 2
    tof_front.start_ranging()
    tof_rear.start_ranging()

    print("-" * 40)
    print("デュアル計測開始 (Ctrl+Cで終了)")

    while True:
        # 片方ずつチェックしてデータを更新する
        # (and で待つと、片方が取れない時に全体が止まるのを防ぐため分離推奨)
        
        # Frontの処理
        if tof_front.data_ready:
            d_f = tof_front.distance
            tof_front.clear_interrupt()
            dist_f_str = f"{d_f} cm" if d_f is not None else "---"
        else:
            dist_f_str = "Wait"

        # Rearの処理
        if tof_rear.data_ready:
            d_r = tof_rear.distance
            tof_rear.clear_interrupt()
            dist_r_str = f"{d_r} cm" if d_r is not None else "---"
        else:
            dist_r_str = "Wait"

        # 画面表示 (カーソルを上書きして見やすくしても良いが、まずはprintで)
        # 読み取りが両方Waitじゃない時だけ表示、あるいは常に表示など好みで
        if "Wait" not in dist_f_str or "Wait" not in dist_r_str:
            print(f"Front: {dist_f_str}  |  Rear: {dist_r_str}")
        
        time.sleep(0.05)

except Exception as e:
    print(f"\nエラー発生: {e}")
    print("配線を確認してください。特にXSHUTピンのGPIO番号が合っているか確認を！")

finally:
    print("終了処理中...")
    try:
        tof_front.stop_ranging()
        tof_rear.stop_ranging()
    except:
        pass
