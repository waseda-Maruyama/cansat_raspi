import time
import board
import adafruit_dps310

# I2Cを初期化
i2c = board.I2C()  # (SCL, SDA) = (board.SCL, board.SDA)

# センサを初期化 (アドレス 0x77)
try:
    dps = adafruit_dps310.DPS310(i2c, 0x77)
    print("気圧センサ (DPS310 @ 0x77) のテストを開始します...")
except Exception as e:
    print(f"エラー: センサ(0x77)の初期化に失敗しました。 {e}")
    print("配線を確認してください。")
    # スクリプトを終了
    exit()


while True:
    try:
        pressure = dps.pressure
        temperature = dps.temperature
        print(f"気圧: {pressure:.2f} hPa")
        print(f"温度: {temperature:.2f} C")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

    time.sleep(2) # 2秒待つ
