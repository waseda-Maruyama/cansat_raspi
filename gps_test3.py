import serial
import math
import time
import csv
import os
from datetime import datetime

# --- 設定 ---
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 9600
LOG_FILE = 'gps_log.csv'  # 保存するファイル名

# --- ターゲット設定 (ゴール地点) ---
TARGET_LATITUDE = 35.707068
TARGET_LONGITUDE = 139.704465
EARTH_RADIUS = 6378137

def nmea_to_decimal(nmea_val, direction):
    """NMEA形式 (DDMM.MMMM) を 10進数 (DD.DDDD) に変換"""
    if not nmea_val: return None
    try:
        dot_index = nmea_val.find('.')
        if dot_index == -1: return None
        dd_str = nmea_val[:dot_index-2]
        mm_str = nmea_val[dot_index-2:]
        val = float(dd_str) + (float(mm_str) / 60.0)
        if direction in ['S', 'W']: val = -val
        return val
    except ValueError:
        return None

def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversineの公式で距離(m)を計算"""
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlon = rlon2 - rlon1
    dlat = rlat2 - rlat1
    a = math.sin(dlat / 2)**2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS * c

def init_log_file():
    """ログファイルの準備（ヘッダー書き込み）"""
    # ファイルが存在しない場合のみヘッダーを書く
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            # ヘッダー: 日時, 緯度, 経度, ゴールまでの距離
            writer.writerow(['Timestamp', 'Latitude', 'Longitude', 'Distance_m'])

def save_to_sd(lat, lon, dist):
    """データをCSVに追記保存"""
    try:
        with open(LOG_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow([timestamp, lat, lon, dist])
    except Exception as e:
        print(f"保存エラー: {e}")

def main():
    print("--- GPSロガー (SDカード保存版) 開始 ---")
    print(f"保存先: {LOG_FILE}")
    print(f"取得間隔: 約1秒\n")
    
    init_log_file()

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        
        while True:
            # 1. シリアルバッファをクリアして「最新のデータ」を待つ状態にする
            #    (これをしないと数秒遅れの古いデータが読まれてしまう)
            ser.reset_input_buffer()

            # 2. データが流れてくるのを少し待つ＆探す
            #    (GPSは常時データを吐いているので、GGAが出るまで何行か読む)
            found_valid_data = False
            start_time = time.time()
            
            while (time.time() - start_time) < 2.0: # 最大2秒探す
                try:
                    line = ser.readline()
                    if not line: continue
                    
                    line_str = line.decode('utf-8', errors='replace').strip()
                    
                    if line_str.startswith('$GNGGA') or line_str.startswith('$GPGGA'):
                        parts = line_str.split(',')
                        if len(parts) > 5 and parts[2] and parts[4]:
                            # 緯度経度変換
                            current_lat = nmea_to_decimal(parts[2], parts[3])
                            current_lon = nmea_to_decimal(parts[4], parts[5])
                            
                            if current_lat is not None and current_lon is not None:
                                # 距離計算
                                dist = calculate_distance(current_lat, current_lon, TARGET_LATITUDE, TARGET_LONGITUDE)
                                
                                # --- 画面表示 ---
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] 緯度: {current_lat:.6f} / 経度: {current_lon:.6f} / 残り: {dist:.2f} m")
                                
                                # --- SDカード(ファイル)保存 ---
                                save_to_sd(current_lat, current_lon, dist)
                                
                                found_valid_data = True
                                break # ループを抜けて待機へ
                except Exception:
                    continue

            if not found_valid_data:
                print("GPS測位中... (データなし)")

            # 3. 1秒待機 (ここを変えると頻度が変わります)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n終了します")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
