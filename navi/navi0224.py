import time
from datetime import datetime
import board
import digitalio
import pwmio
import adafruit_bno055
import adafruit_gps
import serial
import math
import os

# ==========================================
# 1. 設定エリア
# ==========================================
# 目標地点 (テスト先の緯度経度に合わせてください)
TARGET_LATITUDE = 35.707068
TARGET_LONGITUDE = 139.704465

# 制御パラメータ
KP_GAIN = 0.004        # 旋回ゲイン (調整ポイント)
MAX_TURN = 0.35        # 旋回スピードの上限 (行き過ぎ防止)
BASE_SPEED = 0.8      # 基本の前進速度
APPROACH_ANGLE = 10    # この角度以内なら前進許可
MOUNTING_OFFSET = 0 # センサー取り付けズレ補正 (屋外用)

GOAL_DISTANCE_METERS = 5.0 # ゴール判定距離
ACTION_INTERVAL = 0.2      # 制御間隔 (1秒に5回更新)

# ログ保存先
LOG_DIR = "/home/yuki/cansat_raspi/navi/logs"
os.makedirs(LOG_DIR, exist_ok=True)
filename = f"{LOG_DIR}/navi_{int(time.time())}.csv"

# ==========================================
# 2. モーター設定 (ソフトブレーキ対応版)
# ==========================================
print("モーター初期化中...")
ain1 = digitalio.DigitalInOut(board.D6)
ain2 = digitalio.DigitalInOut(board.D5)
ain1.direction = digitalio.Direction.OUTPUT
ain2.direction = digitalio.Direction.OUTPUT
pwma = pwmio.PWMOut(board.D12, frequency=20000)

bin1 = digitalio.DigitalInOut(board.D22)
bin2 = digitalio.DigitalInOut(board.D23)
bin1.direction = digitalio.Direction.OUTPUT
bin2.direction = digitalio.Direction.OUTPUT
pwmb = pwmio.PWMOut(board.D13, frequency=20000)

current_speed_A = 0.0
current_speed_B = 0.0

def set_motor_speed(motor, throttle):
    global current_speed_A, current_speed_B
    throttle = max(-1.0, min(1.0, throttle))
    duty = int(abs(throttle) * 65535)

    if motor == 'A':
        current_speed_A = throttle
        ain1.value = (throttle > 0)
        ain2.value = (throttle < 0)
        pwma.duty_cycle = duty
    elif motor == 'B':
        current_speed_B = throttle
        bin1.value = (throttle > 0)
        bin2.value = (throttle < 0)
        pwmb.duty_cycle = duty

def stop_motors(duration=0.5, steps=10):
    global current_speed_A, current_speed_B
    start_A = current_speed_A
    start_B = current_speed_B
    if start_A == 0.0 and start_B == 0.0:
        return
    for i in range(1, steps + 1):
        ratio = 1.0 - (i / steps)
        set_motor_speed('A', start_A * ratio)
        set_motor_speed('B', start_B * ratio)
        time.sleep(duration / steps)
    set_motor_speed('A', 0.0)
    set_motor_speed('B', 0.0)

# ==========================================
# 3. センサー設定
# ==========================================
i2c = board.I2C()
sensor = None
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
    print("✅ BNO055 接続成功 (0x28)")
except Exception as e:
    try:
        sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x29)
        print("✅ BNO055 接続成功 (0x29)")
    except Exception as e:
        print(f"❌ BNO055が見つかりません: {e}")

