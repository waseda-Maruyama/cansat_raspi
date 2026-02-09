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
        # データを取得
        # sensor.euler は失敗時に None を返すことがあるため一度変数で受ける
        euler = sensor.euler
        
        if euler:
            heading, roll, pitch = euler
            
            # 速度計測用
            count += 1
            now = time.monotonic()
            if now - last_time >= 1.0:
                print(f"FPS: {count} | Heading: {heading} | Roll: {roll} | Pitch: {pitch}")
                last_time = now
                count = 0
        else:
            # データが取れなかった場合（None）
            pass

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
