import time
import board
import digitalio
import pwmio
import adafruit_bno055
import adafruit_gps
import busio  # UART (シリアル通信) のために必要
import math

# --- ターゲット設定 (ゴール地点) ---
TARGET_LATITUDE = 35.707068  # 早稲田大学付近
TARGET_LONGITUDE = 139.704465

# --- P制御ゲイン (要調整) ---
KP_GAIN = 0.015

# --- ゴール判定距離 (メートル) ---
GOAL_DISTANCE_METERS = 3.0

# ======================================================================
# 1. モーター (TB6612) 設定
# ======================================================================
print("モーター (TB6612) 初期化中...")
# (モーター設定は変更なし)
# --- モーターA (左) ---
ain1 = digitalio.DigitalInOut(board.D27)
ain2 = digitalio.DigitalInOut(board.D17)
ain1.direction = digitalio.Direction.OUTPUT
ain2.direction = digitalio.Direction.OUTPUT
pwma = pwmio.PWMOut(board.D18, frequency=5000)
# --- モーターB (右) ---
bin1 = digitalio.DigitalInOut(board.D22)
bin2 = digitalio.DigitalInOut(board.D23)
bin1.direction = digitalio.Direction.OUTPUT
bin2.direction = digitalio.Direction.OUTPUT
pwmb = pwmio.PWMOut(board.D13, frequency=5000)

def set_motor_speed(motor, throttle):
    throttle = max(-1.0, min(1.0, throttle))
    duty = int(abs(throttle) * 65535)
    if motor == 'A':
        if throttle > 0:    ain1.value, ain2.value = True, False
        elif throttle < 0:  ain1.value, ain2.value = False, True
        else:               ain1.value, ain2.value = False, False
        pwma.duty_cycle = duty
    elif motor == 'B':
        if throttle > 0:    bin1.value, bin2.value = True, False
        elif throttle < 0:  bin1.value, bin2.value = False, True
        else:               bin1.value, bin2.value = False, False
        pwmb.duty_cycle = duty

def stop_motors():
    print("停止 (Coast)")
    set_motor_speed('A', 0)
    set_motor_speed('B', 0)

# ======================================================================
# 2. IMU (BNO055) 設定
# ======================================================================
print("IMU (BNO055) 初期化中...")
# (IMUの設定は変更なし - デフォルトI2Cピン GP2/GP3 を使う)
i2c = board.I2C() 
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, 0x29)
except Exception as e:
    print(f"エラー: IMU(0x29)の初期化に失敗。 {e}")
    stop_motors()
    exit()

print("BNO055 キャリブレーションを開始します。")
print("センサーをゆっくりと8の字に動かしてください...")
while not sensor.calibrated:
    print(f"キャリブレーション状態: {sensor.calibration_status}")
    time.sleep(0.5)

print("\nIMU キャリブレーション完了！")

# ======================================================================
# 3. GPS (adafruit_gps) 設定 【★UART GP14/15版に修正★】
# ======================================================================
print("GPS (UART on GP14, GP15) 初期化中...")
try:
    # GP14 (PicoのUART0 TX) 
    # GP15 (PicoのUART0 RX)
    uart = busio.UART(board.GP14, board.GP15, baudrate=9600, timeout=10)
    
    # UART接続用のGPSオブジェクトを使用
    gps = adafruit_gps.GPS(uart) 

    # NMEAセンテンスのRMCとGGAのみ受信 (MTKチップ用コマンド)
    gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
    # 更新レートを 1Hz (1秒間に1回) に設定
    gps.send_command(b"PMTK220,1000")
    
    print("GPS (UART) 初期化完了。測位待機中...")
except Exception as e:
    print(f"エラー: GPS(UART)の初期化に失敗。 {e}")
    print("GP14/GP15の配線、またはボーレート(9600)を確認してください。")
    stop_motors()
    exit()

# ======================================================================
# 4. ナビゲーション計算 (ハーバーサイン公式)
# ======================================================================
# (計算関数は変更なし)
def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dLon = lon2 - lon1
    y = math.sin(dLon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - \
        math.sin(lat1) * math.cos(lat2) * math.cos(dLon)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360

def normalize_angle_error(error):
    while error > 180: error -= 360
    while error < -180: error += 360
    return error

# ======================================================================
# 5. メインループ (自律走行)
# ======================================================================
# (メインループは変更なし)
print("=" * 30)
print(f"メインループ開始。目標: ({TARGET_LATITUDE}, {TARGET_LONGITUDE})")

try:
    while True:
        gps.update()
        
        if not gps.has_fix:
            print("GPS 測位中...")
            stop_motors()
            time.sleep(1)
            continue
            
        current_heading = sensor.euler[0]
        if current_heading is None:
            print("IMU データ取得失敗...")
            stop_motors()
            time.sleep(1)
            continue

        current_lat = gps.latitude
        current_lon = gps.longitude
        
        distance = calculate_distance_meters(current_lat, current_lon, TARGET_LATITUDE, TARGET_LONGITUDE)
        target_bearing = calculate_bearing(current_lat, current_lon, TARGET_LATITUDE, TARGET_LONGITUDE)
        angle_error = normalize_angle_error(target_bearing - current_heading)

        print(f"現在地: ({current_lat:.6f}, {current_lon:.6f})")
        print(f"距離: {distance:.2f} m | 現在方位: {current_heading:.1f} | 目標方位: {target_bearing:.1f} | ズレ: {angle_error:.1f} 度")

        if distance < GOAL_DISTANCE_METERS:
            print(f"目的地 ({GOAL_DISTANCE_METERS}m 以内) に到着！")
            stop_motors()
            break
            
        turn_throttle = angle_error * KP_GAIN
        base_speed = 0.4 # 安全のため遅めに設定
        
        left_speed = base_speed - turn_throttle
        right_speed = base_speed + turn_throttle
        
        left_speed = max(-1.0, min(1.0, left_speed))
        right_speed = max(-1.0, min(1.0, right_speed))
        
        print(f"制御: L={left_speed:.2f} R={right_speed:.2f}")
        set_motor_speed('A', left_speed)
        set_motor_speed('B', right_speed)

        time.sleep(0.1)

except KeyboardInterrupt:
    print("手動で停止しました。")
except Exception as e:
    print(f"エラー発生: {e}")
finally:
    stop_motors()
    print("プログラム終了")
