import time
import board
import busio
import adafruit_dps310
import adafruit_bno055
import os

# --- 設定 ---
# ログファイルの保存場所（日時付きファイル名で生成）
LOG_DIR = "/home/cansat/logs"
os.makedirs(LOG_DIR, exist_ok=True) # フォルダがなければ作る

# ★ここに待機処理を追加★
WAIT_MINUTES = 5
print(f"起動しました。{WAIT_MINUTES}分間待機してから計測を開始します...")

# 300秒（5分）待つ
time.sleep(WAIT_MINUTES * 60)


filename = f"{LOG_DIR}/log_{int(time.time())}.csv"

print(f"ログ保存開始: {filename}")

# I2Cバスの準備 (SDA=GPIO2, SCL=GPIO3)
i2c = board.I2C()

# --- センサー初期化 ---
# 1. 気圧センサ (DPS310)
dps = None
try:
    # 成功した実績のある書き方
    dps = adafruit_dps310.DPS310(i2c, address=0x77)
except:
    try:
        dps = adafruit_dps310.DPS310(i2c, address=0x76)
    except Exception as e:
        print(f"DPS310 初期化エラー: {e}")

# 2. IMUセンサ (BNO055)
imu = None
try:
    imu = adafruit_bno055.BNO055_I2C(i2c, address=0x28)
except:
    try:
        imu = adafruit_bno055.BNO055_I2C(i2c, address=0x29)
    except Exception as e:
        print(f"BNO055 初期化エラー: {e}")

# --- CSVヘッダー書き込み ---
with open(filename, "w") as f:
    f.write("Timestamp,Pressure_hPa,Temp_C,Altitude_m,Heading,Roll,Pitch,AccelX,AccelY,AccelZ\n")

# --- 計測ループ ---
while True:
    try:
        # データ取得
        now = time.time()
        
        # 気圧データ
        if dps:
            try:
                pressure = dps.pressure
                temp = dps.temperature
                # 簡易高度計算
                alt = 44330 * (1.0 - (pressure / 1013.25) ** 0.1903) if pressure else 0
            except:
                pressure, temp, alt = 0, 0, 0
        else:
            pressure, temp, alt = 0, 0, 0

        # IMUデータ
        if imu:
            try:
                heading, roll, pitch = imu.euler
                ax, ay, az = imu.acceleration
                
                heading = heading if heading is not None else 0
                roll = roll if roll is not None else 0
                pitch = pitch if pitch is not None else 0
                ax = ax if ax is not None else 0
                ay = ay if ay is not None else 0
                az = az if az is not None else 0
            except:
                heading, roll, pitch = 0, 0, 0
                ax, ay, az = 0, 0, 0
        else:
            heading, roll, pitch = 0, 0, 0
            ax, ay, az = 0, 0, 0

        # CSV形式の文字列を作成
        line = f"{now:.2f},{pressure:.2f},{temp:.2f},{alt:.2f},{heading:.2f},{roll:.2f},{pitch:.2f},{ax:.2f},{ay:.2f},{az:.2f}\n"
        
        # ファイルに書き込み (毎回保存)
        with open(filename, "a") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

        # 動作確認表示
        print(line.strip())
        
    except Exception as e:
        print(f"Loop Error: {e}")

    time.sleep(0.1)
