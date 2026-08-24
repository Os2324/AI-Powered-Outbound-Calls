"""
Simulated CRM lookup: a stand-in for a real customer-records system.
In a real deployment this would be a database query against your actual CRM
(ticket ID, prior call notes, etc.) -- here it's a small hardcoded dict so the
outbound call greeting can be genuinely dynamic per customer, proving the
concept without needing a real CRM integration.
"""

CUSTOMERS = {
    "201149192315": {
        "name": "أحمد",
        "ticket_id": "TCK-4471",
        "issue": "مشكلة في تسجيل الدخول للحساب",
    },
    "201207756337": {
        "name": "سارة",
        "ticket_id": "TCK-5820",
        "issue": "تأخر في استلام الطلب",
    },
    "201155566677": {
        "name": "محمود",
        "ticket_id": "TCK-6193",
        "issue": "مشكلة في إعادة تعيين كلمة المرور",
    },
    "201227788990": {
        "name": "منى",
        "ticket_id": "TCK-6304",
        "issue": "استفسار عن استرجاع منتج",
    },
    "201099887766": {
        "name": "خالد",
        "ticket_id": "TCK-6421",
        "issue": "خصم مكرر على البطاقة الائتمانية",
    },
    "201288776655": {
        "name": "ياسمين",
        "ticket_id": "TCK-6558",
        "issue": "طلب صيانة جهاز تحت الضمان",
    },
    "201033445566": {
        "name": "عمر",
        "ticket_id": "TCK-6670",
        "issue": "إلغاء الاشتراك الشهري",
    },
    "201211223344": {
        "name": "نور",
        "ticket_id": "TCK-6789",
        "issue": "استفسار عن نقاط برنامج الولاء",
    },
}


def lookup_customer(phone_number):
    """Returns the customer record for a phone number, or None if unknown."""
    return CUSTOMERS.get(phone_number)


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
