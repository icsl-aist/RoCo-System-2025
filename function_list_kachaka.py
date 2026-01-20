# function_list_kachaka.py

import sys
import kachaka_api
import time
import math
from logic.world_state import LOCATION_ID_MAP

try:
    client = kachaka_api.KachakaApiClient("172.31.14.25:26400")
except Exception as e:
    print(f"Kachakaへの接続に失敗しました: {e}")
    sys.exit(1)



# function_list_kachaka.py の dock_shelf 関数

def dock_shelf(shelf_id: str, world_state: dict) -> bool:
    """
    その場で180度回転してシェルフに正対し、ドッキングを行う。
    ドッキング後、対象が正しかったか検証する。
    """
    print(f"\n--- シェルフ '{shelf_id}' へのドッキングシーケンス開始 ---")
    try:
        if shelf_id == "S02":
            print("  -> シェルフに正対するため、180度回転します。")
            client.rotate_in_place(math.pi)
        
        time.sleep(1)
        
        print("  -> ドッキングを実行します。")
        client.dock_shelf()
        print("  -> ドッキング動作完了。")

        # --- ▼▼▼【検証処理】▼▼▼ ---
        
        print("  -> [検証] 状態認識のため1.0秒待機します...")
        time.sleep(1.0) 
        
        actual_docked_shelf_id = client.get_moving_shelf_id()
        print(f"  -> [検証] 期待したID: '{shelf_id}', 実際にドッキングしたID: '{actual_docked_shelf_id}'")

        if actual_docked_shelf_id == shelf_id:
            # (成功) 期待通り
            print("✅ [検証] 成功: 期待したシェルフと正しくドッキングしました。")
            
            if shelf_id == "S02":
                world_state["docked_with"] = "akari"
                world_state["akari_is_docked"] = True
            else:
                world_state["docked_with"] = "obstacle"
            print(f"  -> world_stateを更新しました: docked_with = '{world_state['docked_with']}'")
            return True # アクション成功
        
        else:
            # (失敗) 意図しない棚とドッキング
            print(f"💥 [検証] 失敗: 期待した '{shelf_id}' ではなく '{actual_docked_shelf_id}' とドッキングしました。")
            
            # --- ▼▼▼【ハイブリッドアプローチ】▼▼▼ ---
            # 1. 現実を world_state に更新する
            if actual_docked_shelf_id == "S03": # main.pyのロジックに合わせる
                world_state["docked_with"] = "obstacle"
                world_state["akari_is_docked"] = False
                print(f"  -> world_stateを現実の 'obstacle' に更新しました。")
            elif actual_docked_shelf_id == "S02":
                 world_state["docked_with"] = "akari"
                 world_state["akari_is_docked"] = True
                 print(f"  -> world_stateを現実の 'akari' に更新しました。")
            else:
                # どの棚か認識できなかった (IDが空など)
                world_state["docked_with"] = None
                world_state["akari_is_docked"] = False
                print(f"  -> world_stateを 'None' (ドッキング失敗) に更新しました。")

            # 2. "意図したアクション"は失敗したと通知する
            return False # アクション失敗
            # --- ▲▲▲【ハイブリッドアプローチ】▲▲▲ ---

    except Exception as e:
        print(f"💥 ドッキングシーケンス全体でエラーが発生しました: {e}")
        # 例外発生時も world_state を安全な状態に戻す
        world_state["docked_with"] = None
        world_state["akari_is_docked"] = False
        return False

def undock_shelf(world_state: dict) -> bool:
    """ドッキングを解除する。"""
    print("アンドックを開始します。")
    if not world_state.get("docked_with"):
        print("🤔 既にアンドック状態のため、処理をスキップします。")
        return True
    try:
        client.undock_shelf()
        print("✅ アンドック成功。")
        world_state["docked_with"] = None
        world_state["akari_is_docked"] = False
        return True
    except Exception as e:
        print(f"💥 アンドック中に予期せぬエラーが発生しました: {e}")
        return False

def move_to_location(target_location: str, world_state: dict) -> bool:
    """名前で指定された場所('living_room'など)に移動する。"""
    if target_location not in LOCATION_ID_MAP:
        print(f"場所 '{target_location}' に対応するIDが見つかりません。")
        return False
    location_id = LOCATION_ID_MAP[target_location]
    print(f"Kachakaを '{target_location}' ({location_id}) に移動させます。")
    try:
        client.move_to_location(location_id)
        print(f"✅ '{target_location}'への移動完了。")
        return True
    except Exception as e:
        print(f"💥 移動中に予期せぬエラー: {e}")
        return False

