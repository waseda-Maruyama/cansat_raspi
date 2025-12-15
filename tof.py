import time
import board
import busio
import adafruit_vl53l1x

def main():
    print("--- ToFセンサ (VL53L1X) テスト開始 ---")
    print("Ctrl+C で終了します\n")

    # I2Cバスの準備
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
    except Exception as e:
        print(f"エラー: I2Cバスが見つかりません。\n{e}")
        return

    # センサの初期化
    try:
        tof = adafruit_vl53l1x.VL53L1X(i2c)
        
        # 計測モード設定 (1=Short, 2=Long)
        # Short: ~1.3m (暗所), 高速, 外乱光に強い
        # Long:  ~4.0m (暗所), 遠くまで測れる
        tof.distance_mode = 1 
        tof.timing_budget = 100 # ミリ秒

        print("計測を開始します...")
        tof.start_ranging() # 計測スタート
        
    except ValueError:
        print("エラー: VL53L1X が見つかりません。")
        print("ヒント: 'sudo i2cdetect -y 1' で 29 が表示されているか確認してください。")
        return

    # 計測ループ
    try:
        while True:
            # データ準備ができているか確認
            if tof.data_ready:
                # 距離を取得 (cm単位)
                distance = tof.distance
                
                # エラー値のフィルタリング (Noneが返ることがあるため)
                if distance is not None:
                    print(f"距離: {distance} cm")
                else:
                    print("計測エラー")
                
                # 次の計測のために割り込みをクリア
                tof.clear_interrupt()
                
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n--- テスト終了 ---")
        # 終了時は計測を停止するのが行儀が良い
        # (ただしCtrl+Cだとここまで到達しないこともあるので必須ではない)
        # tof.stop_ranging()

if __name__ == "__main__":
    main()
