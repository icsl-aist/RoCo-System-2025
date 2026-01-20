# function_list_akari.py (全文・バグ修正版)

import sys
import json
import paramiko
import shlex
import re # reはもう使いませんが、念のため残します

# ▼▼▼ main.pyが呼び出している関数名・引数に合わせます ▼▼▼
def find_obstacle(_: dict):
    """
    SSH経由で外部スクリプト(kachaka_controll.py)を呼び出し、
    その標準出力(stdout)から座標(JSON)または"NO_OBSTACLE"を受け取る。
    """
    hostname = "172.31.14.46"
    username = "aitclab2011"
    password = "aitclab2011"
    
    remote_project_path = "/home/aitclab2011/test/akari_yolo_inference2(2025.10.2)/final_project"
    remote_script_path = f"{remote_project_path}/kachaka_app/new_kachaka_controll.py"
    remote_python_path = f"{remote_project_path}/kachaka_app/venv_kachaka/bin/python"

    print(f"\n👁️  SSH経由で {remote_script_path.split('/')[-1]} を呼び出します...")
    
    ssh_client = None
    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname, username=username, password=password, timeout=15)
        print(f"  -> ✅ 外部PC ({hostname}) へのSSH接続に成功しました。")

        command_list = [remote_python_path, remote_script_path]
        command = shlex.join(command_list)

        print(f"  -> 実行コマンド: {command}")
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=60)
        
        output = stdout.read().decode().strip()       # データ ("NO_OBSTACLE" または "{...}")
        error_output = stderr.read().decode().strip() # ログ ("Kachakaを初期化します...")

        # --- ▼▼▼【ここから修正】データ(stdout)を最優先でチェックする ▼▼▼

        # 1. 「障害物なし」の場合 (Success)
        if output == "NO_OBSTACLE":
            print("  -> 障害物はありませんでした。")
            if error_output: # ログ(stderr)があっても、データが正しいので成功として扱う
                print(f"  -> (デバッグログ: {error_output})")
            return False, None # 障害物なし

        # 2. 「障害物あり (JSON)」の場合 (Success)
        try:
            shelf_coords = json.loads(output)
            # 念のため、中身が座標データかチェック
            if "x_world" not in shelf_coords or "y_world" not in shelf_coords:
                print(f"💥 受信したJSONに座標キー('x_world')がありません: {output}")
                if error_output: print(f"  -> (エラーログ: {error_output})")
                return False, None

            # 正常にJSONを解析できた場合
            obstacle_info = {
                "id": "S01",
                "coords": shelf_coords,
                "cleared": False
            }
            print(f"  -> ✅ 障害物を発見しました。ワールド座標: {shelf_coords}")
            if error_output: # ログ(stderr)があっても、データが正しいので成功として扱う
                 print(f"  -> (デバッグログ: {error_output})")
            return True, obstacle_info

        except json.JSONDecodeError:
            # 3.「データが空」または「データが不正」で、かつ「ログ(stderr)」がある場合
            # これが「本物のエラー」
            if error_output:
                print(f"💥 外部スクリプトがエラーを返しました:\n{error_output}")
            else:
                # 予期せぬデータがstdoutに来た (例: "NO_OBSTACLE"でもJSONでもない)
                print(f"💥 外部スクリプトが不明なデータを返しました:\n'{output}'")
            return False, None
        
        # --- ▲▲▲【修正完了】▲▲▲

    except Exception as e:
        print(f"💥 SSH接続またはコマンド実行中にエラーが発生しました: {e}")
        return False, None
    finally:
        if ssh_client:
            ssh_client.close()
            print("  -> 🔌 SSH接続を切断しました。")


import paramiko
import shlex

def speak_audio_remote(text: str):
    """
    SSH経由でAKARIPC上の speak_audio.py を実行し、指定されたテキストを話させます。
    (この関数は変更ありません)
    """
    hostname = "172.31.14.46"
    username = "aitclab2011"
    password = "aitclab2011"
    script_path = "/home/aitclab2011/AKARI_llm/speak_audio.py"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Connecting to {hostname} to speak...")
        client.connect(hostname, username=username, password=password, timeout=10)
        print("Connection successful.")

        safe_text = shlex.quote(text)
        
        command = f"source /home/aitclab2011/AKARI_llm/venv_grpc/bin/activate && python3 {script_path} {safe_text}"

        print(f"Executing command: {command}")
        stdin, stdout, stderr = client.exec_command(command)
        
        output = stdout.read().decode()
        error = stderr.read().decode()

        if output:
            print("Output:", output)
        if error:
            print("Error:", error)
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        client.close()
        print("Connection closed.")