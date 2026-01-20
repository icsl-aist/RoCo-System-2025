# ==============================================================================
# --- ライブラリのインポート ---
# ==============================================================================
# Pythonの標準ライブラリ
import time  # time.sleep() などで処理を一時停止するために使います
import traceback  # エラーが発生したときに詳細情報を表示するために使います
import math  # 2点間の距離を計算する (math.sqrt) ために使います
# paramiko と shlex は function_list_akari.py 側でインポートされるため、ここでは不要です
 
# 外部ファイル (logic/ フォルダ) から、自作の関数をインポート
# プロンプト（AIへの指示書）を読み込むための関数
from logic.prompt_loader import load_prompt, build_prompt_from_dict
# LLM (大規模言語モデル) のAPIを呼び出し、AIに判断させるための関数
from logic.llm_client import decide_action_with_llm, get_api_call_count, reset_api_counter
# ロボットが「今、世界がどうなっているか」を記憶・管理するための関数
from logic.world_state import initialize_world, update_world_state, get_location
# フォーマット整形のための関数
from logic.formatter import format_world_state_for_display
 
# 外部ファイル (function_list_... フォルダ) から、ロボットの「実際の動作」をインポート
# Kachaka (移動ロボット) の基本動作
from function_list_kachaka import (
    move_to_location,  # 指定した場所へ移動
    dock_shelf,  # シェルフ（棚）とドッキング
    undock_shelf,  # シェルフ（棚）とドッキング解除
    put_away,  # シェルフを元の場所に戻す
    speak_kachaka,  # Kachakaに喋らせる
    move_to_obstacle,  # 障害物シェルフへ移動
    move_to_obstacle_zone,  # 障害物シェルフを待避場所へ移動
    client  # Kachaka本体と通信するためのクライアント
)
# Akari (据え置きロボット) の特殊能力
import function_list_akari as akari_utils  # 障害物をカメラで探す (find_obstacle) など
 
# ==============================================================================
# --- 初期設定 ---
# ==============================================================================
# AIに渡すための「役割設定」や「守るべきルール」が書かれたJSONファイルを読み込みます。
# これがAIの "人格" や "行動指針" になります。
AKARI_PROMPT_DICT = load_prompt("prompts/akari_prompt.json")
KACHAKA_PROMPT_DICT = load_prompt("prompts/kachaka_prompt.json")
 
 
# ==============================================================================
# --- 障害物検知モジュール ---
# ==============================================================================
def Obstacle_Detection_Module(obstacle_info, target_location_name, world_state, threshold=1.5):
    """
    Akariが見つけた障害物が、本当に「今から行こうとしている場所」の経路上にあるか（関連があるか）を判定します。
    """
    print("   -> 障害物検知モジュールを実行...")
    try:
        # 1. 目的地の座標を取得
        dest_pose = world_state["locations"][target_location_name]["kachaka_pose"]
        dest_x, dest_y = dest_pose["x"], dest_pose["y"]
 
        # 2. 障害物の座標を取得
        obs_x = obstacle_info['coords']['x_world']
        obs_y = obstacle_info['coords']['y_world']
        
        # 3. 目的地と障害物の「直線距離」を計算 (三平方の定理)
        distance = math.sqrt((dest_x - obs_x)**2 + (dest_y - obs_y)**2)
        print(f"   -> 目的地 '{target_location_name}' (x={dest_x}, y={dest_y}) と障害物 (x={obs_x}, y={obs_y}) との距離: {distance:.2f}m")
 
        # 4. 距離が「閾値(threshold)」より近いか判定
        if distance < threshold:
            # 近い場合：
            print("   -> 距離が閾値より小さいため、関連する障害物と判断します。")
            # AIの記憶(world_state)に障害物情報を正式に記録する
            world_state["obstacle"] = obstacle_info
            return True  # 「関連あり」と報告
        else:
            # 遠い場合：
            print("   -> 距離が閾値より大きいため、今回の移動タスクとは無関係と判断します。")
            return False  # 「関連なし（無視してOK）」と報告
            
    except KeyError as e:
        # "locations" 辞書に目的地の名前がなかった場合など
        print(f"⚠️  座標の取得に失敗しました: {e}")
        return False
    except Exception as e:
        # その他の予期せぬエラー
        print(f"⚠️  予期せぬエラーが発生しました: {e}")
        return False
 
 
