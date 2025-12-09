import time
import board
import adafruit_bno055

i2c = board.I2C()

# i2cdetectで 0x29 が表示されたため、アドレスを 0x29 に指定
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, 0x29) 
    print("9軸IMUセンサ (BNO055 @ 0x29) のテスト...")
except Exception as e:
    print(f"エラー: センサ(0x29)の初期化に失敗しました。 {e}")
    print("配線またはアドレス 0x29 を確認してください。")
    exit()

while True:
    try:
        print(f"温度: {sensor.temperature:.1f} C")
        print(f"加速度 (m/s^2): {sensor.acceleration}")
        print(f"ジャイロ (rad/s): {sensor.gyro}")
        print(f"オイラー角 (Heading, Roll, Pitch): {sensor.euler}")
        print("-" * 20)
    except Exception as e:
        print(f"エラー: {e}")

    time.sleep(2)