# GPS (UART)
uart = serial.Serial("/dev/serial0", baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(uart, debug=False)
gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
gps.send_command(b"PMTK220,200") # 5Hz更新 (GPSの取得頻度を上げる)

# ==========================================
# 4. 計算関数
# ==========================================
def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin((phi2 - phi1)/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dLon = lon2 - lon1
    y = math.sin(dLon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def normalize_angle_error(error):
    while error > 180: error -= 360
    while error < -180: error += 360
    return error

# ★追加：迷走判定のしきい値（ベストな距離から何メートル遠ざかったらやり直すか）
RECALIB_DISTANCE_THRESHOLD = 7.0 

# ==========================================
# 独立関数群 (フェーズ1とフェーズ3のモジュール化)
# ==========================================

def execute_recovery_routine():
    """フェーズ1: 転倒からの復帰（無条件前進）"""
    print("\n💥 復帰ルーチン(前進)を実行します！")
    set_motor_speed('A', 0.8)
    set_motor_speed('B', 0.8)
    time.sleep(3.0) # 1秒間全力でもがいて起き上がる
    stop_motors()
    print("✅ 復帰ルーチン完了。")

def execute_calibration(sensor_obj):
    """フェーズ3: 角丸ポリゴン軌道による地磁気キャリブレーション"""
    if not sensor_obj:
        print("⚠️ センサーがないためキャリブレーションをスキップします。")
        return

    print("\n🤖 BNO055 キャリブレーション (角丸ポリゴン軌道) を開始します...")
    stop_motors()
    time.sleep(1.0)

    timeout = time.time() + 40.0
    start_time = time.time()

    while time.time() < timeout:
        sys_cal, gyro, accel, mag = sensor_obj.calibration_status
        print(f"自動校正中... [Sys:{sys_cal}, Gyro:{gyro}, Accel:{accel}, Mag:{mag}]")

        if mag == 3 and gyro > 0:
            print("\n✅ 自動校正完了！本当の北を認識しました。")
            break

        # 角丸ポリゴン軌道のロジック
        t = time.time() - start_time
        cycle_time = 2.0
        phase_t = t % cycle_time
        l_val = 0.4

        if phase_t < 0.8:
            r_val = 0.4
        elif phase_t < 1.2:
            ratio = (phase_t - 0.8) / 0.4
            r_val = 0.4 - (0.8 * ratio)
        elif phase_t < 1.6:
            r_val = -0.4
        else:
            ratio = (phase_t - 1.6) / 0.4
            r_val = -0.4 + (0.8 * ratio)

        set_motor_speed('A', l_val)
        set_motor_speed('B', r_val)
        time.sleep(0.05)
    else:
        print("\n⚠️ キャリブレーションがタイムアウトしました。現在の状態で進行します。")

    stop_motors(duration=1.0)
    time.sleep(1.0)

# ==========================================
# フロー開始
# ==========================================
print("\n========== システム起動 ==========")

# 初回実行
print("\n【Phase 1】安定姿勢を目指します ")
execute_recovery_routine()

print("\n【Phase 2】 GPSのFix(測位)を待機しています...")
while True:
    gps.update()
    if gps.has_fix:
        print(f"✅ GPS測位完了！(Lat: {gps.latitude:.5f}, Lon: {gps.longitude:.5f})")
        break
    time.sleep(0.5)

print("\n【Phase 3】キャリブレーションを開始します")
execute_calibration(sensor)

# ------------------------------------------------
# フェーズ 4: メインループ (ナビゲーション)
# ------------------------------------------------
print("\n【Phase 4】 屋外ナビゲーション開始")
with open(filename, "w") as f:
    f.write("Timestamp,Lat,Lon,Heading,Dist,TargetAngle,L_Speed,R_Speed,Fix\n")

last_action_time = 0
has_reached_goal = False

# ★追加：迷走検知のための「ベスト距離」記憶変数（最初は無限大にしておく）
min_dist_seen = float('inf') 

try:
    while True:
        gps.update()
        now_sys = time.time()

        if now_sys - last_action_time >= ACTION_INTERVAL:
            last_action_time = now_sys
            timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            has_fix = gps.has_fix
            lat = gps.latitude if has_fix else 0
            lon = gps.longitude if has_fix else 0

            # --- BNO055 データ取得と【転倒検知】 ---
            heading = 0
            pitch, roll = 0, 0
            if sensor:
                try:
                    # euler[0]:Heading, euler[1]:Roll, euler[2]:Pitch
                    raw_h, r, p = sensor.euler
                    if raw_h is not None:
                        heading = (raw_h + MOUNTING_OFFSET) % 360
                    if r is not None and p is not None:
                        roll, pitch = r, p
                except: pass

            # ★転倒検知ロジック (PitchかRollが100度を超えていたら裏返し)
            if abs(roll) > 100 or abs(pitch) > 100:
                print(f"\n⚠️ 転倒検知！ (Roll:{roll:.0f} Pitch:{pitch:.0f})")
                execute_recovery_routine() # 復帰関数を呼び出し
                continue # 起き上がったら、今のループの計算は飛ばしてやり直す

            dist, target_ang, l_val, r_val = 0, 0, 0, 0

            if has_fix and lat != 0:
                dist = calculate_distance_meters(lat, lon, TARGET_LATITUDE, TARGET_LONGITUDE)
                target_ang = calculate_bearing(lat, lon, TARGET_LATITUDE, TARGET_LONGITUDE)

                # ★距離のベストスコア更新
                if dist < min_dist_seen:
                    min_dist_seen = dist
                
                # ★迷走検知ロジック (ベストスコアより RECALIB_DISTANCE_THRESHOLD 以上遠ざかったか？)
                if dist > min_dist_seen + RECALIB_DISTANCE_THRESHOLD:
                    print(f"\n⚠️ 迷走を検知！ (ベスト距離 {min_dist_seen:.1f}m ➔ 現在 {dist:.1f}m に後退)")
                    print("🔄 姿勢リセットと再キャリブレーションを実行します。")
                    
                    execute_recovery_routine()
                    execute_calibration(sensor)
                    
                    # 再発防止のため、ベストスコアを現在の距離にリセットする
                    min_dist_seen = dist 
                    continue # 計算を飛ばして次のループへ

                # --- ゴール判定 ---
                if not has_reached_goal and dist < GOAL_DISTANCE_METERS:
                    print("\n🎉 GOAL REACHED! 🎉")
                    with open(filename, "a") as f:
                        f.write(f"====================,GOAL REACHED at {timestamp_str},====================\n")
                    has_reached_goal = True
                    stop_motors(duration=1.0)

                if has_reached_goal:
                    stop_motors()
                    print(f"[🏁 ゴール待機] 残{dist:.1f}m")
                else:
                    # --- 走行ロジック (P制御＆リミッター) ---
                    angle_diff = normalize_angle_error(target_ang - heading)

                    if abs(angle_diff) < APPROACH_ANGLE:
                        current_base = BASE_SPEED
                        action_icon = "⬆️ 前進"
                    else:
                        current_base = 0.0
                        action_icon = "🔄 旋回"

                    turn = angle_diff * KP_GAIN
                    turn = max(-MAX_TURN, min(MAX_TURN, turn))

                    l_val = max(-1.0, min(1.0, current_base - turn))
                    r_val = max(-1.0, min(1.0, current_base + turn))

                    set_motor_speed('A', l_val)
                    set_motor_speed('B', r_val)
                    
                    # スマホ用ダッシュボード出力
                    diff_str = f"{angle_diff:+4.0f}°"
                    print(f"[{action_icon}] 残:{dist:4.1f}m | 向:{heading:03.0f}°➔{target_ang:03.0f}°({diff_str}) | L:{l_val:>5.2f} R:{r_val:>5.2f}")

            else:
                print("⏳ [📡GPS待機中] 衛星を見失いました... (安全のため一時停止)")
                stop_motors(duration=0.5)

            # ログ保存
            log_line = f"{timestamp_str},{lat},{lon},{heading:.2f},{dist:.2f},{target_ang:.2f},{l_val:.2f},{r_val:.2f},{int(has_fix)}\n"
            with open(filename, "a") as f:
                f.write(log_line)
                f.flush()
                os.fsync(f.fileno())

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n停止信号を受信 (Ctrl+C)")
    stop_motors(duration=1.0)
