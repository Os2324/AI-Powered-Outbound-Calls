import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent / "business.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            city TEXT,
            status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product TEXT,
            amount REAL,
            status TEXT,
            FOREIGN KEY (customer_id)
                REFERENCES customers(id)
        )
    """)

    # ---------------------------------------------------------
    # Sample customers
    # ---------------------------------------------------------

    customers = [
        (1, "أحمد محمد", "01000000001", "القاهرة", "active"),
        (2, "سارة علي", "01000000002", "الجيزة", "active"),
        (3, "محمد حسن", "01000000003", "الإسكندرية", "inactive"),
        (4, "نور أحمد", "01000000004", "القاهرة", "active"),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO customers
        (id, name, phone, city, status)
        VALUES (?, ?, ?, ?, ?)
    """, customers)

    # ---------------------------------------------------------
    # Sample orders
    # ---------------------------------------------------------

    orders = [
        (1001, 1, "هاتف ذكي", 18000, "delivered"),
        (1002, 1, "سماعات", 2500, "delivered"),
        (1003, 2, "لابتوب", 32000, "processing"),
        (1004, 4, "ساعة ذكية", 6500, "cancelled"),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO orders
        (id, customer_id, product, amount, status)
        VALUES (?, ?, ?, ?, ?)
    """, orders)

    conn.commit()
    conn.close()

def get_schema():
    """
    Inspect the SQLite database and return its schema
    including sample/distinct values for TEXT columns.
    """

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # Get all user tables.
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)

        tables = [
            row[0]
            for row in cursor.fetchall()
        ]

        schema_parts = []

        for table in tables:

            cursor.execute(
                f'PRAGMA table_info("{table}")'
            )

            columns = cursor.fetchall()

            schema_parts.append(
                f"TABLE {table}:"
            )

            # Columns
            for column in columns:

                column_name = column[1]
                column_type = column[2]

                schema_parts.append(
                    f"    {column_name} {column_type}"
                )

                # Show distinct values for TEXT columns.
                if column_type.upper() == "TEXT":

                    cursor.execute(
                        f"""
                        SELECT DISTINCT "{column_name}"
                        FROM "{table}"
                        WHERE "{column_name}" IS NOT NULL
                        LIMIT 20
                        """
                    )

                    values = [
                        row[0]
                        for row in cursor.fetchall()
                    ]

                    if values:

                        formatted_values = ", ".join(
                            str(value)
                            for value in values
                        )

                        schema_parts.append(
                            f"        possible values: "
                            f"{formatted_values}"
                        )

            # Foreign keys
            cursor.execute(
                f'PRAGMA foreign_key_list("{table}")'
            )

            foreign_keys = cursor.fetchall()

            for fk in foreign_keys:

                referenced_table = fk[2]
                from_column = fk[3]
                to_column = fk[4]

                schema_parts.append(
                    f"    FOREIGN KEY: "
                    f"{table}.{from_column} → "
                    f"{referenced_table}.{to_column}"
                )

            schema_parts.append("")

        return "\n".join(schema_parts)

    finally:
        conn.close()


def execute_query(sql):
    """
    Execute a read-only SQL query.

    Only a single SELECT/WITH query is allowed.
    """

    sql = sql.strip()

    # Remove trailing semicolon.
    sql = sql.rstrip(";").strip()

    if not sql:
        raise ValueError("SQL query is empty.")

    # Prevent multiple SQL statements.
    if ";" in sql:
        raise ValueError(
            "Multiple SQL statements are not allowed."
        )

    # Only SELECT or WITH queries are allowed.
    first_word = sql.split(None, 1)[0].lower()

    if first_word not in {"select", "with"}:
        raise ValueError(
            "Only read-only SELECT queries are allowed."
        )

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(sql)

        rows = cursor.fetchall()

        columns = [
            description[0]
            for description in cursor.description
        ]

        return columns, rows

    finally:
        conn.close()


if __name__ == "__main__":
    initialize_database()

    print("SQL database initialized successfully.")
    print(f"Database location: {DB_PATH}")