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
import adafruit_dps310
import adafruit_vl53l1x
import struct
from picamera2 import Picamera2
from picamera2.devices import IMX500
from collections import deque
from digitalio import DigitalInOut, Direction


# ==========================================
# 1. 設定エリア
# ==========================================

# 目標地点 
TARGET_LATITUDE = 30.374385
TARGET_LONGITUDE = 130.960048
# 制御パラメータ
KP_GAIN = 0.004        # 旋回ゲイン (調整ポイント)
MAX_TURN = 0.35        # 旋回スピードの上限 (行き過ぎ防止)
BASE_SPEED = 0.8       # 基本の前進速度
APPROACH_ANGLE = 10    # この角度以内なら前進許可
MOUNTING_OFFSET = 180 # センサー取り付けズレ補正 (屋外用)
GOAL_DISTANCE_METERS = 5.0 # ゴール判定距離
ACTION_INTERVAL = 0.2      # 制御間隔 (1秒に5回更新)
RECALIB_DISTANCE_THRESHOLD = 7.0
next_cam_dist = 20.0

# --- 以下追加: 空中分離・着地判定設定 ---
ARM_ALTITUDE = 20.0         # ロック解除高度
TARGET_ALTITUDE = 10.0      # 作動(分離)高度
NICROME_PIN = board.D4
LED_PIN = board.D21
DUTY_CYCLE_PERCENT = 0.2    # ニクロム線出力 (20%)
BURN_TIME = 3.0             # 加熱時間
DROP_THRESHOLD = 10.0       # 最高到達点からの降下検知 (要件に合わせ15.0に変更)
RUN_DURATION = 5.0          # スタック回避走行時間
MOTOR_POWER = 1.0           # 回避走行時のモーター出力


# ログ保存先
LOG_DIR = "/home/yuki/cansat_raspi/logs"
os.makedirs(LOG_DIR, exist_ok=True)
filename = f"{LOG_DIR}/navi_{int(time.time())}.csv"


# ==========================================
# 2. モーター設定 
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
nicrome = pwmio.PWMOut(NICROME_PIN, frequency=100, duty_cycle=0)

# 1. 片方ずつアドレスを変えるためにXSHUTを制御
xshut_front = digitalio.DigitalInOut(board.D27)
xshut_front.direction = digitalio.Direction.OUTPUT
xshut_bottom = digitalio.DigitalInOut(board.D17)
xshut_bottom.direction = digitalio.Direction.OUTPUT
# 両方一度眠らせる（リセット）
xshut_front.value = False
xshut_bottom.value = False
time.sleep(0.1)
# 2. Frontだけ起こしてアドレス変更
xshut_front.value = True
time.sleep(0.1)
# 既存のi2cインスタンスを使用
tof_front = adafruit_vl53l1x.VL53L1X(i2c) 
with tof_front.i2c_device as i2c_dev:
    i2c_dev.write(bytes([0x00, 0x01, 0x30])) # 0x30へ書き換え
tof_front.i2c_device.device_address = 0x30
# 3. Bottomを起こす (デフォルト0x29で起動)
xshut_bottom.value = True
time.sleep(0.1)
tof_bottom = adafruit_vl53l1x.VL53L1X(i2c)
# 計測設定
for t in [tof_front, tof_bottom]:
    t.distance_mode = 2
    t.timing_budget = 50
    t.start_ranging()

sensor = None
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
    print("✅ BNO055 接続成功 (0x28)")
except Exception as e:
    print(f"❌ BNO055が見つかりません: {e}")


print("AIカメラ初期化中...")
imx500 = IMX500("network.rpk")
picam2 = Picamera2(imx500.camera_num)
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)

# 既存のパス設定を維持
CALIB_FILE = "/home/yuki/cansat_raspi/bno_offsets.bin"
print("--- BNO055 手動キャリブレーション保存モード ---")
print("機体をゆっくり8の字に回して、Mag: 3 を目指してください。")
try:
    while True:
        sys, gyro, accel, mag = sensor.calibration_status
        print(f"ステータス - Sys:{sys} Gyro:{gyro} Accel:{accel} Mag:{mag}", end="\r")

        # Magが3になったら保存して終了
        if mag == 3:
            print("\n\n✅ Mag:3 到達！ データを保存します...")

            # レジスタからオフセットを取得
            offsets = sensor.offsets_accelerometer + \
                      sensor.offsets_gyroscope + \
                      sensor.offsets_magnetometer + \
                      (sensor.radius_accelerometer, sensor.radius_magnetometer)
            # バイナリ書き出し
            with open(CALIB_FILE, "wb") as f:
                f.write(struct.pack("<hhhhhhhhhHH", *offsets))

            print(f"保存完了: {CALIB_FILE}")
            break
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\n中断されました。")

