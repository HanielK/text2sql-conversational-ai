def validate_sql(sql: str):
    """
    Basic SQL safety validation.

    Ensures:
    - Query exists
    - Only SELECT queries are allowed
    - Prevents destructive operations
    - Prevents multi-statement execution
    """

    if not sql or len(sql.strip()) == 0:
        return False, "SQL query is empty."

    cleaned_sql = sql.strip()

    upper_sql = cleaned_sql.upper()

    # -------------------------------------------------
    # Only allow SELECT queries
    # -------------------------------------------------

    if not upper_sql.startswith("SELECT"):
        return False, "Only SELECT queries are allowed."

    # -------------------------------------------------
    # Prevent destructive operations
    # -------------------------------------------------

    forbidden = [
        "DROP ",
        "DELETE ",
        "TRUNCATE ",
        "ALTER ",
        "UPDATE ",
        "INSERT "
    ]

    for word in forbidden:
        if word in upper_sql:
            return False, f"Forbidden SQL operation detected: {word.strip()}"

    # -------------------------------------------------
    # Prevent multiple statements
    # -------------------------------------------------

    if ";" in cleaned_sql[:-1]:
        return False, "Multiple SQL statements are not allowed."

    return True, "SQL validated successfully."