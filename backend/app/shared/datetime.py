from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


BRAZIL_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def utc_now() -> datetime:
    return datetime.now(UTC)


def today_utc() -> date:
    return utc_now().date()


def now_in_brazil() -> datetime:
    return utc_now().astimezone(BRAZIL_TIMEZONE)


def today_in_brazil() -> date:
    return now_in_brazil().date()


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Datetime sem timezone não é permitido.")

    return value.astimezone(UTC)


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Data inválida. Use o formato YYYY-MM-DD.") from error


def format_iso_date(value: date) -> str:
    return value.isoformat()


def last_day_of_month(year: int, month: int) -> date:
    if month < 1 or month > 12:
        raise ValueError("O mês deve estar entre 1 e 12.")

    if month == 12:
        first_day_next_month = date(year + 1, 1, 1)
    else:
        first_day_next_month = date(year, month + 1, 1)

    return first_day_next_month - timedelta(days=1)


def is_last_day_of_month(value: date) -> bool:
    return value == last_day_of_month(value.year, value.month)


def add_months_safe(
    value: date,
    months: int,
    preserve_month_end: bool = True,
) -> date:
    month_index = value.month - 1 + months

    target_year = value.year + month_index // 12
    target_month = month_index % 12 + 1
    target_last_day = last_day_of_month(target_year, target_month).day

    if preserve_month_end and is_last_day_of_month(value):
        target_day = target_last_day
    else:
        target_day = min(value.day, target_last_day)

    return date(target_year, target_month, target_day)


def month_period(value: date) -> tuple[date, date]:
    first_day = date(value.year, value.month, 1)
    last_day = last_day_of_month(value.year, value.month)

    return first_day, last_day


def competence_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def is_weekend(value: date) -> bool:
    return value.weekday() >= 5


def adjust_to_business_day(
    value: date,
    direction: str = "next",
) -> date:
    if direction not in {"next", "previous"}:
        raise ValueError("A direção deve ser 'next' ou 'previous'.")

    step = 1 if direction == "next" else -1
    adjusted_date = value

    while is_weekend(adjusted_date):
        adjusted_date = adjusted_date + timedelta(days=step)

    return adjusted_date


def generate_monthly_due_dates(
    first_due_date: date,
    installments: int,
    preserve_month_end: bool = True,
    adjust_weekends: bool = False,
) -> list[date]:
    if installments <= 0:
        raise ValueError("A quantidade de parcelas deve ser maior que zero.")

    due_dates = [
        add_months_safe(
            first_due_date,
            months=index,
            preserve_month_end=preserve_month_end,
        )
        for index in range(installments)
    ]

    if adjust_weekends:
        return [
            adjust_to_business_day(due_date, direction="next")
            for due_date in due_dates
        ]

    return due_dates


def days_between(start_date: date, end_date: date) -> int:
    return (end_date - start_date).days


def is_overdue(
    due_date: date,
    reference_date: date,
) -> bool:
    return due_date < reference_date