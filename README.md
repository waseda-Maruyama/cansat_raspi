**はい、安全かつ確実な手順をご案内します。

「プロセス（実行中のプログラム）の確認」→「古いプロセスの停止」→「新しいプログラムの実行」という流れで行います。

ステップ1：今なにか動いていないか確認する
まず、裏で Python のプログラムが動いたままになっていないか確認します。

Bash

ps aux | grep python
【見方】

出力の中に python3 sensor_loger_and_mission.py や python3 main_mission.py という文字が含まれていたら、まだ動いています。

grep --color=auto python しか出てこなければ、何も動いていません（クリーンな状態です）。

ステップ2：動いているものを確実に止める
もし何か動いていたり、念のためリセットしたい場合は、以下のコマンドですべて強制終了させます。 （これまで作った主要なファイル名を指定して止めます）

Bash

pkill -f sensor_loger_and_mission.py
pkill -f main_mission.py
※ 何も表示されなければ「元々動いていなかった（停止成功）」ということです。

ステップ3：仮想環境に入る
正しい環境（ライブラリが入っている方）に入ります。

Bash

source cansat_env/bin/activate
※ 左側に (cansat_env) と表示されたらOKです。

ステップ4：main_mission.py を nohup で実行
WiFiが切れても止まらないように、かつログ（nav.log）に記録しながら起動します。 -u オプション（リアルタイム表示）を忘れないようにしてください。

Bash

nohup python3 -u main_mission.py > nav.log 2>&1 &
ステップ5：正しく動いたか確認
ログファイルの中身をリアルタイムで覗いてみます。

Bash

tail -f nav.log
【成功のサイン】

モーター初期化中...

✅ GPS & IMU 準備完了

ログ保存開始: /home/cansat/logs/...

📡 GPS測位中... （または座標データ）

これらが流れていれば成功です！ 確認を終えるときは Ctrl+C を押してください（プログラムは止まりません）。**





pkill -f main_mission.py
