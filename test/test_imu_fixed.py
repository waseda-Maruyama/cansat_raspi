import time
import board
import busio
import adafruit_bno055

# I2Cのセットアップ
# ※注意: ラズパイのハードウェア制約で、ここで400k指定しても
# /boot/config.txtの設定が優先されることが多いです。
# 動作が不安定な場合は frequency=100000 (デフォルト) に戻してください。
i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)

try:
    # アドレスは0x28で確定しているので指定
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
except Exception as e:
    print(f"センサの初期化に失敗しました: {e}")
    exit()

print("高速読み取りテスト開始 (Ctrl+Cで停止)")
last_time = time.monotonic()
count = 0

while True:
    try:
        euler = sensor.euler       # (heading, roll, pitch)
        accel = sensor.acceleration  # (ax, ay, az) [m/s^2]
        lin_accel = sensor.linear_acceleration  # 重力抜き [m/s^2]

        if euler and accel and lin_accel:
            heading, roll, pitch = euler
            ax, ay, az = accel
            lax, lay, laz = lin_accel

            count += 1
            now = time.monotonic()
            if now - last_time >= 1.0:
                print(
                  #  f"FPS: {count} | "
                  #  f"Heading: {heading:.2f} Roll: {roll:.2f} Pitch: {pitch:.2f} | "
                    f"Accel: ({ax:.2f}, {ay:.2f}, {az:.2f}) m/s^2 | "
                  #  f"LinAcc: ({lax:.2f}, {lay:.2f}, {laz:.2f}) m/s^2"
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
