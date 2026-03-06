import time
import serial
import adafruit_gps

# ==========================================
# センサー設定
# ==========================================
# GPS (UART)
uart = serial.Serial("/dev/serial0", baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(uart, debug=False)
gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
gps.send_command(b"PMTK220,200") # 5Hz更新

print("========== GPS座標確認プログラム ==========")
print("測位を開始します...")

try:
    while True:
        gps.update()
        
        if gps.has_fix:
            print(f"✅ 測位完了 (Lat: {gps.latitude:.6f}, Lon: {gps.longitude:.6f})")
        else:
            print("⏳ [📡GPS待機中] 衛星を探索中...")
            
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\n停止信号を受信 (Ctrl+C)")
