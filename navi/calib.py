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
MOUNTING_OFFSET = 0.0

# 制御パラメータ（本番と同じ設定）
KP_GAIN = 0.004
BASE_SPEED = 0.5  # 屋内なので少し遅めに設定
APPROACH_ANGLE = 10
CALIB_SPEED = 0.4

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


# ★追加：現在のスピードを記憶しておく変数
current_speed_A = 0.0
current_speed_B = 0.0

def set_motor_speed(motor, throttle):
    global current_speed_A, current_speed_B  # グローバル変数を更新できるようにする
    throttle = max(-1.0, min(1.0, throttle))
    duty = int(abs(throttle) * 65535)

    if motor == 'A':
        current_speed_A = throttle  # 今のスピードを記憶
        ain1.value = (throttle > 0)
        ain2.value = (throttle < 0)
        pwma.duty_cycle = duty
    elif motor == 'B':
        current_speed_B = throttle  # 今のスピードを記憶
        bin1.value = (throttle > 0)
        bin2.value = (throttle < 0)
        pwmb.duty_cycle = duty

def stop_motors(duration=0.5, steps=10):
    """
    duration秒かけて、steps回に分けて滑らかに停止する関数
    デフォルトは 0.5秒かけて 10段階で減速
    """
    global current_speed_A, current_speed_B
    
    # 減速を開始する前のスピードを保存
    start_A = current_speed_A
    start_B = current_speed_B
    
    # すでに止まっていれば何もしない
    if start_A == 0.0 and start_B == 0.0:
        return

    # 徐々に 0 に近づけるループ
    for i in range(1, steps + 1):
        # 残りの割合を計算 (例: 0.9 -> 0.8 -> ... -> 0.0)
        ratio = 1.0 - (i / steps)
        
        # 記憶しておいた初期スピード × 割合 で徐々に下げる
        set_motor_speed('A', start_A * ratio)
        set_motor_speed('B', start_B * ratio)
        
        # durationをstepsで割った時間だけ待つ
        time.sleep(duration / steps)
        
    # 念のため最後に確実に 0 をセット
    set_motor_speed('A', 0.0)
    set_motor_speed('B', 0.0)

# ==========================================
# 3. センサー設定 (BNO055のみ)
# ==========================================
i2c = board.I2C()
sensor = None
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
    print("✅ BNO055 接続成功 (0x28)")
except Exeption as e:
    print(f"❌ センサーが見つかりません: {e}")
    exit()

def normalize_angle_error(error):
    while error > 180: error -= 360
    while error < -180: error += 360
    return error

# ==========================================
# 4. メインループ
# ==========================================
# ==========================================
# 4.5 BNO055 自動キャリブレーション (正方形・姿勢復帰版)
# ==========================================
if sensor:
    print("🤖 モーターによる自動キャリブレーション（正方形軌道）を開始します...")
    
    stop_motors()
    time.sleep(2.0)

    print("走行して地磁気を学習中...")
    timeout = time.time() + 40.0 
    start_time = time.time()

    while time.time() < timeout:
        sys, gyro, accel, mag = sensor.calibration_status
        print(f"自動校正中... [Sys:{sys}, Gyro:{gyro}, Accel:{accel}, Mag:{mag}]")

        if mag == 3 and gyro > 0:
            print("\n✅ 自動校正完了！本当の北を認識しました。")
            break
        
        # ------------------------------------------------
        # 止まらずに滑らかに直進と旋回を繰り返す（角丸ポリゴン軌道）
        # ------------------------------------------------
        t = time.time() - start_time
        
        # 1サイクルを 2.0秒 とする
        cycle_time = 2.0
        phase_t = t % cycle_time

        # ★左タイヤは常に前進（慣性を殺さず、前転を防ぐ最大のポイント）
        l_val = 0.4 
        
        if phase_t < 0.8:
            # 【フェーズ1：直進】 両輪が 0.4 で真っ直ぐ進む
            r_val = 0.4
            
        elif phase_t < 1.2:
            # 【フェーズ2：移行（直進 -> 旋回）】 0.4秒かけて滑らかに右タイヤを逆転
            # ratio は 0.0 から 1.0 まで徐々に増える
            ratio = (phase_t - 0.8) / 0.4
            r_val = 0.4 - (0.8 * ratio) # 0.4 から -0.4 へシームレスに変化
            
        elif phase_t < 1.6:
            # 【フェーズ3：旋回】 右に鋭く曲がる（左は進み続けているので止まらない）
            r_val = -0.4 
            
        else:
            # 【フェーズ4：移行（旋回 -> 直進）】 0.4秒かけて滑らかに右タイヤを前進に戻す
            ratio = (phase_t - 1.6) / 0.4
            r_val = -0.4 + (0.8 * ratio) # -0.4 から 0.4 へシームレスに変化

        # モーターに指示
        set_motor_speed('A', l_val)
        set_motor_speed('B', r_val)
        # ------------------------------------------------
        # ------------------------------------------------
        time.sleep(0.05) # 細かくループを回して状態をチェック
    else:
        print("\n⚠️ キャリブレーションがタイムアウトしました。")

    # 終了時は安全に停止
    stop_motors()
    time.sleep(1.0) 

else:
    print("⚠️ センサーがないためキャリブレーションをスキップします。")




print("\n--- 屋内姿勢制御テスト開始 ---")
print("機体を水平に持ち、ゆっくり左右に回してください。")
print("目標方位は 0度 (北) に固定されています。")
print("中断するには Ctrl+C を押してください。\n")

try:
    while True:
        # 方位取得
        raw_heading = sensor.euler[0]
        
        # センサーエラー時はスキップ
        if raw_heading is None:
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
        # ★追加：旋回スピードの上限を設定（オーバーシュート対策）
        # 最大パワーを 0.35 程度に抑えることで、勢いがつきすぎるのを防ぐ
        MAX_TURN = 0.35
        turn = max(-MAX_TURN, min(MAX_TURN, turn))
        
        # 左右出力の決定
        l_val = current_base - turn
        r_val = current_base + turn

       # ★追加：出力が -1.0 〜 1.0 の範囲を超えないように安全処理
        l_val = max(-1.0, min(1.0, l_val))
        r_val = max(-1.0, min(1.0, r_val))

        # モーター駆動
        set_motor_speed('A', l_val)
        set_motor_speed('B', r_val)

        # ログ表示
        print(f"向: {heading:5.1f}° | ズレ: {angle_diff:5.1f}° | L:{l_val:.2f} R:{r_val:.2f}")
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n停止")
    stop_motors()
