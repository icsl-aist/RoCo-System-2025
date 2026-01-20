# main_with_metrics.py
# (main.py のロジック + main2.py の計測機能)

# ==============================================================================
# --- ライブラリのインポート ---
# ==============================================================================
import time
import traceback
import math  # ★ 距離計算のために追加
import re    # ★ 計測のため追加

# 外部ファイルから、プロンプトの組み立てやLLM APIの呼び出しに必要な関数をインポート
from logic.prompt_loader import load_prompt, build_prompt_from_dict
from logic.llm_client import decide_action_with_llm, get_api_call_count, reset_api_counter
# 外部ファイルから、世界の「状態」を管理するための関数をインポート
from logic.world_state import initialize_world, update_world_state, get_location, format_world_state_for_display
# 外部ファイルから、Kachakaの物理的な「基本動作」を定義した関数群をインポート
from function_list_kachaka import (
    move_to_location,
    dock_shelf,
    undock_shelf,
    put_away,
    speak_kachaka,
    move_to_obstacle,
    move_to_obstacle_zone,
    client  # Kachakaとの通信クライアントもインポート
)
# 外部ファイルから、Akariの「特殊能力」を定義した関数をインポート
import function_list_akari as akari_utils

# ==============================================================================
# --- 初期設定 ---
# ==============================================================================
# (変更なし)
AKARI_PROMPT_DICT = load_prompt("prompts/akari_prompt.json")
KACHAKA_PROMPT_DICT = load_prompt("prompts/kachaka_prompt.json")

# ==============================================================================
# --- ★計測用：ログファイル読み取りモジュール (main2.pyから移植) ---
# ==============================================================================

TOKEN_LOG_FILE = "token_usage.log" 
token_pattern = re.compile(r"Prompt: (\d+), Completion: (\d+), Total: (\d+)")

