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
TARGET_LATITUDE = 35.707068
TARGET_LONGITUDE = 139.704465

KP_GAIN = 0.015
GOAL_DISTANCE_METERS = 3.0
BASE_SPEED = 0.5
MIN_SPEED = 0.3  # 慣性負けを防ぐための最小速度

ACTION_INTERVAL = 1.0

LOG_DIR = "/home/cansat/logs"
os.makedirs(LOG_DIR, exist_ok=True)
filename = f"{LOG_DIR}/mission_{int(time.time())}.csv"

# ==========================================
# 2. モーター設定
# ==========================================
print("モーター初期化中...")

ain1 = digitalio.DigitalInOut(board.D27)
ain2 = digitalio.DigitalInOut(board.D17)
ain1.direction = ain2.direction = digitalio.Direction.OUTPUT
pwma = pwmio.PWMOut(board.D18, frequency=5000)

bin1 = digitalio.DigitalInOut(board.D22)
bin2 = digitalio.DigitalInOut(board.D23)
bin1.direction = bin2.direction = digitalio.Direction.OUTPUT
pwmb = pwmio.PWMOut(board.D13, frequency=5000)

def set_motor_speed(motor, throttle):
    throttle = max(-1.0, min(1.0, throttle))
    duty = int(abs(throttle) * 65535)
    if motor == 'A':
        ain1.value, ain2.value = (throttle > 0), (throttle < 0)
        pwma.duty_cycle = duty
    elif motor == 'B':
        bin1.value, bin2.value = (throttle > 0), (throttle < 0)
        pwmb.duty_cycle = duty

def stop_motors():
    set_motor_speed('A', 0)
    set_motor_speed('B', 0)

# ==========================================
# 3. センサー設定
# ==========================================
i2c = board.I2C()
sensor = None
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
except:
    try: sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x29)
    except: pass

uart = serial.Serial("/dev/serial0", baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(uart, debug=False)
gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
gps.send_command(b"PMTK220,1000")

print("✅ システム準備完了")

# ==========================================
# 4. 計算関数
# ==========================================
def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi, delta_lambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def calculate_bearing(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def normalize_angle_error(error):
    while error > 180: error -= 360
    while error < -180: error += 360
    return error

# ==========================================
# 5. メインループ
# ==========================================
with open(filename, "w") as f:
    f.write("Timestamp,Lat,Lon,Heading,Dist,TargetAngle,L_Speed,R_Speed,Fix\n")

print(f"計測開始: {filename}")

last_action_time = 0
has_reached_goal = False
landing_offset_h = 0.0
is_first_run = True  # 初回走行時に方位オフセットを取得するためのフラグ

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
            
            # --- Heading取得と補正 ---
            heading = 0
            if sensor:
                try:
                    h = sensor.euler[0]
                    if h is not None:
                        # 初回走行開始時に現在の向きを0度基準(オフセット)として記録
                        if has_fix and is_first_run:
                            landing_offset_h = h
                            is_first_run = False
                            print(f"📍 基準方位をセット: {landing_offset_h:.1f}度")
                        
                        # オフセットを適用
                        heading = (h - landing_offset_h) % 360
                except: pass
            
            dist, target_ang, l_val, r_val = 0, 0, 0, 0
            
            if has_fix and lat != 0:
                dist = calculate_distance_meters(lat, lon, TARGET_LATITUDE, TARGET_LONGITUDE)
                target_ang = calculate_bearing(lat, lon, TARGET_LATITUDE, TARGET_LONGITUDE)
                
                if not has_reached_goal and dist < GOAL_DISTANCE_METERS:
                    print("\n🎉 GOAL REACHED! 🎉\n")
                    with open(filename, "a") as f:
                        f.write(f"====================,GOAL REACHED at {timestamp_str},====================\n")
                    has_reached_goal = True
                    stop_motors()
                
                if has_reached_goal:
                    l_val, r_val = 0, 0
                else:
                    # 動きながら補正するロジック
                    angle_diff = normalize_angle_error(target_ang - heading)
                    turn = angle_diff * KP_GAIN
                    
                    l_val = BASE_SPEED - turn
                    r_val = BASE_SPEED + turn
                    
                    # 慣性で止まらないよう最小速度を維持し、かつ上限をクリップ
                    l_val = max(MIN_SPEED, min(0.8, l_val))
                    r_val = max(MIN_SPEED, min(0.8, r_val))
                    
                    set_motor_speed('A', l_val)
                    set_motor_speed('B', r_val)
                    print(f"RUN: 残{dist:.1f}m | 補正後向{heading:.0f}° | L:{l_val:.2f} R:{r_val:.2f}")
            
            else:
                print("📡 GPS待機中... (慣性維持のため微速前進)")
                # GPSロスト時も完全に止まらず、ゆっくり直進して姿勢を安定させる
                if not has_reached_goal and not is_first_run:
                    set_motor_speed('A', MIN_SPEED)
                    set_motor_speed('B', MIN_SPEED)
                else:
                    stop_motors()
            
            # --- ログ保存 ---
            log_line = f"{timestamp_str},{lat},{lon},{heading:.2f},{dist:.2f},{target_ang:.2f},{l_val:.2f},{r_val:.2f},{int(has_fix)}\n"
            with open(filename, "a") as f:
                f.write(log_line)
                f.flush()
                os.fsync(f.fileno())

        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n停止")
    stop_motors()
