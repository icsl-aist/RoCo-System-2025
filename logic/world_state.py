# logic/world_state.py (修正後)

def initialize_world():
    """初期の世界状態を定義する関数"""
    return {
        "akari_location": "kitchen",
        "kachaka_location": "entrance",
        "kachaka_pose": None,
        "akari_is_docked": False,
        "docked_with": None,
        "step": 0,
        "history": [],
        "obstacle": None, 
        
        # --- ▼▼▼【ここから追加】目的地の名前と座標の対応リスト ▼▼▼ ---
        "locations": {
            "refrigerator_front": {
                "kachaka_pose": {"x": 5.736, "y": -0.039}
            },
            "kitchen": {
                "kachaka_pose": {"x": 3.11, "y": 0.13}
            },
            "entrance": {
                "kachaka_pose": {"x": 0.0, "y": 0.0}
            },
            "living_room": {
                "kachaka_pose": {"x": 1.739, "y": -0.222}
            }
            # 必要に応じて他の場所も追加できます
            # "table": {
            #     "kachaka_pose": {"x": 3.5, "y": 2.1}
            # },
        }
        # --- ▲▲▲【ここまで追加】▲▲▲ ---
    }

def get_location(world_state: dict, target_location: str, with_akari: bool = False) -> dict:
    """位置情報を更新する関数"""
    world_state["kachaka_location"] = target_location
    if with_akari:
        world_state["akari_location"] = target_location
    return world_state

def update_world_state(world_state: dict, akari_action: str, kachaka_action: str) -> bool:
    """毎ステップの最後に呼び出され、タスクが完了したかを判定する。"""
    
    if world_state.get("docked_with") == "akari":
        world_state["akari_is_docked"] = True
        world_state["akari_location"] = world_state["kachaka_location"]
    else:
        world_state["akari_is_docked"] = False

    if world_state.get("docked_with") == "obstacle" and world_state.get("obstacle"):
        world_state["obstacle"]["location"] = world_state["kachaka_location"]
        if world_state["kachaka_location"] == "obstacle_zone":
            world_state["obstacle"]["cleared"] = True
            print("  -> 障害物シェルフが待避場所に到達したため 'cleared' フラグを立てました。")


    target_loc = world_state.get("target_location")

    if target_loc is None:
        # まだ目的地が決まっていない場合は完了しない
        return False

    # 1. Akariが目的地にいるか？
    akari_at_goal = world_state["akari_location"] == target_loc
    
    # 2. 障害物はクリアされたか？（障害物がない場合もOK）
    obstacle_cleared = not world_state.get("obstacle") or world_state["obstacle"].get("cleared", False)
    akari_spoke_at_goal = False
    if "SPEAK" in akari_action:
        # アクションがSPEAKで、かつAkariの位置がゴールならOK
        if akari_at_goal:
             akari_spoke_at_goal = True

    return akari_at_goal and obstacle_cleared and akari_spoke_at_goal

LOCATION_ID_MAP = {
    "entrance": "home",
    "refrigerator_front": "L01",
    "kitchen": "L02",
    "living_room": "L03",
    "safe_zone": "L04",
    "obstacle_zone": "L05",
    "AKARI": "S02_home",
    "障害物": "S03_home",
}

ID_LOCATION_MAP = {v: k for k, v in LOCATION_ID_MAP.items()}
