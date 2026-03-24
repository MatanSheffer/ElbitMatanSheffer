import re
import time
from openai import OpenAI, APIStatusError, APIError

import config
from src.database import get_connection
from src.prompts import SQL_SYSTEM_PROMPT, ANSWER_SYSTEM_PROMPT

_client: OpenAI | None = None

MAX_SQL_RETRIES = 1


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=config.GROQ_BASE_URL, api_key=config.GROQ_API_KEY)
    return _client


def _chat(system: str, user: str) -> str:
    resp = _get_client().chat.completions.create(
        model=config.MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    text = resp.choices[0].message.content.strip()
    # Qwen3 may emit <think>...</think> blocks -- strip them
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def _extract_sql(text: str) -> str:
    """Pull SQL out of the LLM response, stripping markdown fences if present."""
    match = re.search(r"```(?:sql)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # No fences -- assume the whole response is SQL
    lines = [l for l in text.splitlines() if not l.startswith("--")]
    return "\n".join(lines).strip()


def _generate_sql(question: str, error_context: str | None = None) -> str:
    prompt = question
    if error_context:
        prompt += f"\n\nהשאילתה הקודמת נכשלה עם השגיאה:\n{error_context}\nנסה שוב."
    raw = _chat(SQL_SYSTEM_PROMPT, prompt)
    return _extract_sql(raw)


MAX_RESULT_ROWS = 30
MAX_RESULT_CHARS = 3000


def _is_geom(val) -> bool:
    s = str(val)
    return s.startswith("POINT(") or s.startswith("POLYGON(") or s.startswith("MULTI")


def _run_query(sql: str) -> str:
    conn = get_connection()
    result = conn.execute(sql)
    cols = [desc[0] for desc in result.description]
    rows = result.fetchall()
    if not rows:
        return "לא נמצאו תוצאות."

    # Filter out geometry columns based on first row values
    keep = [i for i, v in enumerate(rows[0]) if not _is_geom(v)]
    cols = [cols[i] for i in keep]

    header = " | ".join(cols)
    lines = [header, "-" * len(header)]
    truncated = len(rows) > MAX_RESULT_ROWS
    for row in rows[:MAX_RESULT_ROWS]:
        lines.append(" | ".join(str(row[i]) for i in keep))
    if truncated:
        lines.append(f"(... עוד {len(rows) - MAX_RESULT_ROWS} שורות)")

    text = "\n".join(lines)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + "\n(... תוצאות קוצצו)"
    return text


def _format_answer(question: str, sql: str, results: str) -> str:
    user_msg = f"שאלה: {question}\n\nשאילתת SQL:\n{sql}\n\nתוצאות:\n{results}"
    return _chat(ANSWER_SYSTEM_PROMPT, user_msg)


def ask(question: str) -> dict:
    """Full pipeline: question -> SQL -> execute -> answer.
    Returns dict with sql, results, and answer."""

    try:
        sql = _generate_sql(question)
    except APIError as e:
        return {"sql": None, "results": None, "answer": f"שגיאת API: {e.message}"}

    for attempt in range(1 + MAX_SQL_RETRIES):
        try:
            results = _run_query(sql)
            break
        except Exception as e:
            if attempt < MAX_SQL_RETRIES:
                try:
                    sql = _generate_sql(question, error_context=f"SQL: {sql}\nError: {e}")
                except APIError as api_err:
                    return {"sql": sql, "results": None, "answer": f"שגיאת API: {api_err.message}"}
            else:
                return {
                    "sql": sql,
                    "results": None,
                    "answer": f"לא הצלחתי להריץ את השאילתה. שגיאה: {e}",
                }

    try:
        answer = _format_answer(question, sql, results)
    except APIStatusError as e:
        if e.status_code == 413 or "rate_limit" in str(e):
            time.sleep(2)
            try:
                answer = _format_answer(question, sql, results)
            except APIError:
                answer = "התוצאות התקבלו אך לא ניתן לפרמט תשובה (חריגה ממגבלת טוקנים). ראה תוצאות גולמיות למעלה."
        else:
            answer = f"שגיאת API: {e.message}"
    except APIError as e:
        answer = f"שגיאת API: {e.message}"
    return {"sql": sql, "results": results, "answer": answer}
