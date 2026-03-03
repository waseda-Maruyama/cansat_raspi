
import time
import board
import adafruit_bno055
import struct
import os

CALIB_FILE = "/home/yuki/cansat_raspi/bno_offsets.bin"

i2c = board.I2C()
sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)

def load_calibration(sensor_obj):
    """保存されたオフセットをセンサーに流し込む"""
    if not os.path.exists(CALIB_FILE):
        print("❌ 保存ファイルが見つかりません。")
        return False
        
    with open(CALIB_FILE, "rb") as f:
        data = struct.unpack("<hhhhhhhhhHH", f.read())
        # センサーの各プロパティに直接代入
        sensor_obj.offsets_accelerometer = data[0:3]
        sensor_obj.offsets_gyroscope = data[3:6]
        sensor_obj.offsets_magnetometer = data[6:9]
        sensor_obj.radius_accelerometer = data[9]
        sensor_obj.radius_magnetometer = data[10]
    return True

print("--- BNO055 読み込み＆北指名テスト ---")

if load_calibration(sensor):
    print("✅ データの復元に成功しました。")
else:
    exit()

print("現在の方位を表示します（0度付近が北です）。Ctrl+Cで終了。")

try:
    while True:
        sys, gyro, accel, mag = sensor.calibration_status
        heading, roll, pitch = sensor.euler
        
        if heading is not None:
            # 既存の表示スタイルを継承
            print(f"Heading: {heading:05.1f}° | Calib[M:{mag} S:{sys}]", end="\r")
            
            if abs(heading) < 5 or abs(heading - 360) < 5:
                print("\n★ 北を向いています！ ★")
        
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\nテスト終了。")
