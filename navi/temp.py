import time
import board
import adafruit_bno055

# I2Cとセンサーの初期化
i2c = board.I2C()
sensor = None

try:
    sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
    print("✅ BNO055 接続成功 (0x28)")
except Exception:
    try:
        sensor = adafruit_bno055.BNO055_I2C(i2c, address=0x29)
        print("✅ BNO055 接続成功 (0x29)")
    except Exception as e:
        print(f"❌ センサーが見つかりません: {e}")
        exit()

print("\n=========================================")
print("   姿勢（Pitch / Roll）確認テスト開始")
print("=========================================")
print("機体を平らな床に置いたり、手で傾けたりして")
print("値がどう変化するか確認してください。")
print("終了するには Ctrl+C を押してください。\n")

try:
    while True:
        # eulerプロパティから (Heading, Roll, Pitch) を取得
        euler = sensor.euler
        
        if euler[0] is not None and euler[1] is not None and euler[2] is not None:
            heading, roll, pitch = euler
            
            # 状態をわかりやすくテキストで表示
            status = "🟢 正常 (水平)"
            if abs(roll) > 100 or abs(pitch) > 100:
                status = "⚠️ 転倒 (裏返し)"

            # 値を揃えて出力
            print(f"Roll(左右傾き): {roll:+4.0f}° | Pitch(前後傾き): {pitch:+4.0f}° | Heading(方位): {heading:03.0f}° | 判定: {status}")
        else:
            print("センサー準備中...")
            
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nテストを終了します。")
