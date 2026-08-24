import os

from dotenv import load_dotenv
from openai import OpenAI

from sql_database import execute_query, get_schema
load_dotenv()


LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "gemini-flash-lite-latest",
)

LLM_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)


def create_llm_client():
    if not LLM_API_KEY:
        raise ValueError(
            "LLM_API_KEY is not configured."
        )

    return OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )


def generate_sql(question, client):
    """
    Convert a natural-language question into a SQL SELECT query.
    """

    schema = get_schema()

    system_prompt = f"""
أنت نظام متخصص في تحويل الأسئلة باللغة العربية
إلى استعلامات SQL.

استخدم فقط الجداول والأعمدة الموجودة في قاعدة البيانات.

مخطط قاعدة البيانات:

{schema}

القواعد:

1. أرجع استعلام SQL فقط.
2. استخدم SELECT فقط.
3. لا تستخدم INSERT أو UPDATE أو DELETE.
4. لا تستخدم DROP أو ALTER أو CREATE.
5. لا تخترع جداول أو أعمدة غير موجودة.
6. استخدم JOIN عندما تحتاج بيانات من أكثر من جدول.
7. في أسئلة العدد استخدم COUNT.
8. في أسئلة الإجمالي استخدم SUM.
9. في أسئلة المتوسط استخدم AVG.
10. إذا كان السؤال عن عميل بالاسم، ابحث في customers.name.
11. استخدم القيم الفعلية الموجودة في قاعدة البيانات عند عمل شروط WHERE.
12. لا تترجم قيم status إلى العربية. استخدم القيم الإنجليزية كما هي مخزنة في قاعدة البيانات.
"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": question,
            },
        ],
        temperature=0,
    )

    sql = response.choices[0].message.content.strip()

    # Remove Markdown SQL fences if Gemini adds them.
    if sql.startswith("```"):
        sql = sql.replace("```sql", "")
        sql = sql.replace("```", "")
        sql = sql.strip()

    return sql


def ask_database(question):
    """
    Complete natural-language → SQL → database pipeline.
    """

    client = create_llm_client()

    sql = generate_sql(
        question,
        client,
    )

    print("\nGenerated SQL:")
    print(sql)

    columns, rows = execute_query(sql)

    print("\nDatabase result:")
    print(columns)
    print(rows)

    return sql, columns, rows


if __name__ == "__main__":

    question = input(
        "اكتب سؤالك عن قاعدة البيانات: "
    )

    ask_database(question)