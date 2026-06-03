from app.core.database import check_database_connection


def get_database_health() -> dict[str, object]:
    return check_database_connection()
