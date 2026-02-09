import time
import board
import digitalio
import pwmio
import adafruit_bno055
import math

# ==========================================
# 1. 設定エリア
# ==========================================
# 屋内テスト用：常に「0度（北）」を目標方位とする
VIRTUAL_TARGET_BEARING = 0.0
MOUNTING_OFFSET = -90.0

# 制御パラメータ（本番と同じ設定）
KP_GAIN = 0.004
BASE_SPEED = 0.1  # 屋内なので少し遅めに設定
APPROACH_ANGLE = 20

# ==========================================
# 2. モーター設定 (左モーター反転対応版)
# ==========================================
# 左モーター (A)
ain1 = digitalio.DigitalInOut(board.D6)
ain2 = digitalio.DigitalInOut(board.D5)
ain1.direction = digitalio.Direction.OUTPUT
ain2.direction = digitalio.Direction.OUTPUT
pwma = pwmio.PWMOut(board.D12, frequency=20000)

# 右モーター (B)
bin1 = digitalio.DigitalInOut(board.D22)
bin2 = digitalio.DigitalInOut(board.D23)
bin1.direction = digitalio.Direction.OUTPUT
bin2.direction = digitalio.Direction.OUTPUT
pwmb = pwmio.PWMOut(board.D13, frequency=20000)

def set_motor_speed(motor, throttle):
    throttle = max(-1.0, min(1.0, throttle))
    duty = int(abs(throttle) * 65535)

    if motor == 'A':
        # 左モーター前後反転の修正を反映
        ain1.value = (throttle < 0) # True/Falseを入れ替え
        ain2.value = (throttle > 0)
        pwma.duty_cycle = duty
    elif motor == 'B':
        bin1.value = (throttle > 0)
        bin2.value = (throttle < 0)
        pwmb.duty_cycle = duty

def stop_motors():
    set_motor_speed('A', 0)
    set_motor_speed('B', 0)

# ==========================================
# 3. センサー設定 (BNO055のみ)
# ==========================================
i2c = board.I2C()
sensor = None
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
    print("✅ BNO055 接続成功 (0x28)")
except:
    print(f"❌ センサーが見つかりません: {e}")
    exit()

def normalize_angle_error(error):
    while error > 180: error -= 360
    while error < -180: error += 360
    return error

# ==========================================
# 4. メインループ
# ==========================================
print("📡 BNO055 キャリブレーションを開始します...")
print("機体を『8の字』にゆっくり回したり、傾けたりしてください。")

# キャリブレーション状態を確認するループ
# 3番目の値 (Magnetometer) が 3 になれば方位が正確になります
while not sensor.calibrated:
    sys, gyro, accel, mag = sensor.calibration_status
    print(f"校正中... [Sys:{sys}, Gyro:{gyro}, Accel:{accel}, Mag:{mag}]")

    # 全体(sensor.calibrated)を待たず、磁気(mag)が3になればOKとする
    if mag == 3:
        # ジャイロも最低限(1以上)あればより安定します
        if gyro > 0:
            break
    time.sleep(0.5)

print("\n✅ 校正完了！本当の北（磁北）を基準に動作を開始します。")

print("\n--- 屋内姿勢制御テスト開始 ---")
print("機体を水平に持ち、ゆっくり左右に回してください。")
print("目標方位は 0度 (北) に固定されています。")
print("中断するには Ctrl+C を押してください。\n")

try:
    while True:
        # 方位取得
        raw_heading = sensor.euler[0]
        
        # センサーエラー時はスキップ
        if heading is None:
            time.sleep(0.1)
            continue

        # --- 制御ロジック ---
        heading = (raw_heading + MOUNTING_OFFSET) % 360
        # 1. ズレの計算 (目標0度 - 現在向き)
        angle_diff = normalize_angle_error(VIRTUAL_TARGET_BEARING - heading)

        # 2. 「近づいたら前進」ロジック
        if abs(angle_diff) < APPROACH_ANGLE:
            # ズレが小さい(20度以内) -> 前進許可
            current_base = BASE_SPEED
        else:
            # ズレが大きい -> 前進せず、その場で旋回して向きを合わせる
            current_base = 0.0

        # 3. 旋回量の計算 (P制御)
        turn = angle_diff * KP_GAIN
        
        # 左右出力の決定
        l_val = current_base + turn
        r_val = current_base - turn

        # モーター駆動
        set_motor_speed('A', l_val)
        set_motor_speed('B', r_val)

        # ログ表示
        print(f"向: {heading:5.1f}° | ズレ: {angle_diff:5.1f}° | L:{l_val:.2f} R:{r_val:.2f}")
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n停止")
    stop_motors()
