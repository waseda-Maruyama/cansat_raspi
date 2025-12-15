import time
import board
import busio
import digitalio
import pwmio
import os
import adafruit_dps310
import adafruit_bno055
from collections import deque

# ==========================================
# 設定エリア
# ==========================================
# ログ保存場所
LOG_DIR = "/home/cansat/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 1. 閾値設定
WAIT_TIME_START = 300      # 待機時間 (秒)
DROP_THRESHOLD = 10.0     # 落下判定 (m)
LANDING_THRESHOLD = 2.0   # 着地判定 (m)
RUN_DURATION = 5.0       # 走行時間 (秒)
MOTOR_POWER = 1.0         # モーター出力

# 2. ピン設定 (Config準拠)
# 左モーター
PIN_L_PWM, PIN_L_IN1, PIN_L_IN2 = board.D18, board.D27, board.D17
# 右モーター
PIN_R_PWM, PIN_R_IN1, PIN_R_IN2 = board.D13, board.D22, board.D24

print("--- CanSat Mission Program (Log & 9-Axis) Start ---")

# ==========================================
# センサー & モーター初期化
# ==========================================
i2c = board.I2C()

# 1. 気圧センサ (DPS310)
dps = None
try:
    dps = adafruit_dps310.DPS310(i2c, address=0x77)
    print("✅ 気圧センサ接続成功 (Address: 0x77)")
except:
    try:
        dps = adafruit_dps310.DPS310(i2c, address=0x76)
        print("✅ 気圧センサ接続成功 (Address: 0x76)")
    except Exception as e:
        print(f"❌ 気圧センサが見つかりません: {e}")

# 2. 9軸センサ (BNO055)
imu = None
try:
    imu = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
    print("✅ 9軸IMU接続成功")
except:
    try:
        imu = adafruit_bno055.BNO055_I2C(i2c, address=0x29)
        print("✅ 9軸IMU接続成功 (Addr: 0x29)")
    except:
        print("⚠️ 9軸IMUが見つかりません (ログは0で埋めます)")

# 3. モーター設定
l_in1 = digitalio.DigitalInOut(PIN_L_IN1)
l_in2 = digitalio.DigitalInOut(PIN_L_IN2)
l_in1.direction = digitalio.Direction.OUTPUT
l_in2.direction = digitalio.Direction.OUTPUT
l_pwm = pwmio.PWMOut(PIN_L_PWM, frequency=5000)

r_in1 = digitalio.DigitalInOut(PIN_R_IN1)
r_in2 = digitalio.DigitalInOut(PIN_R_IN2)
r_in1.direction = digitalio.Direction.OUTPUT
r_in2.direction = digitalio.Direction.OUTPUT
r_pwm = pwmio.PWMOut(PIN_R_PWM, frequency=5000)

def drive_motor(l, r):
    # Left
    l_in1.value, l_in2.value = (l > 0), (l < 0)
    l_pwm.duty_cycle = int(abs(l) * 65535)
    # Right
    r_in1.value, r_in2.value = (r > 0), (r < 0)
    r_pwm.duty_cycle = int(abs(r) * 65535)

def stop_motor():
    drive_motor(0, 0)

# ==========================================
# 待機処理
# ==========================================
print(f"待機モード: {WAIT_TIME_START}秒間 待機します...")
time.sleep(WAIT_TIME_START)

# ==========================================
# ログファイル作成
# ==========================================
csv_filename = f"{LOG_DIR}/mission_{int(time.time())}.csv"
with open(csv_filename, "w") as f:
    # ヘッダー: 時刻, フェーズ, 気圧, 高度, オイラー角(3), 加速度(3), ジャイロ(3), 地磁気(3)
    f.write("Time,Phase,Pressure,Altitude,Heading,Roll,Pitch,AccelX,AccelY,AccelZ,GyroX,GyroY,GyroZ,MagX,MagY,MagZ\n")

print(f"計測開始！ログ保存先: {csv_filename}")

# ==========================================
# メインループ
# ==========================================
history = deque(maxlen=50) # 5秒分の高度履歴
PHASE = 0
start_time = time.time()
run_start_time = 0

try:
    while True:
        now = time.time()
        
        # --- データ取得 ---
        # 気圧・高度
        press, alt = 0, 0
        if dps:
            try:
                press = dps.pressure
                alt = 44330 * (1.0 - (press / 1013.25) ** 0.1903)
            except: pass

        # 9軸データ (Euler, Accel, Gyro, Mag)
        h, r, p = 0, 0, 0
        ax, ay, az = 0, 0, 0
        gx, gy, gz = 0, 0, 0
        mx, my, mz = 0, 0, 0
        
        if imu:
            try:
                # オイラー角
                e = imu.euler
                if e[0] is not None: h, r, p = e
                # 加速度
                a = imu.acceleration
                if a[0] is not None: ax, ay, az = a
                # ジャイロ
                g = imu.gyro
                if g[0] is not None: gx, gy, gz = g
                # 地磁気
                m = imu.magnetic
                if m[0] is not None: mx, my, mz = m
            except: pass

        # --- ログ保存 (CSV) ---
        log_line = f"{now:.2f},{PHASE},{press:.2f},{alt:.2f}," \
                   f"{h:.2f},{r:.2f},{p:.2f}," \
                   f"{ax:.2f},{ay:.2f},{az:.2f}," \
                   f"{gx:.2f},{gy:.2f},{gz:.2f}," \
                   f"{mx:.2f},{my:.2f},{mz:.2f}\n"
        
        with open(csv_filename, "a") as f:
            f.write(log_line)
            f.flush()
            os.fsync(f.fileno())

        # --- 制御ロジック ---
        history.append(alt)
        
        if PHASE == 0: # 落下検知
            if len(history) == 50:
                diff = history[0] - history[-1]
                if diff >= DROP_THRESHOLD:
                    print(f"🚀 落下検知! (降下量: {diff:.1f}m)")
                    PHASE = 1
                    history.clear()

        elif PHASE == 1: # 着地検知
            if len(history) == 50:
                stab = max(history) - min(history)
                if stab <= LANDING_THRESHOLD:
                    print(f"🪂 着地検知! (変動幅: {stab:.1f}m)")
                    PHASE = 2
                    run_start_time = time.time()

        elif PHASE == 2: # 走行
            elapsed = time.time() - run_start_time
            print(f"🏎️ 走行中... 残り {RUN_DURATION - elapsed:.1f}秒")
            drive_motor(MOTOR_POWER, MOTOR_POWER)
            
            if elapsed >= RUN_DURATION:
                print("🏁 走行終了")
                stop_motor()
                PHASE = 3

        elif PHASE == 3: # 終了
            pass

        time.sleep(0.1)

except KeyboardInterrupt:
    stop_motor()
    print("停止")
