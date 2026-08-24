import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "gemini-flash-lite-latest",
)
LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def create_client():
    if not LLM_API_KEY:
        raise ValueError(
            "LLM_API_KEY is not set."
        )

    return OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )


def route_question(question, client):
    """
    Decide whether a question should be answered
    using the SQL database or the knowledge base.

    Returns:
        "sql"
        or
        "rag"
    """

    system_prompt = """
أنت نظام لتحديد مصدر الإجابة المناسب لسؤال المستخدم.

لديك مصدران:

1. SQL_DATABASE
   يستخدم عندما يسأل المستخدم عن بيانات موجودة
   في قاعدة البيانات، مثل:
   - عدد العملاء
   - أسماء العملاء
   - العملاء النشطين
   - الطلبات
   - قيمة الطلبات
   - حالة الطلبات
   - بيانات مرتبطة بالعملاء والطلبات
   - أي سؤال يحتاج إلى حساب أو فلترة أو JOIN
     على البيانات الموجودة في قاعدة البيانات.

2. KNOWLEDGE_BASE
   يستخدم عندما يسأل المستخدم عن معلومات أو إجراءات
   موجودة في المستندات الداخلية، مثل:
   - خطوات تنفيذ إجراء
   - سياسة الشركة
   - تعليمات خدمة العملاء
   - شرح عملية
   - معلومات من ملفات PDF أو Word أو SOPs.

أعد كلمة واحدة فقط:

SQL

أو:

RAG

لا تضف أي شرح.
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

    result = response.choices[0].message.content.strip().upper()

    if result == "SQL":
        return "sql"

    return "rag"


def main():
    client = create_client()

    question = input(
        "اكتب سؤالك: "
    )

    route = route_question(
        question,
        client,
    )

    print(f"\nRoute: {route}")


if __name__ == "__main__":
    main()
