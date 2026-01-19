import time
import board
import digitalio

# LED設定 
led = digitalio.DigitalInOut(board.D21)
led.direction = digitalio.Direction.OUTPUT

print("LED点滅テスト開始 (Ctrl+C終了)")

try:
    while True:
        led.value = True   # 点灯
        print("LED ON ")
        time.sleep(0.5)
        led.value = False  # 消灯
        print("LED OFF")
        time.sleep(0.5)
except KeyboardInterrupt:
    led.value = False
    print("LED OFF - 終了")
