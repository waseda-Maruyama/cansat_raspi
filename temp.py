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
try:

    print("\n3. 【両方】が【前】に回りますか？ (3秒)")
    set_speed('A', 1.0)
    set_speed('B', 1.0)
    time.sleep(5)
    time.sleep(1)
    print("\nテスト終了。停止します。")
    set_speed('A', 0)
    set_speed('B', 0)

except KeyboardInterrupt:
    print("停止")
    set_speed('A', 0)
    set_speed('B', 0)

