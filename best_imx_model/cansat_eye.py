import time
import board
import digitalio
import pwmio
from picamera2 import Picamera2
from picamera2.devices import IMX500

# ==========================================
# 1. モーター設定
# ==========================================
ain1 = digitalio.DigitalInOut(board.D6)
ain2 = digitalio.DigitalInOut(board.D5)
ain1.direction = digitalio.Direction.OUTPUT
ain2.direction = digitalio.Direction.OUTPUT
pwma = pwmio.PWMOut(board.D12, frequency=20000)

bin1 = digitalio.DigitalInOut(board.D22)
bin2 = digitalio.DigitalInOut(board.D23)
bin1.direction = digitalio.Direction.OUTPUT
bin2.direction = digitalio.Direction.OUTPUT
pwmb = pwmio.PWMOut(board.D13, frequency=20000)

def set_motor_speed(motor, throttle):
    throttle = max(-1.0, min(1.0, throttle))
    duty = int(abs(throttle) * 65535)

    if motor == 'A':  # 左モーター
        ain1.value = (throttle > 0)
        ain2.value = (throttle < 0)
        pwma.duty_cycle = duty
    elif motor == 'B':  # 右モーター
        bin1.value = (throttle > 0)
        bin2.value = (throttle < 0)
        pwmb.duty_cycle = duty

def stop_motors():
    set_motor_speed('A', 0)
    set_motor_speed('B', 0)

# ==========================================
# 2. AIテンソル解析
# ==========================================
def parse_direct_tensor(tensor_list):
    # データ数が1801個であることを確認
    if not tensor_list or len(tensor_list) != 1801:
        return None

    # [0] は「AIが確信を持って検出した物体の数」
    num_detections = int(tensor_list[0])
    
    # 1つも見つからなかったら None を返す
    if num_detections == 0:
        return None

    # 見つかった場合、最初の物体（一番信頼度が高いもの）のX座標は [1] にある
    cx = tensor_list[1]
    
    # 画像サイズ(320x320と想定)で 0.0 ~ 1.0 に正規化
    center_x = cx / 320.0
    
    # デバッグ用に検出数も出しておきます
    print(f"🎯 ロックオン (検出数:{num_detections}個) 位置:{center_x:.2f}")
    
    return center_x

def flush_metadata(picam2, flush_count=3):
    """
    カメラのバッファに溜まった古い(ブレた)推論結果を捨てて、
    機体が停止した後の「最新の綺麗な画像」の推論結果を取得する
    """
    meta = None
    for _ in range(flush_count):
        meta = picam2.capture_metadata()
    return meta

# ==========================================
# 3. メイン制御ループ (Stop & Go)
# ==========================================
def main():
    print("AIモデル(network.rpk)を初期化中...")
    imx500 = IMX500("network.rpk")
    picam2 = Picamera2(imx500.camera_num)
    
    config = picam2.create_preview_configuration(main={"size": (640, 480)})
    picam2.configure(config)
    picam2.start()
    
    # 状態の定義
    STATE_SCAN = "SCAN"
    STATE_ALIGN = "ALIGN"
    STATE_DASH = "DASH"
    
    current_state = STATE_SCAN
    lost_counter = 0  # 連続で見失った回数をカウントする変数
    
    # パワー設定
    SEARCH_PWR = 1.0
    TURN_PWR = 0.9
    DRIVE_PWR = 1.0
    
    print("====================================")
    print("🚀 自律追従システム (Stop & Go方式) 起動")
    print("====================================")

    try:
        stop_motors()
        while True:
            # 【重要】AIの推論サイクルに合わせて少し待つ（CPUの負荷低減も兼ねる）
            time.sleep(0.1)
            
            # シンプルに最新のメタデータを1回だけ取得する
            metadata = picam2.capture_metadata()
            cx = None
            
            if 'CnnOutputTensor' in metadata:
                cx = parse_direct_tensor(metadata['CnnOutputTensor'])

            # ---------------------------------------------
            # 【モード1】スキャン（探す）
            # ---------------------------------------------
            if current_state == STATE_SCAN:
                if cx is not None:
                    print(f"\n🎯 コーン発見！(位置:{cx:.2f}) 照準を合わせます。")
                    current_state = STATE_ALIGN
                    lost_counter = 0  # 発見したらカウンターをリセット
                else:
                    # \r を使って同じ行を上書きし、ログが埋まるのを防ぐ
                    print("\r🔄 周囲をスキャン中... (右へ旋回)", end="")
                    set_motor_speed('A',SEARCH_PWR)
                    set_motor_speed('B', -SEARCH_PWR)
                    time.sleep(0.2)
                    stop_motors()
                    time.sleep(0.5)
            
            # ---------------------------------------------
            # 【モード2】アライン（真正面に向く）
            # ---------------------------------------------
            elif current_state == STATE_ALIGN:
                if cx is None:
                    lost_counter += 1
                    # 5回連続（約0.5秒間）見えなかったら「完全に見失った」と判定
                    if lost_counter >= 10:
                        print("\n⚠️ 完全に見失った！スキャンモードに戻ります。")
                        current_state = STATE_SCAN
                    continue
                
                # 見えた場合はカウンターをリセット
                lost_counter = 0
                
                if cx < 0.2:
                    print(f"\r👈 左にズレている (位置:{cx:.2f}) -> ちょい左旋回   ", end="")
                    set_motor_speed('A', -TURN_PWR)
                    set_motor_speed('B', TURN_PWR)
                    time.sleep(0.3)
                    stop_motors()
                    time.sleep(0.3)
                elif cx > 0.8:
                    print(f"\r👉 右にズレている (位置:{cx:.2f}) -> ちょい右旋回   ", end="")
                    set_motor_speed('A', TURN_PWR)
                    set_motor_speed('B', -TURN_PWR)
                    time.sleep(0.3)
                    stop_motors()
                    time.sleep(0.3)
                else:
                    print(f"\n✨ 真正面にロックオン！(位置:{cx:.2f}) ダッシュ準備！")
                    current_state = STATE_DASH
                    
            # ---------------------------------------------
            # 【モード3】ダッシュ（直進）
            # ---------------------------------------------
            elif current_state == STATE_DASH:
                print("🚀 直進ダーッシュ！！！")
                set_motor_speed('A', DRIVE_PWR)
                set_motor_speed('B', DRIVE_PWR)
                time.sleep(5.0)
                stop_motors()
                time.sleep(1.0)
                
                current_state = STATE_ALIGN

    except KeyboardInterrupt:
        print("\nシステムを安全に停止します。")
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
    finally:
        stop_motors()
        picam2.stop()

if __name__ == "__main__":
    main()
