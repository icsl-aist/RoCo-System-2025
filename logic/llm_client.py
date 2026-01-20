import os
from openai import OpenAI
from usage_tokens import log_token_usage_from_response

# OpenAI APIクライアント初期化
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-xxxxxxxxxxxxxxxxxxxxxxxx"))

# === APIコールカウント用変数 ===
_api_call_count = 0

def reset_api_counter():
    """APIコールカウンターをリセットする。"""
    global _api_call_count
    _api_call_count = 0

def get_api_call_count():
    """現在のAPIコール回数を取得する。"""
    return _api_call_count

def decide_action_with_llm(prompt: str) -> str:
    """LLMにプロンプトを送信して応答を得る。"""
    global _api_call_count
    _api_call_count += 1  # 呼び出しごとにカウント

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0
        )
        log_token_usage_from_response(response)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ OpenAI APIエラー: {e}")
        return "WAIT エラー発生中"
