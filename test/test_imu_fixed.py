import time
import csv
from datetime import datetime
import board
import busio
import adafruit_bno055
import digitalio
import pwmio

# ==========================================
# 0. 走行パラメータ
# ==========================================
# 左右で個体差がある場合は RIGHT_TRIM を微調整してください。
BASE_THROTTLE = 0.8
RIGHT_TRIM = 0.00

# ==========================================
# 1. モーター設定
# ==========================================
ain1 = digitalio.DigitalInOut(board.D6)
ain2 = digitalio.DigitalInOut(board.D5)
ain1.direction = digitalio.Direction.OUTPUT
ain2.direction = digitalio.Direction.OUTPUT
pwma = pwmio.PWMOut(board.D12, frequency=20000)

bin1 = digitalio.DigitalInOut(board.D22)
bin2 = digitalio.DigitalInOut(board.D23)
bin1.direction = digitalio.Direction.OUTPUT
bin2.direction = digitalio.Direction.OUTPUT
pwmb = pwmio.PWMOut(board.D13, frequency=20000)

def set_motor_speed(motor, throttle):
    throttle = max(-1.0, min(1.0, throttle))
    duty = int(abs(throttle) * 65535)

    if motor == 'A':  # 左モーター
        ain1.value = (throttle < 0)
        ain2.value = (throttle > 0)
        pwma.duty_cycle = duty
    elif motor == 'B':  # 右モーター
        bin1.value = (throttle > 0)
        bin2.value = (throttle < 0)
        pwmb.duty_cycle = duty

def stop_motors():
    set_motor_speed('A', 0)
    set_motor_speed('B', 0)

# I2Cのセットアップ
# 動作が不安定な場合は frequency=100000 (デフォルト) に戻してください。
i2c = board.I2C()

try:
    # アドレスは0x28で確定しているので指定
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
except Exception as e:
    print(f"センサの初期化に失敗しました: {e}")
    exit()

print("高速読み取りテスト開始 (Ctrl+Cで停止)")
csv_path = "imu_log.csv"
csv_file = open(csv_path, mode="a", newline="", encoding="utf-8")
csv_writer = csv.writer(csv_file)

# 空ファイルのときだけヘッダーを書き込む
if csv_file.tell() == 0:
    csv_writer.writerow(
        [
            "timestamp",
            "heading",
            "roll",
            "pitch",
            "ax",
            "ay",
            "az",
            "lax",
            "lay",
            "laz",
            "left_throttle",
            "right_throttle",
        ]
    )

print(f"CSV出力先: {csv_path}")
left_throttle = BASE_THROTTLE
right_throttle = BASE_THROTTLE + RIGHT_TRIM

# 直進開始
set_motor_speed('A', left_throttle)
set_motor_speed('B', right_throttle)
print(f"直進開始: left={left_throttle:.2f}, right={right_throttle:.2f}")

last_time = time.monotonic()
count = 0

try:
    while True:
        try:
            euler = sensor.euler       # (heading, roll, pitch)
            accel = sensor.acceleration  # (ax, ay, az) [m/s^2]
            lin_accel = sensor.linear_acceleration  # 重力抜き [m/s^2]

            if euler and accel and lin_accel:
                heading, roll, pitch = euler
                ax, ay, az = accel
                lax, lay, laz = lin_accel

                timestamp = datetime.now().isoformat(timespec="milliseconds")
                csv_writer.writerow([
                    timestamp,
                    heading,
                    roll,
                    pitch,
                    ax,
                    ay,
                    az,
                    lax,
                    lay,
                    laz,
                    left_throttle,
                    right_throttle,
                ])
                csv_file.flush()

                count += 1
                now = time.monotonic()
                if now - last_time >= 1.0:
                    print(
                        f"FPS: {count} | "
                        f"Heading: {heading:.2f} Roll: {roll:.2f} Pitch: {pitch:.2f} | "
                        f"Accel: ({ax:.2f}, {ay:.2f}, {az:.2f}) m/s^2 | "
                        f"LinAcc: ({lax:.2f}, {lay:.2f}, {laz:.2f}) m/s^2"
                    )
                    count = 0
                    last_time = now
                


        except OSError as e:
            # I2C通信エラー（クロックストレッチなど）はよく起きるので
            # 止まらずに再試行させるが、ログには出す
            print(f"通信エラー(無視して続行): {e}")
            time.sleep(0.01) # 少し休む

        except KeyboardInterrupt:
            print("\n終了します")
            break

        except Exception as e:
            print(f"予期せぬエラー: {e}")
            time.sleep(0.1)
finally:
    stop_motors()
    print("モーター停止")
    csv_file.close()
