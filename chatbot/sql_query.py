from text_to_sql import generate_sql
from sql_database import execute_query

def format_sql_result(
    question,
    sql,
    columns,
    rows,
    client,
):
    """
    Convert a SQL database result into a natural
    Arabic answer.
    """

    if not rows:
        return "لم يتم العثور على بيانات مطابقة لسؤالك."

    result_text = "\n".join(
        str(dict(zip(columns, row)))
        for row in rows
    )

    system_prompt = """
أنت مساعد داخلي لخدمة العملاء.

مهمتك تحويل نتيجة استعلام SQL إلى إجابة عربية
واضحة ومباشرة على سؤال المستخدم.

القواعد:
- اعتمد فقط على نتيجة قاعدة البيانات.
- لا تخترع أي معلومات.
- لا تذكر SQL للمستخدم.
- أجب باللغة العربية.
- إذا كانت النتيجة رقمًا، اذكر الرقم بوضوح.
- إذا كانت هناك عدة سجلات، اعرض المعلومات المهمة بشكل منظم.
- كن مختصرًا ومهنيًا.
"""

    user_prompt = f"""
سؤال المستخدم:
{question}

استعلام SQL المستخدم:
{sql}

أعمدة النتيجة:
{columns}

نتيجة قاعدة البيانات:
{result_text}

اكتب الإجابة النهائية بالعربية.
"""

    response = client.chat.completions.create(
        model="gemini-flash-lite-latest",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()


def process_sql_question(question, client):
    """
    Complete natural-language SQL pipeline.

    Returns:
        sql, columns, rows, answer
    """

    try:
        sql = generate_sql(
            question,
            client,
        )

    except Exception as exc:
        print(f"[ERROR] Text-to-SQL failed: {exc}")

        return (
            None,
            [],
            [],
            "عذرًا، لم أتمكن من فهم السؤال الخاص بقاعدة البيانات. "
            "يرجى إعادة صياغة السؤال والمحاولة مرة أخرى."
        )

    try:
        columns, rows = execute_query(
            sql
        )

    except ValueError as exc:
        print(
            f"[ERROR] SQL validation failed: {exc}"
        )

        return (
            sql,
            [],
            [],
            "عذرًا، لم أتمكن من تنفيذ هذا السؤال "
            "بشكل آمن على قاعدة البيانات."
        )

    except Exception as exc:
        print(
            f"[ERROR] SQL execution failed: {exc}"
        )

        return (
            sql,
            [],
            [],
            "عذرًا، حدث خطأ أثناء الوصول إلى قاعدة البيانات. "
            "يرجى المحاولة مرة أخرى."
        )

    try:
        answer = format_sql_result(
            question,
            sql,
            columns,
            rows,
            client,
        )

    except Exception as exc:
        print(
            f"[ERROR] SQL result formatting failed: {exc}"
        )

        return (
            sql,
            columns,
            rows,
            "تم الحصول على البيانات، ولكن تعذر تنسيق الإجابة."
        )

    return (
        sql,
        columns,
        rows,
        answer,
    )