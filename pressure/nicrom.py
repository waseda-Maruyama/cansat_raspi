import time
import board
import pwmio
from digitalio import DigitalInOut, Direction

# GPIO 4 (Pin 7) の設定
NICROME_PIN = board.D4
LED_PIN = board.D21  

print("=== ニクロム線 加熱テスト (対話モード) ===")
print("注意: 0.1Ωの場合、値は慎重に上げてください。")
print("開始推奨値: 0.01 (1%)")
print("終了するには 'q' を入力してください。")

try:
    # PWM初期化 (周波数100Hz)
    nicrome_pwm = pwmio.PWMOut(NICROME_PIN, frequency=100, duty_cycle=0)

    led = DigitalInOut(LED_PIN)
    led.direction = Direction.OUTPUT
    led.value = False
    while True:
        user_input = input("\nデューティ比を入力 (0.01 〜 1.0) > ")

        if user_input.lower() == 'q':
            break

        try:
            duty_float = float(user_input)
            
            # 安全リミット (念のため最大50%で制限をかけておくことを推奨)
            if duty_float < 0.0:
                print("0以上の値を入力してください。")
                continue
            if duty_float > 0.5:
                print("⚠️ 危険: 0.50 (50%) 以上は過電流のリスクが高いためブロックしました。")
                print("本当に流す場合はコードのリミットを解除してください。")
                continue

            # Duty比計算 (0-65535)
            duty_int = int(65535 * duty_float)
            
            print(f"--> 出力開始: {duty_float*100:.1f}% ({duty_int})")
            
            # 出力 ON 
            led.value = True
            nicrome_pwm.duty_cycle = duty_int
            time.sleep(2.0) # 1秒間通電
            
            # 出力 OFF
            led.value = False
            nicrome_pwm.duty_cycle = 0
            print("--> 停止。状態を確認してください。")

        except ValueError:
            print("数値を入力してください。")

except Exception as e:
    print(f"エラー発生: {e}")

finally:
    # 安全のため必ずOFFにして終了
    if 'nicrome_pwm' in locals():
        nicrome_pwm.duty_cycle = 0
        nicrome_pwm.deinit()
    if 'led' in locals():
        led.value = False
        led.deinit()
    print("PWMリソースを開放して終了しました。")
