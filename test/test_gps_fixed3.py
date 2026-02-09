import time
import serial
import adafruit_gps

print("GPSモジュール (Serial接続) テスト開始")

# --- 修正箇所: busio ではなく serial を使う ---
# Raspberry Piの GPIO 14(TX), 15(RX) は通常 "/dev/serial0" に割り当てられています
try:
    # シリアルポートを開く
    # serial0 は raspi-config でシリアルを有効にすると現れます
    uart = serial.Serial("/dev/serial0", baudrate=9600, timeout=10)
    
    # GPSオブジェクトの作成
    gps = adafruit_gps.GPS(uart, debug=False)
    
    # 初期設定 (RMCとGGAのみ出力)
    gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
    # 更新レート 1Hz
    gps.send_command(b"PMTK220,1000")
    
    print("✅ GPS初期化成功。データ受信待機中...")
    print("※ 屋内では受信できません。窓際か屋外で試してください。")

except Exception as e:
    print(f"❌ 初期化エラー: {e}")
    print("ヒント: 'sudo raspi-config' > Interface Options > Serial Port で")
    print("  - Shell access: No")
    print("  - Serial hardware: Yes")
    print("  に設定されているか確認してください。")
    exit()

# --- 計測ループ ---
last_print = time.monotonic()
while True:
    # データを読み込む
    gps.update()
    
    current = time.monotonic()
    if current - last_print >= 1.0:
        last_print = current
        
        if not gps.has_fix:
            print("📡 測位中... (Fix待ち)")
            continue
        
        print("=" * 40)
        print(f"📍 緯度: {gps.latitude:.6f}")
        print(f"📍 経度: {gps.longitude:.6f}")
        print(f"🕒 時間: {gps.timestamp_utc}")
        print(f"⛰️ 高度: {gps.altitude_m} m")
