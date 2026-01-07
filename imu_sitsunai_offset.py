import time
import board
import digitalio
import pwmio
import adafruit_bno055

# ==========================================
# 1. ピン設定 (config.py / 最終配線準拠)
# ==========================================
# 左モーター
PIN_L_PWM, PIN_L_IN1, PIN_L_IN2 = board.D18, board.D27, board.D17
# 右モーター
PIN_R_PWM, PIN_R_IN1, PIN_R_IN2 = board.D13, board.D22, board.D24

# ==========================================
# 2. 初期化
# ==========================================
i2c = board.I2C()

# 9軸センサ (実績のある0x29を優先)
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x29)
    print("✅ BNO055 接続成功 (0x29)")
except:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
    print("✅ BNO055 接続成功 (0x28)")

# モーター設定
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

def drive(l, r):
    l_in1.value, l_in2.value = (l > 0), (l < 0)
    l_pwm.duty_cycle = int(abs(l) * 65535)
    r_in1.value, r_in2.value = (r > 0), (r < 0)
    r_pwm.duty_cycle = int(abs(r) * 65535)

def stop():
    drive(0, 0)

# ==========================================
# 3. テストシーケンス
# ==========================================
offset_h = 0.0

def get_heading():
    raw_h = sensor.euler[0]
    if raw_h is None: return 0.0
    return (raw_h - offset_h) % 360

try:
    print("🚀 テスト開始: 5秒後に動き出します...")
    time.sleep(5)

    # --- ステップ1: 前進3秒 ---
    print("Step 1: 前進中 (3秒)...")
    drive(0.6, 0.6)
    time.sleep(3)

    # --- ステップ2: 停止とオフセット取得 ---
    print("Step 2: 停止・姿勢安定待ち...")
    # ゆっくり止まるために出力を絞る
    drive(0.3, 0.3)
    time.sleep(0.5)
    stop()
    time.sleep(2.0) # 完全に静止するまで待機

    raw_val = sensor.euler[0]
    if raw_val is not None:
        offset_h = raw_val
        print(f"📍 基準方位(0度)をセットしました: {offset_h:.1f}")
    
    # --- ステップ3: 右90度旋回テスト ---
    print("Step 3: 右に90度旋回します...")
    target = 90.0
    start_time = time.time()
    
    while time.time() - start_time < 5: # 最大5秒間試行
        current = get_heading()
        error = (target - current + 180) % 360 - 180
        print(f"現在方位: {current:.1f} | ズレ: {error:.1f}", end='\r')
        
        if abs(error) < 5.0: # 5度以内に収まったら終了
            print("\n✅ 目標角度に到達")
            break
            
        # 旋回制御 (簡易P制御)
        power = max(0.3, min(0.6, abs(error) * 0.01))
        if error > 0: drive(power, -power) # 右旋回
        else: drive(-power, power) # 左旋回
        
        time.sleep(0.05)
    
    stop()
    print("\n🏁 テスト終了")

except KeyboardInterrupt:
    stop()
    print("\n中断されました")
