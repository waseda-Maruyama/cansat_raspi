import os
import time
import subprocess
 
SAVE_DIR = "cone_data"
os.makedirs(SAVE_DIR, exist_ok=True)
 
print(f"【データ収集モード】")
print(f"・Enterキー : 写真を撮影")
print(f"・'q' + Enter : 終了")
print(f"保存先ディレクトリ: ./{SAVE_DIR}/\n")
 
count = 1
while True:
    cmd = input(f"[{count}枚目] 撮影待ち (Enterでパシャッ / qで終了): ")
     
    if cmd.lower() == 'q':
        print("撮影を終了する。")
        break
 
    # タイムスタンプでファイル名を一意にする
    filename = f"{SAVE_DIR}/img_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
 
    # libcamera-stillで撮影（プレビューなし、露光時間を安定させるため待ち1ms）
    try:
        subprocess.run(
            ["rpicam-still", "-n", "-t", "1", "-o", filename],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"  -> 保存完了: {filename}\n")
        count += 1
    except subprocess.CalledProcessError as e:
        print(f"  -> [エラー] カメラの呼び出しに失敗した。接続を確認してほしい。")
 
