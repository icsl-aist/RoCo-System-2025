import json # JSONファイルを扱うためのライブラリをインポートします

def load_prompt(path: str) -> dict:
    """
    指定されたファイルパスからJSONファイルを読み込み、Pythonの辞書（dict）として返す関数です。
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt_from_dict(prompt_dict: dict, world_state: dict, history: list, akari_action: str = None) -> str:
    """
    プロンプトのテンプレート（辞書）、ゲーム世界の現在の状態、過去の行動履歴などから、
    AI（LLM）に渡すための最終的な指示文（プロンプト）を文字列として組み立てます。
    """
    parts = []

    # 1. 役割（Role）のセクションを追加
    # .get()を使い、キーが存在しない場合でもエラーにならないようにします
    parts.append(f"== 役割 ==\n{prompt_dict.get('role', '役割未設定')}")

    # 2. 世界の概要（World Overview）のセクションを追加
    # 'initial_position'への直接アクセスを削除し、'goal'のみを安全に取得します
    world_overview = prompt_dict.get("world_overview", {})
    goal = world_overview.get("goal", "（目標未設定）")
    parts.append(f"== 世界の概要 ==\n目標：{goal}")

    # 3. ルール（Rules）のセクションを追加
    # .get()を使い、キーが存在しない場合は空のリストとして扱います
    rules = prompt_dict.get("rules", [])
    parts.append("== ルール ==\n" + "\n".join(rules))

    # 4. 指示文（Instruction）のセクションを作成
    instruction = prompt_dict.get("instruction", "指示がありません。")
    
    history_text = "\n".join([f"- {h['agent']}: {h['action']}" for h in history])
    # world_stateから不要なキーを除外し、見やすく整形します
    world_state_text = ", ".join([f"{k}: {v}" for k, v in world_state.items() if k not in ['history', 'step']])
    
    instruction = instruction.replace("{history}", history_text)
    instruction = instruction.replace("{world_state}", world_state_text)
    
    if akari_action:
        instruction = instruction.replace("{akari_action}", akari_action)
    else:
        # プレースホルダーが残らないように、空文字で置き換えるか、あるいは固定メッセージを入れます
        instruction = instruction.replace("{akari_action}", "（アカリからの先行提案なし）")

    parts.append(instruction)

    # 5. 出力形式（Output Format）のセクションを追加
    output_format = prompt_dict.get("output_format")
    if output_format:
        if isinstance(output_format, list) and output_format and isinstance(output_format[0], dict):
            formatted = [f"- {item.get('name', 'N/A')}: {item.get('description', 'N/A')}" for item in output_format]
            parts.append("\n以下のような形式で答えてください：\n" + "\n".join(formatted))
        elif isinstance(output_format, list):
            parts.append("\n以下のような形式で答えてください：\n" + "\n".join(output_format))

    return "\n\n".join(parts)


def build_speech_prompt_from_command(prompt_dict: dict, command: str) -> str:
    """
    AIが考えた行動コマンドをもとに、自然な日本語のセリフに変換させるための専用のプロンプトを作成します。
    """
    parts = []
    parts.append(f"== 役割 ==\n{prompt_dict.get('role', '')}")
    parts.append(f"== 目標 ==\n{prompt_dict.get('goal', '')}")
    parts.append(f"== ルール ==\n" + "\n".join(prompt_dict.get('rules', [])))

    if "input_format" in prompt_dict:
        parts.append(f"== 入力形式 ==\n{prompt_dict['input_format']}")
    if "output_format" in prompt_dict:
        parts.append(f"== 出力形式 ==\n{prompt_dict['output_format']}")
    
    instruction_text = prompt_dict.get("instruction", "").replace("{command}", command)
    parts.append(instruction_text) 

    return "\n\n".join(parts)