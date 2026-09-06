"""
Simulated CRM lookup: a stand-in for a real customer-records system.
In a real deployment this would be a database query against your actual CRM
(ticket ID, prior call notes, etc.) -- here it's a small hardcoded dict so the
outbound call greeting can be genuinely dynamic per customer, proving the
concept without needing a real CRM integration.

Each customer is tagged with organization_id, matching the same multi-tenant
boundary used for documents -- an agent logged into one company should only
ever see and call that company's own customers.
"""

CUSTOMERS = {
    "201149192315": {
        "name": "أحمد",
        "ticket_id": "TCK-4471",
        "issue": "مشكلة في تسجيل الدخول للحساب",
        "organization_id": 1,
    },
    "201207756337": {
        "name": "سارة",
        "ticket_id": "TCK-5820",
        "issue": "استفسار عن باقة البيانات",
        "organization_id": 1,
    },
    "201155566677": {
        "name": "محمود",
        "ticket_id": "TCK-6193",
        "issue": "شكوى ضعف تغطية الشبكة",
        "organization_id": 1,
    },
    "201227788990": {
        "name": "منى",
        "ticket_id": "TCK-6304",
        "issue": "استفسار عن فاتورة متأخرة",
        "organization_id": 1,
    },
    "201099887766": {
        "name": "خالد",
        "ticket_id": "TCK-6421",
        "issue": "استبدال شريحة SIM تالفة",
        "organization_id": 2,
    },
    "201288776655": {
        "name": "ياسمين",
        "ticket_id": "TCK-6558",
        "issue": "عطل في الراوتر المنزلي",
        "organization_id": 2,
    },
    "201033445566": {
        "name": "عمر",
        "ticket_id": "TCK-6670",
        "issue": "مشكلة تفعيل خدمة التجوال",
        "organization_id": 2,
    },
    "201211223344": {
        "name": "نور",
        "ticket_id": "TCK-6789",
        "issue": "اعتراض على قيمة الفاتورة",
        "organization_id": 2,
    },
}


def lookup_customer(phone_number):
    """Returns the customer record for a phone number, or None if unknown."""
    return CUSTOMERS.get(phone_number)


def get_customers_by_organization(organization_id):
    """Returns {phone_number: record} for just this organization's customers."""
    return {
        phone: record
        for phone, record in CUSTOMERS.items()
        if record["organization_id"] == organization_id
    }


def build_greeting(phone_number):
    customer = lookup_customer(phone_number)
    if customer:
        return (
            f"مساء الخير يا {customer['name']}. معاك نظام المتابعة الآلي من خدمة العملاء. "
            f"بخصوص تذكرتك رقم {customer['ticket_id']} الخاصة بـ{customer['issue']}، "
            "حابب أتأكد من حضرتك، هل تم حل المشكلة، ولا لسه محتاج مساعدة؟"
        )
    return (
        "مساء الخير. معاك نظام المتابعة الآلي من خدمة العملاء. "
        "كنا اتكلمنا مع حضرتك في مكالمة سابقة واتفقنا على خطوات معينة لحل المشكلة. "
        "حابب أتأكد من حضرتك، هل تم تنفيذ الخطوات دي وانحلت المشكلة، ولا لسه محتاج مساعدة؟"
    )
