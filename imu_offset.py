import time
import board
import adafruit_bno055

# I2C初期化
i2c = board.I2C()

# センサー初期化 (gps.pyやtest_imu.pyの実績に基づき0x29を使用)
try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x29)
    print("✅ BNO055 接続成功 (Address: 0x29)")
except Exception as e:
    print(f"❌ エラー: {e}")
    exit()

# オフセット用変数
offset_h, offset_r, offset_p = 0.0, 0.0, 0.0

def get_corrected_euler():
    """現在の値を読み取り、オフセットを適用して返す"""
    euler = sensor.euler
    if euler[0] is None:
        return None
    
    # 生の値を読み取り
    raw_h, raw_r, raw_p = euler
    
    # 補正計算 (360度/180度の範囲に収める)
    corr_h = (raw_h - offset_h) % 360
    corr_r = (raw_r - offset_r)
    corr_p = (raw_p - offset_p)
    
    return corr_h, corr_r, corr_p

print("\n--- IMU 軸補正テスト ---")
print("1. 機体を着地した状態（傾いた状態）で固定してください。")
print("2. Enterキーを押すと、その状態を『水平・正面(0,0,0)』として記録します。")
input(">>> 準備ができたらEnterを押してください...")

# 現在の値をオフセットとして記録
current = sensor.euler
if current[0] is not None:
    offset_h, offset_r, offset_p = current
    print(f"\n✨ オフセット記録完了: H={offset_h:.1f}, R={offset_r:.1f}, P={offset_p:.1f}")
else:
    print("❌ データが取得できませんでした。")
    exit()

print("\n--- 補正後の値（この値が制御に使われます） ---")
try:
    while True:
        corrected = get_corrected_euler()
        if corrected:
            h, r, p = corrected
            print(f"修正後方位(Heading): {h:>6.1f} | Roll: {r:>6.1f} | Pitch: {p:>6.1f}", end='\r')
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nテストを終了します。")