def speak_kachaka(text: str):
    """Kachakaに指定されたテキストを発話させる。"""
    print(f"💬 Kachaka says: {text}")
    try:
        client.speak(text)
    except Exception as e:
        print(f"スピーカー出力エラー: {e}")

def put_away(world_state: dict) -> bool:
    """現在ドッキング中の家具をホームポジションに片付ける。"""
    print("ドッキング中の家具を片付けます。")
    try:
        client.return_shelf()
        print("✅ 片付け完了。")
        world_state["docked_with"] = None
        return True
    except Exception as e:
        print(f"💥 片付けに失敗しました。エラー: {e}")
        return False

DOCKING_APPROACH_DISTANCE = 0.6

def move_to_obstacle(world_state: dict) -> bool:
    """world_stateに記録された障害物の座標に向かって移動する。"""
    print("\n--- 障害物への接近シーケンス開始 ---")
    obstacle_info = world_state.get("obstacle")
    if not obstacle_info or "coords" not in obstacle_info:
        print("💥 エラー: world_stateに障害物の座標情報がありません。")
        return False
    
    obstacle_coords = obstacle_info["coords"]
    x_shelf_world = obstacle_coords["x_world"]
    y_shelf_world = obstacle_coords["y_world"]
    try:
        print(f"  -> 障害物のある座標 (X={x_shelf_world:.2f}, Y={y_shelf_world:.2f}) へ移動します。")
        kachaka_pose = client.get_robot_pose()
        delta_y, delta_x = y_shelf_world - kachaka_pose.y, x_shelf_world - kachaka_pose.x
        target_yaw = math.atan2(delta_y, delta_x)
        target_x = x_shelf_world - DOCKING_APPROACH_DISTANCE * math.cos(target_yaw)
        target_y = y_shelf_world - DOCKING_APPROACH_DISTANCE * math.sin(target_yaw)
        client.move_to_pose(target_x, target_y, target_yaw)
        print("✅ 障害物への接近完了。")
        return True
    except Exception as e:
        print(f"💥 障害物への移動中にエラーが発生しました: {repr(e)}")
        return False

# function_list_kachaka.py の修正箇所

# def move_obstacle_to_zone(world_state: dict) -> bool:
#     """現在ドッキングしている障害物シェルフを、指定の障害物置き場へ移動させる。"""
#     print("\n--- 障害物の退避シーケンス開始 ---")
#     if not world_state.get("docked_with") == "obstacle":
#         print("💥 エラー: 障害物とドッキングしていません。")
#         return False

#     obstacle_zone_id = LOCATION_ID_MAP["obstacle_zone"]
    
#     # ▼▼▼【重要】APIからIDを取得するのではなく、world_stateから取得する▼▼▼
#     obstacle_shelf_id = world_state.get("obstacle", {}).get("id")
#     if not obstacle_shelf_id:
#          print("💥 エラー: world_stateから障害物IDが取得できませんでした。")
#          return False
#     # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

#     try:
#         print(f"  -> 障害物 ({obstacle_shelf_id}) を '{obstacle_zone_id}' へ移動させます。")
#         client.move_shelf(obstacle_shelf_id, obstacle_zone_id)
        
#         if world_state.get("obstacle"):
#             world_state["obstacle"]["cleared"] = True
#         print("✅ 障害物の退避完了。")
#         return True
#     except Exception as e:
#         print(f"💥 障害物の退避中にエラーが発生しました: {repr(e)}")
#         return False
    
def move_to_obstacle_zone(target_location, world_state: dict) -> bool:
    """障害物をobstacle_zoneに移動し、その場でアンドックする"""
    print("--- 障害物の退避シーケンス開始 ---")
    try:
        # 1. 障害物置き場へ移動
        if not move_to_location(target_location, world_state):
            # move_to_locationが失敗した場合、ここで終了
            return False
        
        # --- ▼▼▼【修正】▼▼▼ ---
        # 2. 移動直後に「間」を設ける
        print("  -> 移動完了。アンドックの準備のため1秒待機します。")
        time.sleep(1) 
        # --- ▲▲▲【修正】▲▲▲ ---

        # 3. その場でアンドックする
        print("  -> 障害物置き場でアンドックします。")
        if not undock_shelf(world_state):
            print("  -> 障害物とのアンドックに失敗しました。")
            return False
        
        print("✅ 障害物の退避とアンドックが完了しました。")
        world_state["obstacle"]["cleared"] = True
        return True


    except Exception as e:
        # move_to_location以外の予期せぬエラー
        print(f"💥 障害物退避シーケンス中に予期せぬエラー: {e}")
        return False