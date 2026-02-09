import time
import board
import adafruit_dps310
import os
import csv
import numpy as np # 計算用 (なければ標準機能で計算します)
from datetime import datetime

# ==========================================
# 設定
# ==========================================
# ログ保存先
LOG_DIR = "/home/yuki/cansat_raspi/logs/pressure_test"
os.makedirs(LOG_DIR, exist_ok=True)

# CSVファイル名 (日時付き)
csv_filename = f"{LOG_DIR}/pressure_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# 計測間隔 (秒)
INTERVAL = 0.1 

# ==========================================
# 初期化
# ==========================================
print("--- 気圧データロガー ---")
print("動作: データをCSVに記録し、終了時に統計を表示します。")
print(f"保存先: {csv_filename}")

# I2C / センサ初期化 (0x77)
try:
    i2c = board.I2C()
    dps = adafruit_dps310.DPS310(i2c, address=0x77)
    dps.reset()
    # 精度重視の設定 (必要に応じて変更)
    dps.pressure_oversample_count = adafruit_dps310.SampleCount.COUNT_64
    dps.pressure_rate = adafruit_dps310.Rate.RATE_16_HZ
    
    # 安定するまで少し待つ
    print("センサ初期化中... (3秒待機)")
    time.sleep(3)
    
except Exception as e:
    print(f"❌ 初期化エラー: {e}")
    exit()

# データ保持用リスト
alt_data = []
press_data = []

print("\n計測開始！ (停止するには Ctrl+C を押してください)")

# ==========================================
# メインループ
# ==========================================
try:
    with open(csv_filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        # ヘッダー書き込み
        writer.writerow(["Timestamp", "Pressure_hPa", "Temp_C", "Altitude_m"])
        
        while True:
            # データ取得
            p = dps.pressure
            t = dps.temperature
            
            # 高度計算 (標準大気圧 1013.25hPa を基準とした絶対高度)
            # ※この値を「その場の基準(0m)」としたい場合、この値の平均をオフセットにします
            alt = 44330 * (1.0 - (p / 1013.25) ** 0.1903)
            
            # リストに追加
            press_data.append(p)
            alt_data.append(alt)
            
            # タイムスタンプ
            now_str = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            
            # CSV記録
            writer.writerow([datetime.now(), f"{p:.2f}", f"{t:.2f}", f"{alt:.2f}"])
            f.flush() # 毎回書き込みを確定させる（強制終了対策）
            
            # コンソール表示
            print(f"[{now_str}] 気圧: {p:.2f} hPa | 推定高度: {alt:.2f} m")
            
            time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("\n\n--- 計測終了 ---")

    # ==========================================
    # 統計データの計算と表示
    # ==========================================
    if len(alt_data) > 0:
        count = len(alt_data)
        
        # 気圧
        p_avg = sum(press_data) / count
        p_min = min(press_data)
        p_max = max(press_data)
        
        # 高度
        a_avg = sum(alt_data) / count
        a_min = min(alt_data)
        a_max = max(alt_data)
        
        print("\n📊 統計結果 (オフセット設定の参考にしてください)")
        print(f"サンプル数: {count}")
        print("-" * 40)
        print(f"【高度 (m)】")
        print(f"  平均値 (Average): {a_avg:.4f} m  <-- これを offset.txt に推奨")
        print(f"  最小値 (Min)    : {a_min:.4f} m")
        print(f"  最大値 (Max)    : {a_max:.4f} m")
        print(f"  ブレ幅 (Delta)  : {a_max - a_min:.4f} m")
        print("-" * 40)
        print(f"【気圧 (hPa)】")
        print(f"  平均: {p_avg:.2f} hPa")
        print(f"  最小: {p_min:.2f} hPa")
        print(f"  最大: {p_max:.2f} hPa")
        print("-" * 40)
        print(f"CSV保存完了: {csv_filename}")
        
    else:
        print("データがありませんでした。")

finally:
    pass