# ==============================================================================
# --- メイン関数 ---
# ==============================================================================
def main():
    """1回分のタスク（例：「冷蔵庫までモノを運ぶ」）を実行し、その結果を辞書で返すメイン関数"""
    
    # --- 初期化 ---
    start_time = time.time()  # タスク開始時刻を記録
    world_state = initialize_world()  # 世界の状態を「最初の状態」に戻す
    MAX_STEPS = 30  # AIが無限に考え続けないよう、最大ステップ数を決めておく
 
    try:
        # --- メインループ ---
        # ステップ数が最大値に達するか、タスクが完了するまで繰り返す
        while world_state['step'] < MAX_STEPS:
            print(f"\n===== Step {world_state['step']} =====")
 
            # --- 1. 現状認識 ---
            # Kachakaの「今いる場所（物理）」を取得し、AIの「記憶（world_state）」に反映する
            current_pose = client.get_robot_pose()
            world_state["kachaka_pose"] = {"x": current_pose.x, "y": current_pose.y, "theta": current_pose.theta}
            
            # 現在のAIの「記憶」をコンソールに表示する
            print(f"状態:\n{format_world_state_for_display(world_state)}")
 
            # --- 2. Akariの思考 ---
            # Akari (司令塔) が次どうすべきか考える
            # 必要な情報 (プロンプト、世界状態、過去の履歴) を渡して、LLM APIを呼び出す
            akari_prompt = build_prompt_from_dict(AKARI_PROMPT_DICT, world_state, world_state["history"])
            akari_action = decide_action_with_llm(akari_prompt).strip()  # AIの回答 (文字列) を受け取る
            
            print(f"🤖 Akariの提案: {akari_action}")

            # --- ▼▼▼ 【！】修正・追加箇所 ▼▼▼ ---
            # Akariの提案を音声で出力する
            try:
                # Akariの提案が「SPEAK at...」でない場合のみ、提案内容を読み上げる
                # (SPEAK at... の場合は、Kachakaが喋るため二重発話を防ぐ)
                if not akari_action.startswith("SPEAK at"):
                    # function_list_akari (akari_utils) 経由で呼び出す
                    akari_utils.speak_audio_remote(akari_action) 
                else:
                    print("   -> (SPEAKアクションのため、Akariの提案読み上げはスキップします)")
            except Exception as e:
                # 音声出力が失敗しても、メインの動作は続行するようにする
                print(f"⚠️  Akariの音声出力に失敗しました: {e}")
            # --- ▲▲▲ 修正ここまで ▲▲▲ ---

            # Akariが何を言ったかを「履歴」に記録する
            world_state["history"].append({"agent": "Akari", "action": akari_action})
 
            # このステップでのアクションが成功したかどうかのフラグ（ひとまず「成功」と仮定）
            action_successful = True
            
            # --- 3. Akariの提案 (アクション) に基づく実行 ---
            
            # アクションが「Kachaka、〜へ運んで」の場合
            if akari_action.startswith("ASK Kachaka to carry to"):
                target_location = akari_action.split()[-1]  # "refrigerator_front" などの目的地名を取得
                
                # ケース1: まだAkari(S02)とドッキングしていない場合
                if not world_state.get("docked_with") == "akari":
                    print(f"  -> 運搬の前に、まずAkari(S02)とドッキングします...")
                    if not dock_shelf("S02", world_state):
                        action_successful = False  # ドッキング失敗
                
                # ケース2: 既にAkariとドッキング済みの場合
                else:
                    print(f"🗺️  ドッキング済みのため、目的地 '{target_location}' への移動前に経路の障害物チェックを強制実行します...")
                    # Akariの「特殊能力」であるカメラで障害物を探す
                    found, obstacle_info = akari_utils.find_obstacle(world_state)
                    
                    if found:
                        # 障害物を発見！
                        print(f"  -> 障害物らしきもの (id={obstacle_info['id']}) を発見。")
                        # それが本当に「関連ある」障害物か、距離で判定する
                        is_relevant = Obstacle_Detection_Module(obstacle_info, target_location, world_state)
                        
                        if is_relevant:
                            # 関連がある場合
                            # AIの記憶(world_state)は更新されたので、AIに「再計画」させる
                            print("   -> 関連する障害物として world_state を更新。AIに再計画を促します。")
                            # このステップではあえて移動しない (action_successfulは True のまま)
                        else:
                            # 関連がない（遠い）障害物の場合
                            print("   -> 障害物は経路上にないと判断。通常の移動を続行します。")
                            if move_to_location(target_location, world_state):
                                world_state = get_location(world_state, target_location, with_akari=True)
                            else:
                                action_successful = False  # 移動失敗
                    else:
                        # 障害物が無かった場合
                        print("🛰️  経路は安全です。通常の移動を開始します。")
                        if move_to_location(target_location, world_state):
                            # 移動成功。AIの記憶(world_state)も更新
                            world_state = get_location(world_state, target_location, with_akari=True)
                        else:
                            action_successful = False  # 移動失敗
 
            # アクションが「Kachaka、〜へ来て」の場合 (Akariを運ばない、Kachaka単独の移動)
            elif akari_action.startswith("CALL Kachaka to"):
                target_location = akari_action.split()[-1]
                if move_to_location(target_location, world_state):
                     world_state = get_location(world_state, target_location, with_akari=False)
                else:
                    action_successful = False
 
            # アクションが「ドッキング解除して」の場合
            elif akari_action == "ASK Kachaka to undock":
                if not undock_shelf(world_state):
                    action_successful = False
 
            # アクションが「〜で喋って」の場合
            elif akari_action.startswith("SPEAK at"):
                 speak_kachaka("目的地に到着しました。")
            
            # --- 4. Kachakaの思考 (Akariの指示が上記以外の場合) ---
            # Akariの指示が曖昧だったり、Kachakaにしかできない専門的な作業（障害物撤去など）だったりした場合
            else:
                 # Kachaka (実行役) が「Akariの指示」をどう解釈して実行するか考える
                 kachaka_prompt = build_prompt_from_dict(KACHAKA_PROMPT_DICT, world_state, world_state["history"], akari_action)
                 raw_action = decide_action_with_llm(kachaka_prompt)
                 kachaka_action = raw_action.strip().lstrip("- ").strip()  # " - DOCK" などを "DOCK" に整形
                 print(f"🚙 Kachakaの応答: {kachaka_action}")
                 
                 # Kachakaの「応答 (アクション)」に基づいて実行
 
                 if kachaka_action == "MOVE to obstacle":
                     # 障害物の場所へ移動
                     if not move_to_obstacle(world_state): action_successful = False
                     world_state = get_location(world_state, "at_obstacle", with_akari=False)
                 
                 elif kachaka_action == "MOVE obstacle to zone":
                     # 障害物を待避場所へ移動
                     if not move_to_obstacle_zone("obstacle_zone", world_state): action_successful = False
                     world_state = get_location(world_state, "obstacle_zone", with_akari=False)
                 
                 # --- ▼▼▼ 【！】ここが修正されたDOCKロジックです ▼▼▼ ---
                 elif kachaka_action.startswith("DOCK"):
                     
                     # まず「未処理の障害物」があるかを確認する
                     obstacle_data = world_state.get("obstacle")
                     is_uncleared_obstacle = False  # デフォルトは「いない」
 
                     if obstacle_data:
                         # 障害物情報があり、かつ
                         # "cleared" フラグが「厳密に False」の場合のみ「未処理」とみなす
                         # (clearedが True や None の場合は「処理済み」または「関係ない」とみなす)
                         if obstacle_data.get("cleared") is False:
                             is_uncleared_obstacle = True
                     
                     
                     if is_uncleared_obstacle:
                         # --- ケースA: 未処理の障害物(S03)にドッキングする場合 ---
                         shelf_to_dock = "S03"
                         target_location_name = "at_obstacle"
                         print(f"  -> {kachaka_action}を検知。障害物(S03)とのドッキングを試みます。")
                         
                         # ドッキングは「移動」と「ドッキング」の2ステップ
                         # 1. まず障害物の場所へ移動
                         print(f"  -> ドッキングのため、まず '{target_location_name}' へ移動します...")
                         if not move_to_obstacle(world_state):
                             action_successful = False
                         else:
                             world_state = get_location(world_state, target_location_name, with_akari=False)
                             
                             # 2. 移動成功後にドッキング
                             print(f"  -> '{target_location_name}' に到着。ドッキングを実行します。")
                             if not dock_shelf(shelf_to_dock, world_state):
                                 action_successful = False
                     
                     else:
                         # --- ケースB: Akari(S02)にドッキングする場合 ---
                         shelf_to_dock = "S02"
                         # Akariが今いる場所 (AIの記憶から) を目的地にする
                         target_location_name = world_state.get("akari_location", "kitchen") # 見つからなければ 'kitchen'
                         print(f"  -> {kachaka_action}を検知。Akari(S02)とのドッキングを試みます。")
                         
                         # 1. まずAkariの場所へ移動
                         print(f"  -> ドッキングのため、まず '{target_location_name}' へ移動します...")
                         if not move_to_location(target_location_name, world_state):
                             action_successful = False
                         else:
                             world_state = get_location(world_state, target_location_name, with_akari=False)
                             
                             # 2. 移動成功後にドッキング
                             print(f"  -> '{target_location_name}' に到着。ドッキングを実行します。")
                             if not dock_shelf(shelf_to_dock, world_state):
                                 action_successful = False
 
                 # --- ▲▲▲ 修正ロジックここまで ▲▲▲ ---
 
                 elif kachaka_action.startswith("UNDOCK"):
                     # ドッキング解除
                     if not undock_shelf(world_state): action_successful = False
                 
                 elif kachaka_action == "WAIT":
                     # 何もしない（様子見）
                     time.sleep(1)
 
            # --- 5. ステップの事後処理 ---
            
            # このステップで「失敗」が起きていた場合
            if not action_successful:
                fail_message = f"アクション '{akari_action}' の実行が失敗しました。再計画します。"
                print(f"🖥️  System: {fail_message}")
                # AIの「履歴」に失敗したことを記録（これを元にAIは次の手を考える）
                world_state["history"].append({"agent": "System", "action": fail_message})
                world_state["step"] += 1  # ステップ数は進める
                time.sleep(1)
                continue  # 次のループ（次のステップ）へ
            
            # --- 6. タスク完了判定 ---
            # このステップのアクションが成功した場合、
            # 「最終的なゴール」を達成したかどうかを判定する
            # (この関数の中で、障害物の 'cleared' フラグを True にする処理なども行われる)
            if update_world_state(world_state, akari_action, ""):
                print("🎉 タスク完了!")
                
                # --- 7. 後片付け処理 ---
                try:
                    print("📦 棚を所定の位置に戻します...")
                    if world_state.get("docked_with"):
                        put_away(world_state)  # ドッキング中なら、棚をホームポジションに戻す
                    print("🔋 Kachakaを充電ドックに戻します...")
                    move_to_location("entrance", world_state)  # Kachakaもホーム（入口）に戻る
                except Exception as e:
                    print(f"⚠️ 後片付け処理でエラーが発生しました: {e}")
                
                return {"success": True}  # main関数を終了
            
            # タスクがまだ完了していない場合
            world_state["step"] += 1  # ステップ数を1つ進める
            time.sleep(0.5)  # 少し待機
 
        # --- ループ終了後 ---
        # whileループが「タスク完了」以外で終了した場合（= MAX_STEPS に達した場合）
        print(f"⚠️ 最大ステップ数 {MAX_STEPS} に達したため、タスク失敗とします。")
        return {"success": False}
    
    except Exception:
        # メインループ全体で予期せぬエラーが起きた場合
        traceback.print_exc()  # エラー詳細を表示
        return {"success": False}
 
# ==============================================================================
# --- スクリプト実行の起点 ---
# ==============================================================================
if __name__ == "__main__":
    """
    このスクリプトが直接実行された時（importされた時ではなく）に、以下の処理を行います。
    """
    reset_api_counter()  # LLM APIの呼び出し回数カウンターをリセット
    result = main()  # メイン関数を実行
    
    # 最終結果を表示
    print("\n--- 実行結果 ---")
    print(result)