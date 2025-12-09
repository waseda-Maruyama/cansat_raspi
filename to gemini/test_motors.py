import time
import board
import digitalio
import pwmio

print("モータードライバ (TB6612) [Direct Control] テスト開始")
print(" `cansat_manual.html` Section 7 のピン配置で動作します。")

# --- モーターA (左) の設定 ---
ain1 = digitalio.DigitalInOut(board.D27) # GPIO 27 (物理ピン13)
ain2 = digitalio.DigitalInOut(board.D17) # GPIO 17 (物理ピン11)
ain1.direction = digitalio.Direction.OUTPUT
ain2.direction = digitalio.Direction.OUTPUT
# PWMOut は 0 (0%) から 65535 (100%) の duty_cycle を取る
pwma = pwmio.PWMOut(board.D18, frequency=5000) # GPIO 18 (物理ピン12)

# --- モーターB (右) の設定 ---
bin1 = digitalio.DigitalInOut(board.D22) # GPIO 22 (物理ピン15)
bin2 = digitalio.DigitalInOut(board.D23) # GPIO 23 (物理ピン16)
bin1.direction = digitalio.Direction.OUTPUT
bin2.direction = digitalio.Direction.OUTPUT
pwmb = pwmio.PWMOut(board.D13, frequency=5000) # GPIO 13 (物理ピン33)

# STBYは 3.3V に直結されているので、常にON（コード制御不要）

def set_motor_speed(motor, throttle):
    """ -1.0 (逆転) から 1.0 (正転) でモーターを制御 """

    # throttle値が-1.0から1.0の範囲に収まるようにする
    throttle = max(-1.0, min(1.0, throttle))

    # duty_cycle (0 to 65535) を計算
    duty = int(abs(throttle) * 65535)

    if motor == 'A':
        if throttle > 0: # 正転
            ain1.value = True
            ain2.value = False
        elif throttle < 0: # 逆転
            ain1.value = False
            ain2.value = True
        else: # 停止 (Coast: 惰性で止まる)
            ain1.value = False
            ain2.value = False
        pwma.duty_cycle = duty

    elif motor == 'B':
        if throttle > 0: # 正転
            bin1.value = True
            bin2.value = False
        elif throttle < 0: # 逆転
            bin1.value = False
            bin2.value = True
        else: # 停止 (Coast: 惰性で止まる)
            bin1.value = False
            bin2.value = False
        pwmb.duty_cycle = duty

def stop_motors():
    print("停止 (Coast)")
    set_motor_speed('A', 0)
    set_motor_speed('B', 0)

try:
    print("ピンを初期化中...")
    time.sleep(1) # ピンが安定するまで待つ

    # 50%のパワーで前進
    print("前進 (50%) - 3秒")
    set_motor_speed('A', 0.5)
    set_motor_speed('B', 0.5)
    time.sleep(3)

    # 停止
    stop_motors()
    time.sleep(2)

    # 50%のパワーで後退
    print("後退 (50%) - 3秒")
    set_motor_speed('A', -0.5)
    set_motor_speed('B', -0.5)
    time.sleep(3)

    # 停止
    stop_motors()
    time.sleep(2)

    # 100%のパワーで前進
    print("前進 (100%) - 2秒")
    set_motor_speed('A', 1.0)
    set_motor_speed('B', 1.0)
    time.sleep(2)

    print("テスト完了")

except Exception as e:
    print(f"エラー発生: {e}")
finally:
    # スクリプトが終了するかエラーで落ちても、必ずモーターを止める
    stop_motors()

