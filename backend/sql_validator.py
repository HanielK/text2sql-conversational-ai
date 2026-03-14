def validate_sql(sql: str):
    """
    Basic SQL safety validation.
    Prevents destructive queries and ensures SQL exists.
    """

    if not sql or len(sql.strip()) == 0:
        return False, "SQL query is empty."

    forbidden = [
        "DROP",
        "DELETE",
        "TRUNCATE",
        "ALTER",
        "UPDATE",
        "INSERT"
    ]

    upper_sql = sql.upper()

    for word in forbidden:
        if word in upper_sql:
            return False, f"Forbidden SQL operation detected: {word}"

    return True, "SQL validated successfully."