def get_last_token_usage_from_log():
    """
    token_usage.log ファイルの *最終行* を読み取り、トークン数を取得する。
    """
    try:
        with open(TOKEN_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if not lines:
                return None
            
            last_line = lines[-1].strip()
            match = token_pattern.search(last_line)
            
            if match:
                prompt_tokens = int(match.group(1))
                completion_tokens = int(match.group(2))
                total_tokens = int(match.group(3))
                return {
                    "prompt": prompt_tokens,
                    "completion": completion_tokens,
                    "total": total_tokens
                }
            else:
                print(f"⚠️  トークンログのパースに失敗 (最終行: {last_line})")
                return None
                
    except FileNotFoundError:
        print(f"⚠️  トークンログファイル {TOKEN_LOG_FILE} が見つかりません。")
        return None
    except Exception as e:
        print(f"⚠️  トークンログファイルの読み取り中にエラー: {e}")
        return None

# ==============================================================================
# --- 障害物検知モジュール (main.pyのものをそのまま使用) ---
# ==============================================================================
def Obstacle_Detection_Module(obstacle_info, target_location_name, world_state, threshold=1.5):
    """
    障害物の座標と目的地の座標を比較し、その差が小さい場合は障害物情報を記憶・更新する。
    """
    print("   -> 障害物検知モジュールを実行...")
    try:
        dest_pose = world_state["locations"][target_location_name]["kachaka_pose"]
        dest_x, dest_y = dest_pose["x"], dest_pose["y"]

        obs_x = obstacle_info['coords']['x_world']
        obs_y = obstacle_info['coords']['y_world']
        
        distance = math.sqrt((dest_x - obs_x)**2 + (dest_y - obs_y)**2)
        print(f"   -> 目的地 '{target_location_name}' (x={dest_x}, y={dest_y}) と障害物 (x={obs_x}, y={obs_y}) との距離: {distance:.2f}m")

        if distance < threshold:
            print("   -> 距離が閾値より小さいため、関連する障害物と判断します。")
            world_state["obstacle"] = obstacle_info
            return True
        else:
            print("   -> 距離が閾値より大きいため、今回の移動タスクとは無関係と判断します。")
            return False
    except KeyError as e:
        print(f"⚠️  座標の取得に失敗しました: {e}")
        return False
    except Exception as e:
        print(f"⚠️  予期せぬエラーが発生しました: {e}")
        return False


# ==============================================================================
# --- メイン関数 (main.py のロジック + main2.py の計測) ---
# ==============================================================================
def main():
    """1回分のタスクを実行し、その結果を辞書で返すメイン関数"""
    
    # --- ★計測用の変数初期化 ---
    total_run_time_start = time.time()
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_llm_tokens = 0
    # ---
    
    world_state = initialize_world()
    MAX_STEPS = 30 

    try:
        while world_state['step'] < MAX_STEPS:
            
            # --- ★ステップごとの計測開始 ---
            step_start_time = time.time()
            step_prompt_tokens = 0
            step_completion_tokens = 0
            step_total_tokens = 0
            # ---

            print(f"\n===== Step {world_state['step']} =====")

            current_pose = client.get_robot_pose()
            world_state["kachaka_pose"] = {"x": current_pose.x, "y": current_pose.y, "theta": current_pose.theta}
            
            print(f"状態:\n{format_world_state_for_display(world_state)}")

            akari_prompt = build_prompt_from_dict(AKARI_PROMPT_DICT, world_state, world_state["history"])
            
            # --- LLM呼び出し (Akari) ---
            akari_action = decide_action_with_llm(akari_prompt).strip()
            
            # --- ★トークン計測 (Akari) ---
            tokens = get_last_token_usage_from_log()
            if tokens:
                step_prompt_tokens += tokens["prompt"]
                step_completion_tokens += tokens["completion"]
                step_total_tokens += tokens["total"]
            # ---

            print(f"🤖 Akariの提案: {akari_action}")
            
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

            world_state["history"].append({"agent": "Akari", "action": akari_action})

            action_successful = True
            
            # === ▼ main.py のロジック (変更なし) ▼ ===
            
            if akari_action.startswith("ASK Kachaka to carry to"):
                target_location = akari_action.split()[-1]

                world_state["target_location"] = target_location
                
                # ★ここが main.py 固有のロジック
                if not world_state.get("docked_with") == "akari":
                    if not dock_shelf("S02", world_state):
                        action_successful = False
                # ★ここまで
                else:
                    print(f"🗺️  ドッキング済みのため、目的地 '{target_location}' への移動前に経路の障害物チェックを強制実行します...")
                    found, obstacle_info = akari_utils.find_obstacle(world_state)
                    
                    if found:
                        is_relevant = Obstacle_Detection_Module(obstacle_info, target_location, world_state)
                        if is_relevant:
                            print("   -> 関連する障害物として world_state を更新。AIに再計画を促します。")
                        else:
                            print("   -> 障害物は経路上にないと判断。通常の移動を続行します。")
                            if move_to_location(target_location, world_state):
                                world_state = get_location(world_state, target_location, with_akari=True)
                            else:
                                action_successful = False
                    else:
                        print("🛰️  経路は安全です。通常の移動を開始します。")
                        if move_to_location(target_location, world_state):
                            world_state = get_location(world_state, target_location, with_akari=True)
                        else:
                            action_successful = False

            elif akari_action.startswith("CALL Kachaka to"):
                target_location = akari_action.split()[-1]
                if move_to_location(target_location, world_state):
                     world_state = get_location(world_state, target_location, with_akari=False)
                else:
                    action_successful = False

            elif akari_action == "ASK Kachaka to undock":
                if not undock_shelf(world_state):
                    action_successful = False

            elif akari_action.startswith("SPEAK at"):
                 speak_kachaka("目的地に到着しました。")
            
            else:
                 kachaka_prompt = build_prompt_from_dict(KACHAKA_PROMPT_DICT, world_state, world_state["history"], akari_action)
                 
                 # --- LLM呼び出し (Kachaka) ---
                 raw_action = decide_action_with_llm(kachaka_prompt)
                 
                 # --- ★トークン計測 (Kachaka) ---
                 tokens = get_last_token_usage_from_log()
                 if tokens:
                     step_prompt_tokens += tokens["prompt"]
                     step_completion_tokens += tokens["completion"]
                     step_total_tokens += tokens["total"]
                 # ---

                 kachaka_action = raw_action.strip().lstrip("- ").strip()
                 print(f"🚙 Kachakaの応答: {kachaka_action}")

                 if kachaka_action == "MOVE to obstacle":
                     if not move_to_obstacle(world_state): action_successful = False
                     world_state = get_location(world_state, "at_obstacle", with_akari=False)
                 elif kachaka_action == "MOVE obstacle to zone":
                     if not move_to_obstacle_zone("obstacle_zone", world_state): action_successful = False
                     world_state = get_location(world_state, "obstacle_zone", with_akari=False)
                 
                 # ★ここが main.py 固有のロジック
                 elif kachaka_action.startswith("DOCK"):
                     is_uncleared_obstacle = (
                         world_state.get("obstacle") and 
                         not world_state.get("obstacle").get("cleared")
                     )
                     shelf_to_dock = "S03" if is_uncleared_obstacle else "S02"
                     print(f"  -> {kachaka_action}を検知。ドッキング対象: {shelf_to_dock}")
                     if not dock_shelf(shelf_to_dock, world_state): 
                         action_successful = False
                 # ★ここまで
                 
                 elif kachaka_action.startswith("UNDOCK"):
                     if not undock_shelf(world_state): action_successful = False
                 elif kachaka_action == "WAIT":
                     time.sleep(1)

            # === ▲ main.py のロジック (変更なし) ▲ ===


            # --- ★ステップごとの計測結果を集計＆出力 ---
            step_end_time = time.time()
            step_duration = step_end_time - step_start_time
            
            total_prompt_tokens += step_prompt_tokens
            total_completion_tokens += step_completion_tokens
            total_llm_tokens += step_total_tokens
            
            print(f"   -> [計測] Step {world_state['step']} 所要時間: {step_duration:.2f}s")
            print(f"   -> [計測] Step {world_state['step']} トークン数: {step_total_tokens} (Prompt: {step_prompt_tokens}, Completion: {step_completion_tokens})")
            # ---

            if not action_successful:
                fail_message = f"アクション '{akari_action}' の実行が失敗しました。再計画します。"
                print(f"🖥️  System: {fail_message}")
                world_state["history"].append({"agent": "System", "action": fail_message})
                world_state["step"] += 1
                time.sleep(1)
                continue
            
            if update_world_state(world_state, akari_action, ""):
                print("🎉 タスク完了!")
                # try:
                #     print("📦 棚を所定の位置に戻します...")
                #     if world_state.get("docked_with"):
                #         put_away(world_state)
                #     print("🔋 Kachakaを充電ドックに戻します...")
                #     move_to_location("entrance", world_state)
                # except Exception as e:
                #     print(f"⚠️ 後片付け処理でエラーが発生しました: {e}")
                
                # --- ★★★ 合計計測結果の出力 (成功時) ★★★ ---
                total_run_time_end = time.time()
                total_duration = total_run_time_end - total_run_time_start
                print("\n--- 📈 実行結果 (計測サマリー) ---")
                print(f"   結果: 成功 (Success)")
                print(f"   合計所要時間: {total_duration:.2f} 秒")
                print(f"   合計ステップ数: {world_state['step']}")
                print(f"   合計LLMトークン数: {total_llm_tokens}")
                print(f"     (Prompt: {total_prompt_tokens}, Completion: {total_completion_tokens})")
                print("---------------------------------")
                # ---
                
                return {"success": True}
            
            world_state["step"] += 1
            time.sleep(0.5)

        # --- ★★★ 合計計測結果の出力 (失敗時: 最大ステップ) ★★★ ---
        print(f"⚠️ 最大ステップ数 {MAX_STEPS} に達したため、タスク失敗とします。")
        total_run_time_end = time.time()
        total_duration = total_run_time_end - total_run_time_start
        print("\n--- 📈 実行結果 (計測サマリー) ---")
        print(f"   結果: 失敗 (Failure - Max Steps)")
        print(f"   合計所要時間: {total_duration:.2f} 秒")
        print(f"   合計ステップ数: {world_state['step']}")
        print(f"   合計LLMトークン数: {total_llm_tokens}")
        print(f"     (Prompt: {total_prompt_tokens}, Completion: {total_completion_tokens})")
        print("---------------------------------")
        # ---

        return {"success": False}
    
    except Exception:
        # --- ★★★ 合計計測結果の出力 (失敗時: 例外) ★★★ ---
        traceback_str = traceback.format_exc()
        print(traceback_str)
        
        total_run_time_end = time.time()
        total_duration = total_run_time_end - total_run_time_start
        print("\n--- 📈 実行結果 (計測サマリー) ---")
        print(f"   結果: 失敗 (Failure - Exception)")
        print(f"   合計所要時間: {total_duration:.2f} 秒")
        print(f"   合計ステップ数: {world_state.get('step', 'N/A')}")
        print(f"   合計LLMトークン数: {total_llm_tokens}")
        print(f"     (Prompt: {total_prompt_tokens}, Completion: {total_completion_tokens})")
        print("---------------------------------")
        # ---
        
        return {"success": False}

if __name__ == "__main__":
    reset_api_counter()
    result = main()
    print("\n--- 実行結果 ---"); print(result)