dps = None
base_altitude = 0.0
try:
    dps = adafruit_dps310.DPS310(i2c, address=0x77)
    print("✅ 気圧センサ接続成功 (Address: 0x77)")
except Exception as e:
    print(f"❌ 気圧センサが見つかりません: {e}")

if dps:
    print("--- 初期高度(オフセット)のキャリブレーション ---")
    calib_samples = 10
    calib_alts = []
    try:
        for _ in range(calib_samples):
            press = dps.pressure
            alt = 44330 * (1.0 - (press / 1013.25) ** 0.1903)
            calib_alts.append(alt)
            time.sleep(0.1)
        base_altitude = sum(calib_alts) / calib_samples
        print(f"✅ 基準高度設定完了: {base_altitude:.2f} m")
    except Exception as e:
        print(f"⚠️ オフセット設定失敗。基準=0.0mで開始: {e}")

# GPS (UART)
uart = serial.Serial("/dev/serial0", baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(uart, debug=False)
gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
gps.send_command(b"PMTK220,500") # 2Hz更新 (GPSの取得頻度を上げる)

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

heading = 0.0
roll = 0.0
pitch = 0.0

def update_sensor_data():
    """センサーから最新の姿勢情報を取得し、グローバル変数を更新する"""
    global heading, roll, pitch
    if not sensor: return
    try:
        raw_h, r, p = sensor.euler
        if raw_h is not None:
            heading = (raw_h + MOUNTING_OFFSET) % 360
        if r is not None and p is not None:
            roll, pitch = r, p
    except: pass

# ==========================================
# 独立関数群 
# ==========================================
def execute_recovery_routine():
    print(f"\n⚠️ 復帰シーケンス開始 (Roll:{roll:.0f} Pitch:{pitch:.0f})")

    # Step 1 & 2: 前進揺さぶり動作
    # (パワー, 前進時間, 後退パワー, 後退時間) の順で定義
    steps = [
        (MOTOR_POWER, 2.0, -0.5, 1.0, "🚀 Step 1: 前方全力"),
        (0.8,         2.0, -0.5, 1.0, "🔄 Step 2: 80%出力")
    ]

    for p_fwd, t_fwd, p_rev, t_rev, msg in steps:
        print(msg)
        # 前進
        set_motor_speed('A', p_fwd); time.sleep(0.05)
        set_motor_speed('B', p_fwd); time.sleep(t_fwd)
        # 切り替えの衝撃緩和（一瞬止める）
        set_motor_speed('A', 0); set_motor_speed('B', 0); time.sleep(0.1)
        # 揺さぶり（少し下がる）
        set_motor_speed('A', p_rev); time.sleep(0.05)
        set_motor_speed('B', p_rev); time.sleep(t_rev)
        
        stop_motors(duration=0.3) # 毎回スローダウン停止
        update_sensor_data()
        if abs(roll) < 100 and abs(pitch) < 100:
            return

    # Step 3: 最終手段 後退全振り
    print("🔄 Step 3: 後退全振り (Reverse 100%)")
    set_motor_speed('A', -MOTOR_POWER); time.sleep(0.05)
    set_motor_speed('B', -MOTOR_POWER); time.sleep(2.0)
    # 前に少し戻して体制を整える
    set_motor_speed('A', 0.5); time.sleep(0.05)
    set_motor_speed('B', 0.5); time.sleep(1.0)
    stop_motors()

def execute_calibration(sensor_obj):
    """フェーズ3: 角丸ポリゴン軌道による地磁気キャリブレーション"""
    execute_recovery_routine()
    if not sensor_obj:
        print("⚠️ センサーがないためキャリブレーションをスキップします。")
        return
    print("\n🤖 BNO055 キャリブレーション (角丸ポリゴン軌道) を開始します...")
    try:
        sensor_obj.mode = adafruit_bno055.CONFIG_MODE
        time.sleep(0.05)
        sensor_obj.mode = adafruit_bno055.NDOF_MODE
        time.sleep(0.05)
    except Exception:
        pass
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

def load_calibration(sensor_obj):
    """保存されたオフセットをセンサーに流し込む"""
    if not os.path.exists(CALIB_FILE):
        print("❌ 保存ファイルが見つかりません。")
        execute_recovery_routine()
    with open(CALIB_FILE, "rb") as f:
        data = struct.unpack("<hhhhhhhhhHH", f.read())
        # センサーの各プロパティに直接代入
        sensor_obj.offsets_accelerometer = data[0:3]
        sensor_obj.offsets_gyroscope = data[3:6]
        sensor_obj.offsets_magnetometer = data[6:9]
        sensor_obj.radius_accelerometer = data[9]
        sensor_obj.radius_magnetometer = data[10]
    return True

def burn_nicrome():
    """ニクロム線を通電加熱し、分離を確認する"""
    global is_fired
    print(f"\n🔥 分離条件達成！ ニクロム線加熱開始")
    # ニクロム線 ON
    nicrome.duty_cycle = int(65535 * DUTY_CYCLE_PERCENT)
    burn_start = time.time()
    # 加熱中のループ (3秒間)
    while time.time() - burn_start < BURN_TIME:
        try:
            if dps:
                p = dps.pressure
                a = 44330 * (1.0 - (p / 1013.25) ** 0.1903)
                print(f"[BURNING] 高度: {a - base_altitude:.2f}m")
        except: pass
        time.sleep(0.1)
    # ニクロム線 OFF
    nicrome.duty_cycle = 0
    is_fired = True
    print("✅ 加熱完了・分離成功")

def parse_direct_tensor(tensor_list):
    # データ数が1801個であることを確認
    if not tensor_list or len(tensor_list) != 1801:
        return None

    # [0] は「AIが確信を持って検出した物体の数」
    num_detections = int(tensor_list[0])

    # 1つも見つからなかったら None を返す
    if num_detections == 0:
        return None

    # 見つかった場合、最初の物体（一番信頼度が高いもの）のX座標は [1] にある
    cx = tensor_list[1]

    # 画像サイズ(320x320と想定)で 0.0 ~ 1.0 に正規化
    center_x = cx / 320.0

    # デバッグ用に検出数も出しておきます
    print(f"🎯 ロックオン (検出数:{num_detections}個) 位置:{center_x:.2f}")

    return center_x

def flush_metadata(picam2, flush_count=3):
    """
    カメラのバッファに溜まった古い(ブレた)推論結果を捨てて、
    機体が停止した後の「最新の綺麗な画像」の推論結果を取得する
    """
    meta = None
    for _ in range(flush_count):
        meta = picam2.capture_metadata()
    return meta

# ------------------------------------------------
# 【Phase 1】 空中分離・着地判定フェーズ
# ------------------------------------------------
def phase1_drop_and_landing():
    print("\n【Phase 1】 放出待機・空中分離・着地判定 を開始します")
    # 履歴・判定用変数
    is_armed = False            # 発火準備フラグ
    is_fired = False            # 発火フラグ
    is_deployed = False         # 開傘(衝撃)検知フラグ
    max_altitude = 0.0
    below_target_count = 0
    landing_count = 0
    static_count = 0
    tof_target_count = 0  # ToF用カウンター
    has_landed = False

    while not has_landed:
        press, temp, abs_alt, rel_alt = 0, 0, 0, 0
        d_b = None
    
        if tof_bottom.data_ready:
            try:
                d_b = tof_bottom.distance
            finally:
                tof_bottom.clear_interrupt()
        if d_b is not None and d_b < 300:
            tof_target_count += 1
        else:
            tof_target_count = 0

        if dps:
            try:
                press = dps.pressure
                temp = dps.temperature
                abs_alt = 44330 * (1.0 - (press / 1013.25) ** 0.1903)
                rel_alt = abs_alt - base_altitude
            
                if rel_alt > max_altitude:
                    max_altitude = rel_alt
            except: pass

        ax, ay, az = 0, 0, 0
        accel_norm = 9.8 # デフォルト1G
        if sensor:
            try:
                a = sensor.acceleration
                if a[0] is not None:
                    ax, ay, az = a
                    accel_norm = math.sqrt(ax**2 + ay**2 + az**2)
            except: pass

    # --- 2. ARMING (放出待機) ---
        if not is_armed:
            if rel_alt > ARM_ALTITUDE:
                is_armed = True
                print(f"🚀 上昇検知！ ロック解除 (高度: {rel_alt:.2f}m > {ARM_ALTITUDE}m)")
            else:
                print(f"[STANDBY] 高度: {rel_alt:.2f}m (Target: > {ARM_ALTITUDE}m)", end="\r")
    
        # --- 3. 空中分離 (発火) ---
        elif is_armed and not is_fired:
            # 開傘(衝撃)検知: 約1G から離れたか
            if (accel_norm > 19.6 or accel_norm < 5.0) and not is_deployed:
                is_deployed = True
                print(f"\n💥 衝撃検知！ 開傘と判定 (G: {accel_norm/9.8:.1f})")
        
            # 降下検知 (15m以上落ちたか)
            has_dropped = (max_altitude - rel_alt) >= DROP_THRESHOLD

            if rel_alt < TARGET_ALTITUDE:
                below_target_count += 1
            else:
                below_target_count = 0

            # 発火条件: 降下済 AND ターゲット未満
            # 本丸: 高度10m以下 かつ (衝撃検知済 OR 3回連続10m未満)
            condition_main = has_dropped and (rel_alt < TARGET_ALTITUDE) and (is_deployed or below_target_count >= 3)
            # バックアップ: Bottom ToFが5回連続300cm(3m)以内を検知
            condition_backup = has_dropped and (tof_target_count >= 5)
            if condition_main:
                burn_nicrome()
                print(f"\n   空中分離！ 気圧高度({rel_alt:.2f}m)より")
            elif condition_backup:
                burn_nicrome()
                print(f"\n📡 ToF緊急分離！ 気圧高度({rel_alt:.2f}m)よりToFを優先 (Bottom: {d_b}cm)")
        

        # --- 4. 着地判定 ---
        elif is_armed: # 分離済み、または分離前だが高度が下がってきた場合
            # 条件A: 気圧が 3m 〜 -3m にいるか
            if -3.0 <= rel_alt <= 3.0:
                landing_count += 1
            else:
                landing_count = 0
        
            # 条件B: 9軸加速度が 1G (9.0〜11.0 m/s^2) 付近で安定しているか
            if 9.0 <= accel_norm <= 11.0:
                static_count += 1
            else:
                static_count = 0

            # 50サンプル(5秒)気圧安定 OR 50サンプル(5秒)加速度安定
            if landing_count >= 50 or static_count >= 50:
                print(f"\n🪂 着地検知！ (Alt: {rel_alt:.2f}m, G: {accel_norm:.1f})")
                has_landed = True

        time.sleep(0.1)

    # --- 5. 緊急分離 (未分離レスキュー) ---
    if not is_fired:
        print("\n⚠️ 未分離レスキュー実行！ 着地後に強制加熱します")
        nicrome.duty_cycle = int(65535 * DUTY_CYCLE_PERCENT)
        time.sleep(BURN_TIME+1)
        nicrome.duty_cycle = 0
        is_fired = True
        print("✅ 強制加熱完了")

    # --- 6. スタック回避走行 ---
    print(f"\n🏎️ スタック回避走行開始 ({RUN_DURATION}秒)")
    execute_recovery_routine()
    print("✅ 回避走行完了。ナビゲーションフェーズへ移行します。")



# ------------------------------------------------
# 【Phase 2】 GPSナビゲーションフェーズ
# ------------------------------------------------
def phase2_gps_navigation():
    global next_cam_dist
    print("\n【Phase 2】 GPSのFix(測位)を待機しています...")
    uart.reset_input_buffer()
    while True:
      gps.update()
      if gps.has_fix:
        print(f"✅ GPS測位完了！(Lat: {gps.latitude:.5f}, Lon: {gps.longitude:.5f})")
        break
      time.sleep(0.01)
    uart.reset_input_buffer()
    with open(filename, "a") as f:
        f.write("Timestamp,Lat,Lon,Heading,Dist,TargetAngle,L_Speed,R_Speed,Fix\n")

    last_action_time = 0
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
                        if min_dist_seen < 15.0: # ★追加: ゴール付近(例: 15m以内)まで来て迷走した場合
                            print(f"\n✅ ゴール付近(ベスト{min_dist_seen:.1f}m)での迷走検知。カメラフェーズへ移行します。")
                            break # ★追加: ループを抜けてPhase 3へ
                        else:
                            print("🔄 姿勢リセットと再キャリブレーションを実行します。")
                            execute_calibration(sensor)               
                            min_dist_seen = dist 
                            continue # 計算を飛ばして次のループへ
                   # ★カメラ起動判定 (20mから5m間隔で移行)
                    if dist < next_cam_dist:
                        stop_motors()
                        print(f"\n🎉 距離 {next_cam_dist}m 圏内に到達！(現在 {dist:.1f}m) カメラフェーズへ移行します。")
                        # ★追加: 次の目標を5m下げる (最小は5m)
                        next_cam_dist = max(5.0, next_cam_dist - 5.0) 
                        break # ループを抜けてPhase 3へ

                # ★ゴール判定 (Phase 3への移行)
                    if dist < GOAL_DISTANCE_METERS:
                        stop_motors()
                        print(f"\n🎉 ゴール到達！(残 {dist:.1f}m) カメラフェーズへ移行します。")
                        break # ★追加: ループを抜けてPhase 3へ

                    else:
                        # --- 走行ロジック (P制御＆リミッター) ---
                        angle_diff = normalize_angle_error(target_ang - heading)
                       
                        if abs(angle_diff) < APPROACH_ANGLE:
                            # 直進: 両輪フルパワー
                            action_icon = "⬆️ 前進"
                            l_val = 1.0
                            r_val = 1.0
                        else:
                            # 旋回: 片輪のみフルパワー駆動
                            action_icon = "🔄 旋回"
                            if angle_diff > 0:
                                # 右旋回: 右を軸に(0.0)、左を回す(1.0)
                                l_val = 0.0
                                r_val = 1.0
                            else:
                                # 左旋回: 左を軸に(0.0)、右を回す(1.0)
                                l_val = 1.0
                                r_val = 0.0
                        #if abs(angle_diff) < APPROACH_ANGLE:
                        #    current_base = BASE_SPEED
                        #    action_icon = "⬆️ 前進"
                       # else:
                        #    current_base = 0.0
                         #   action_icon = "🔄 旋回"
                       # turn = angle_diff * KP_GAIN
                       # turn = max(-MAX_TURN, min(MAX_TURN, turn))

                       # l_val = max(-1.0, min(1.0, current_base - turn))
                       # r_val = max(-1.0, min(1.0, current_base + turn))
                       # l_val = 1.0
                       # r_val = 1.0

                        set_motor_speed('A', l_val)
                        set_motor_speed('B', r_val)
                    
                        # スマホ用ダッシュボード出力
                        diff_str = f"{angle_diff:+4.0f}°"
                        print(f"[{action_icon}] 残:{dist:4.1f}m | 向:{heading:03.0f}°➔{target_ang:03.0f}°({diff_str}) | L:{l_val:>5.2f} R:{r_val:>5.2f}")

                else:
                    print("⏳ [📡GPS待機中] 衛星を見失いました... (安全のため一時停止)")
                    stop_motors(duration=0.5)

                #ログ保存
                log_line = f"{timestamp_str},{lat},{lon},{heading:.2f},{dist:.2f},{target_ang:.2f},{l_val:.2f},{r_val:.2f},{int(has_fix)}\n"
                with open(filename, "a") as f:
                    f.write(log_line)
                    f.flush()
                    os.fsync(f.fileno())

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n停止信号を受信 (Ctrl+C)")
        stop_motors(duration=1.0)
	raise


# ==========================================
# 【Phase 3】AIkカメラ (Stop & Go)
# ==========================================
scan = False

def phase3_ai_terminal():
    global scan
    """【Phase 3】メイン制御ループ (Stop & Go) ※既存のmain()関数を改名"""
    print("\n【Phase 3】 AIカメラナビゲーション開始")

    STATE_SCAN = "SCAN"
    STATE_ALIGN = "ALIGN"
    STATE_DASH = "DASH"
    current_state = STATE_SCAN
    lost_counter = 0
    scan_counter = 0
    SEARCH_PWR = 0.5
    TURN_PWR = 0.3
    DRIVE_PWR = 0.8
    TOF_GOAL_LONG_THRESHOLD = 100
    TOF_GOAL_SHORT_THRESHOLD = 40
    
    led = DigitalInOut(LED_PIN)
    led.direction = Direction.OUTPUT
    led.value = False
    led.value = False

    try:
        stop_motors()
        while True:
            # 【重要】AIの推論サイクルに合わせて少し待つ（CPUの負荷低減も兼ねる）
            time.sleep(0.1)

            # --- ★追加: 前方ToFセンサーによる最終ゴール判定 ---
            if tof_front.data_ready:
                try:
                    d_f = tof_front.distance
                    if d_f is not None:
                        # 状況把握のため現在距離を上書き表示
                        print(f"[ToF] 前方距離: {d_f} mm", end="\r") 
                        
                        if d_f <= TOF_GOAL_LONG_THRESHOLD:
                            DRIVE_PWR = 0.5
                        if d_f <= TOF_GOAL_SHORT_THRESHOLD:
                            print(f"\n\n🎉 最終ゴール到達！(前方距離: {d_f} mm) ミッションコンプリート！")
                            led.value = True
                            
                            return True # ★Phase 3 を完了として終了させる
                finally:
                    tof_front.clear_interrupt()
            # ----------------------------------------------------
            # シンプルに最新のメタデータを1回だけ取得する
            metadata = picam2.capture_metadata()
            cx = None
            if 'CnnOutputTensor' in metadata:
                cx = parse_direct_tensor(metadata['CnnOutputTensor'])

            # ---------------------------------------------
            # 【モード1】スキャン（探す）
            # ---------------------------------------------
            if current_state == STATE_SCAN:
                if cx is not None:
                    print(f"\n🎯 コーン発見！(位置:{cx:.2f}) 照準を合わせます。")
                    current_state = STATE_ALIGN
                    scan = True
                    lost_counter = 0  
                    scan_counter = 0  # 発見したらスキャン回数をリセット
                else:
                    scan_counter += 1
                    if scan_counter > 15:
                        if scan:
                            # ★変更: 一度でも見つけている場合は諦めずにスキャンを継続（カウンターのみリセット）
                            scan_counter = 0
                        else:
                            # 一度も見つけていない場合のみPhase 2へ戻る
                            print("\n⚠️ コーンが見つかりません。GPSフェーズ(Phase 2)に戻ります。")
                            return False          

                    # \r を使って同じ行を上書きし、ログが埋まるのを防ぐ
                    print("\r🔄 周囲をスキャン中... (右へ旋回)", end="")
                    set_motor_speed('A',-SEARCH_PWR)
                    set_motor_speed('B', SEARCH_PWR)

            # ---------------------------------------------
            # 【モード2】アライン（真正面に向く）
            # ---------------------------------------------
            elif current_state == STATE_ALIGN:
                if cx is None:
                    lost_counter += 1
                    # 5回連続（約0.5秒間）見えなかったら「完全に見失った」と判定
                    if lost_counter >= 10:
                        print("\n⚠️ 完全に見失った！スキャンモードに戻ります。")
                        current_state = STATE_SCAN
                    continue

                # 見えた場合はカウンターをリセット
                lost_counter = 0

                if cx < 0.30:
                    print(f"\r👈 左にズレている (位置:{cx:.2f}) -> ちょい左旋回   ", end="")
                    set_motor_speed('A', -TURN_PWR)
                    set_motor_speed('B', TURN_PWR)
                    time.sleep(0.1)
                    stop_motors()
                    time.sleep(0.3)
                elif cx > 0.55:
                    print(f"\r👉 右にズレている (位置:{cx:.2f}) -> ちょい右旋回   ", end="")
                    set_motor_speed('A', TURN_PWR)
                    set_motor_speed('B', -TURN_PWR)
                    time.sleep(0.1)
                    stop_motors()
                    time.sleep(0.3)
                else:
                    print(f"\n✨ 真正面にロックオン！(位置:{cx:.2f}) ダッシュ準備！")
                    current_state = STATE_DASH

            # ---------------------------------------------
            # 【モード3】ダッシュ（直進）
            # ---------------------------------------------
            elif current_state == STATE_DASH:
                print("🚀 直進ダーッシュ！！！")
                set_motor_speed('A', DRIVE_PWR)
                set_motor_speed('B', DRIVE_PWR)
                time.sleep(1.0)
                stop_motors()
                time.sleep(0.5)

                current_state = STATE_ALIGN

    except KeyboardInterrupt:
        print("\nシステムを安全に停止します。")
	raise
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
	raise
    finally:
        stop_motors()
        picam2.stop()



# ==========================================
# メインシーケンス (システム実行の起点)
# ==========================================
if __name__ == "__main__":

    try:
        # phase1_drop_and_landing()
        
        # ★追加: Phase 2 と Phase 3 を行き来するためのループ
        while True:
            if not scan : phase2_gps_navigation()
            
            mission_complete = phase3_ai_terminal()

            if mission_complete:
                print("\n🏁 全ミッション完了！")
                break # 完全クリアで終了
            else:
                print("\n🔄 Phase 2 (GPSナビゲーション) からリトライします...")
    except KeyboardInterrupt:
        print("\n停止信号を受信 (Ctrl+C)")
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
    finally:
        stop_motors()
        # 必要に応じてカメラやLEDのリソース解放処理を追加
