import time
import board
import busio
import adafruit_bno055

# I2C周波数を400kHzに設定
i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)

try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, 0x28) # アドレスは確認してください
except:
    sensor = adafruit_bno055.BNO055_I2C(i2c, 0x29)

print("高速読み取りテスト開始 (Ctrl+Cで停止)")
last_time = time.monotonic()
count = 0

while True:
    try:
        # データを取得
        heading, roll, pitch = sensor.euler
        
        # 速度計測用
        count += 1
        now = time.monotonic()
        if now - last_time >= 1.0:
            print(f"FPS: {count} | Heading: {heading}")
            last_time = now
            count = 0
            
    except Exception as e:
        pass
