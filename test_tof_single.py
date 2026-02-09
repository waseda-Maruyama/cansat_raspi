import time
import board
import busio
import digitalio
import adafruit_vl53l1x

# GPIO17 (XSHUT) の設定
xshut = digitalio.DigitalInOut(board.D17)
xshut.direction = digitalio.Direction.OUTPUT

# リセット起動
xshut.value = False
time.sleep(0.1)
xshut.value = True
time.sleep(0.1)

# I2C準備
i2c = busio.I2C(board.SCL, board.SDA)
vl53 = adafruit_vl53l1x.VL53L1X(i2c)

# 距離モード (2=Long: 4mまで)
vl53.distance_mode = 2 
vl53.timing_budget = 50

print("計測開始 (無限遠でも止まりません)")
vl53.start_ranging()

while True:
    # データが来ているかチェック
    if vl53.data_ready:
        try:
            dist = vl53.distance
            
            # ここが重要！ None（無限遠）のときは数字扱いしない
            if dist is None:
                print("Out of range (無限遠)")
            else:
                print(f"距離: {dist} cm")
        
        except Exception as e:
            print(f"読み取りエラー: {e}")
        
        finally:
            # 【最重要】何があっても必ず割り込みをクリアする
            # これを忘れるとセンサがフリーズして「切れる」
            vl53.clear_interrupt()
            
    time.sleep(0.05)
