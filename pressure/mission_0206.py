import time
import board
import pwmio
import adafruit_dps310
import os
import sys
from datetime import datetime

# ==========================================
# 設定
# ==========================================
OFFSET_FILE = "/home/yuki/cansat_raspi/pressure/offset.txt"
WAIT_TIME = 0.1             # ループ間隔(秒)

# --- 高度設定 ---
# 1. 機能有効化高度 (ARMING)
#    この高さを超えるまでは、絶対にニクロム線は作動しません。
#    地上での誤作動を防ぐため、ターゲット高度より高く設定してください。
ARM_ALTITUDE = 10.0

# 2. 作動高度 (TARGET)
#    ARMED状態で、この高さを「下回ったら」加熱します。
TARGET_ALTITUDE = 5.0

# --- ニクロム線設定 ---
NICROME_PIN = board.D4
DUTY_CYCLE_PERCENT = 0.2    # 20%出力 (0.8Ωなら約4.6A)
BURN_TIME = 3.0             # 3秒間加熱 (念のため少し長めに)

# ログ設定
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)
csv_file = f"{LOG_DIR}/flight_release_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# ニクロム線 初期化 (初期状態は必ずOFF)
nicrome = pwmio.PWMOut(NICROME_PIN, frequency=100, duty_cycle=0)

# 状態フラグ
is_armed = False  # 上空に到達したか？
is_fired = False  # すでに発火したか？

print("--- フライトシステム (安全機構付き 投下モード) ---")
print(f"設定: {ARM_ALTITUDE}m 以上でロック解除 -> {TARGET_ALTITUDE}m 以下で加熱")
print(f"出力: {DUTY_CYCLE_PERCENT*100}% / {BURN_TIME}秒")

# 1. 基準値(オフセット)の読み込み
base_altitude = 0.0
if os.path.exists(OFFSET_FILE):
    try:
        with open(OFFSET_FILE, "r") as f:
            content = f.read().strip()
            base_altitude = float(content)
        print(f"✅ 設定ファイルを読み込みました: 基準 = {base_altitude:.2f} m")
    except ValueError:
        print("⚠️ 設定ファイルが破損しています。基準 = 0.0m で開始します。")
else:
    print("⚠️ 設定ファイル(offset.txt)が見つかりません。")
    print("   基準 = 0.0m (海抜0m想定) で開始します。")

# 2. センサ初期化
try:
    i2c = board.I2C()
    dps = adafruit_dps310.DPS310(i2c, address=0x77)
except Exception as e:
    print(f"❌ センサエラー: {e}")
    nicrome.deinit()
    sys.exit()

# CSVヘッダー
with open(csv_file, 'w') as f:
    f.write("Time,Pressure_hPa,Abs_Alt_m,Rel_Alt_m,State,Status_Message\n")

print("監視を開始します...")

# 3. メインループ
try:
    while True:
        try:
            press = dps.pressure
            # 現在の絶対高度
            abs_alt = 44330 * (1.0 - (press / 1013.25) ** 0.1903)
            # 相対高度 (現在 - 基準)
            rel_alt = abs_alt - base_altitude

            status_msg = ""
            state_code = "STANDBY"

            # === 状態判定ロジック ===

            # 1. まだARMED(ロック解除)されていない場合、高度をチェック
            if not is_armed:
                if rel_alt > ARM_ALTITUDE:
                    is_armed = True
                    print(f"🚀 上昇検知！ ロック解除 (高度: {rel_alt:.2f}m > {ARM_ALTITUDE}m)")
                    status_msg = "ARMED just now"
                    state_code = "ARMED"
                else:
                    state_code = "STANDBY"
                    status_msg = f"Waiting for ascent (> {ARM_ALTITUDE}m)"

            # 2. ロック解除済み、かつ未発火の場合
            elif is_armed and not is_fired:
                state_code = "ARMED"
                
                # 発火条件チェック
                if rel_alt < TARGET_ALTITUDE:
                    print(f"🔥 降下検知！ ニクロム線加熱開始 (高度: {rel_alt:.2f}m < {TARGET_ALTITUDE}m)")
                    state_code = "BURNING"
                    status_msg = "Heating Nicrome..."
                    
                    # ログ記録 (加熱開始)
                    with open(csv_file, 'a') as f:
                        f.write(f"{datetime.now()},{press:.2f},{abs_alt:.2f},{rel_alt:.2f},{state_code},{status_msg}\n")

                    # === 加熱実行 (ブロッキング) ===
                    nicrome.duty_cycle = int(65535 * DUTY_CYCLE_PERCENT)
                    time.sleep(BURN_TIME)
                    nicrome.duty_cycle = 0
                    
                    is_fired = True
                    print("✅ 加熱完了・停止")
                    status_msg = "Fired Successfully"
                    state_code = "FIRED"
                else:
                    status_msg = f"Descending... (Target: < {TARGET_ALTITUDE}m)"

            # 3. 発火済みの場合
            else:
                state_code = "FIRED"
                status_msg = "Mission Complete"

            # ==========================

            # ログ保存
            with open(csv_file, 'a') as f:
                f.write(f"{datetime.now()},{press:.2f},{abs_alt:.2f},{rel_alt:.2f},{state_code},{status_msg}\n")

            # コンソール表示
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Alt: {rel_alt:6.2f}m | State: {state_code} | {status_msg}")

            time.sleep(WAIT_TIME)

        except OSError:
            continue

except KeyboardInterrupt:
    print("\n停止")
except Exception as e:
    print(f"エラー: {e}")
finally:
    nicrome.duty_cycle = 0
    nicrome.deinit()
    print("Safe Shutdown")
