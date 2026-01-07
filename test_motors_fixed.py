import time
import board
import digitalio
import pwmio

print("--- モーター方向テスト開始 ---")

# ==========================================
# 1. ピン設定 (あなたの環境に合わせています)
# ==========================================
# 左モーター (A)
ain1 = digitalio.DigitalInOut(board.D27)
ain2 = digitalio.DigitalInOut(board.D17)
ain1.direction = digitalio.Direction.OUTPUT
ain2.direction = digitalio.Direction.OUTPUT
pwma = pwmio.PWMOut(board.D18, frequency=5000)

# 右モーター (B)
bin1 = digitalio.DigitalInOut(board.D22)
bin2 = digitalio.DigitalInOut(board.D23)
bin1.direction = digitalio.Direction.OUTPUT
bin2.direction = digitalio.Direction.OUTPUT
pwmb = pwmio.PWMOut(board.D13, frequency=5000)

def set_speed(motor, throttle):
    # throttle: 1.0(前進最大) 〜 -1.0(後退最大)
    duty = int(abs(throttle) * 65535)
    
    if motor == 'A': # 左
        if throttle > 0:
            ain1.value = True
            ain2.value = False
        elif throttle < 0:
            ain1.value = False
            ain2.value = True
        else:
            ain1.value = False
            ain2.value = False
        pwma.duty_cycle = duty
        
    elif motor == 'B': # 右
        if throttle > 0:
            bin1.value = True
            bin2.value = False
        elif throttle < 0:
            bin1.value = False
            bin2.value = True
        else:
            bin1.value = False
            bin2.value = False
        pwmb.duty_cycle = duty

# ==========================================
# 2. テスト実行
# ==========================================
try:
    print("\n1. 【左】タイヤだけが【前】に回りますか？ (3秒)")
    set_speed('A', 0.5)  # 左 前進
    set_speed('B', 0.0)  # 右 停止
    time.sleep(3)
    set_speed('A', 0.0)
    time.sleep(1)

    print("\n2. 【右】タイヤだけが【前】に回りますか？ (3秒)")
    set_speed('A', 0.0)  # 左 停止
    set_speed('B', 0.5)  # 右 前進
    time.sleep(3)
    set_speed('B', 0.0)
    time.sleep(1)

    print("\n3. 【両方】が【前】に回りますか？ (3秒)")
    set_speed('A', 0.5)
    set_speed('B', 0.5)
    time.sleep(3)
    
    print("\nテスト終了。停止します。")
    set_speed('A', 0)
    set_speed('B', 0)

except KeyboardInterrupt:
    print("停止")
    set_speed('A', 0)
    set_speed('B', 0)

