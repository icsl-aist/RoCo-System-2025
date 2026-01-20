#usage_tokens.py
import datetime

def log_token_usage_from_response(response, log_file_path="token_usage.log"):
    """
    OpenAI API の response からトークン使用量をログファイルに書き出す。
    """
    usage = response.usage  # または response["usage"] （ライブラリによる）
    if usage is None:
        return  # 使用量情報がない場合はスキップ

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    total_tokens = usage.total_tokens

    log_line = f"[{timestamp}] Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}\n"

    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(log_line)
