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
# 目標地点 (早稲田大学周辺)
TARGET_LATITUDE = 35.707068
TARGET_LONGITUDE = 139.704465

# 制御パラメータ
KP_GAIN = 0.015
GOAL_DISTANCE_METERS = 3.0
BASE_SPEED = 0.5

# 制御間隔 (秒)
ACTION_INTERVAL = 1.0

# ログ保存先
LOG_DIR = "/home/cansat/logs"
os.makedirs(LOG_DIR, exist_ok=True)
filename = f"{LOG_DIR}/mission_{int(time.time())}.csv"

# ==========================================
# 2. モーター設定 (修正版: 右D23)
# ==========================================
print("モーター初期化中...")

# 左モーター (A)
ain1 = digitalio.DigitalInOut(board.D27)
ain2 = digitalio.DigitalInOut(board.D17)
ain1.direction = digitalio.Direction.OUTPUT
ain2.direction = digitalio.Direction.OUTPUT
pwma = pwmio.PWMOut(board.D18, frequency=5000)

# 右モーター (B) - GPIO23を使用
bin1 = digitalio.DigitalInOut(board.D22)
bin2 = digitalio.DigitalInOut(board.D23) # 修正済み
bin1.direction = digitalio.Direction.OUTPUT
bin2.direction = digitalio.Direction.OUTPUT
pwmb = pwmio.PWMOut(board.D13, frequency=5000)

def set_motor_speed(motor, throttle):
    throttle = max(-1.0, min(1.0, throttle))
    duty = int(abs(throttle) * 65535)
    
    if motor == 'A':
        ain1.value = (throttle > 0)
        ain2.value = (throttle < 0)
        pwma.duty_cycle = duty
    elif motor == 'B':
        bin1.value = (throttle > 0)
        bin2.value = (throttle < 0)
        pwmb.duty_cycle = duty

def stop_motors():
    set_motor_speed('A', 0)
    set_motor_speed('B', 0)

# ==========================================
# 3. センサー設定
# ==========================================
i2c = board.I2C()

# 9軸センサ (BNO055)
sensor = None
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
except:
    try: sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x29)
    except: pass

# GPS (UART)
uart = serial.Serial("/dev/serial0", baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(uart, debug=False)
gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
gps.send_command(b"PMTK220,1000") # 1Hz更新

print("✅ システム準備完了")

# ==========================================
# 4. 計算関数
# ==========================================
def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
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

# ==========================================
# 5. メインループ
# ==========================================
# CSVヘッダー書き込み (9軸のHeadingや日時を含める)
with open(filename, "w") as f:
    f.write("Timestamp,Lat,Lon,Heading,Dist,TargetAngle,L_Speed,R_Speed,Fix\n")

print(f"計測開始: {filename}")
print("GPS受信待機中...")

last_action_time = 0
has_reached_goal = False # ゴールしたかどうかのフラグ

try:
    while True:
        # GPSデータ読み込み（常に実行）
        gps.update()
        
        now_sys = time.time()
        
        # 制御・ログ保存タイミング (1秒に1回)
        if now_sys - last_action_time >= ACTION_INTERVAL:
            last_action_time = now_sys
            
            # 日時文字列 (例: 2023-12-15 12:00:00)
            timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # --- データ取得 ---
            has_fix = gps.has_fix
            lat = gps.latitude if has_fix else 0
            lon = gps.longitude if has_fix else 0
            
            # 9軸データ (Heading)
            heading = 0
            if sensor:
                try:
                    h = sensor.euler[0]
                    if h is not None: heading = h
                except: pass
            
            # --- 制御ロジック ---
            dist, target_ang, l_val, r_val = 0, 0, 0, 0
            
            if has_fix and lat != 0:
                dist = calculate_distance_meters(lat, lon, TARGET_LATITUDE, TARGET_LONGITUDE)
                target_ang = calculate_bearing(lat, lon, TARGET_LATITUDE, TARGET_LONGITUDE)
                
                # ★ ゴール判定 ★
                # まだゴールしておらず、かつ距離内に入った場合
                if not has_reached_goal and dist < GOAL_DISTANCE_METERS:
                    print("\n🎉🎉🎉 GOAL REACHED! (記録を継続します) 🎉🎉🎉\n")
                    
                    # CSVに区切り線を書き込む
                    with open(filename, "a") as f:
                        f.write(f"====================,GOAL REACHED at {timestamp_str},====================\n")
                    
                    has_reached_goal = True # フラグを立てる
                    stop_motors() # モーター停止
                
                # --- モーター制御 ---
                if has_reached_goal:
                    # ゴール後はモーター停止のまま
                    l_val, r_val = 0, 0
                    stop_motors()
                    print(f"[GOAL済] 現在地ログ継続: 残{dist:.1f}m")
                else:
                    # まだゴールしていないなら走る
                    angle_diff = normalize_angle_error(target_ang - heading)
                    turn = angle_diff * KP_GAIN
                    l_val = BASE_SPEED - turn
                    r_val = BASE_SPEED + turn
                    set_motor_speed('A', l_val)
                    set_motor_speed('B', r_val)
                    print(f"RUN: 残{dist:.1f}m | 向{heading:.0f}° | L:{l_val:.2f} R:{r_val:.2f}")
            
            else:
                # GPSロスト時
                print("📡 GPS検索中... (Motor Stop)")
                stop_motors()
            
            # --- ログ保存 (日時, 9軸, GPS全て含む) ---
            # フォーマット: 日時, 緯度, 経度, 9軸方角, 距離, 目標方角, 左出力, 右出力, Fix状態
            log_line = f"{timestamp_str},{lat},{lon},{heading:.2f},{dist:.2f},{target_ang:.2f},{l_val:.2f},{r_val:.2f},{int(has_fix)}\n"
            
            with open(filename, "a") as f:
                f.write(log_line)
                f.flush()
                os.fsync(f.fileno())

        # 短いスリープ
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n停止")
    stop_motors()
