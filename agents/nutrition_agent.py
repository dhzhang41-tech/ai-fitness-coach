from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME


def estimate_protein_from_text(food_desc: str) -> float:
    """
    输入食物描述，返回估算蛋白质克数（float）。
    只返回数字，调用失败返回 0.0。
    """
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是营养估算助手。"
                        "用户描述吃了什么食物，"
                        "你只需要返回一个整数，"
                        "代表这些食物总共含有多少克蛋白质。"
                        "不要返回任何其他文字，只返回数字。"
                        "如果无法估算返回0。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"这些食物含多少克蛋白质：{food_desc}",
                },
            ],
            max_tokens=10,
            temperature=0,
        )
        result = response.choices[0].message.content.strip()
        return float(result)
    except Exception:
        return 0.0
