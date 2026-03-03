import time
import board
import adafruit_bno055
import struct
import os

# 既存のパス設定を維持
CALIB_FILE = "/home/yuki/cansat_raspi/bno_offsets.bin"

i2c = board.I2C()
sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)

print("--- BNO055 手動キャリブレーション保存モード ---")
print("機体をゆっくり8の字に回して、Mag: 3 を目指してください。")

try:
    while True:
        sys, gyro, accel, mag = sensor.calibration_status
        print(f"ステータス - Sys:{sys} Gyro:{gyro} Accel:{accel} Mag:{mag}", end="\r")
        
        # Magが3になったら保存して終了
        if mag == 3:
            print("\n\n✅ Mag:3 到達！ データを保存します...")
            
            # レジスタからオフセットを取得
            offsets = sensor.offsets_accelerometer + \
                      sensor.offsets_gyroscope + \
                      sensor.offsets_magnetometer + \
                      (sensor.radius_accelerometer, sensor.radius_magnetometer)
            
            # バイナリ書き出し
            with open(CALIB_FILE, "wb") as f:
                f.write(struct.pack("<hhhhhhhhhHH", *offsets))
            
            print(f"保存完了: {CALIB_FILE}")
            break
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\n中断されました。")
