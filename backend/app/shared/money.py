from decimal import Decimal, ROUND_HALF_UP


MONEY_QUANT = Decimal ("0.01")

def to_money(value: str | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding = ROUND_HALF_UP)

def round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

def sum_money(values: list[Decimal]) -> Decimal:
    total = sum(values, Decimal("0.00"))

    return round_money(total)

def allocate_money(total: Decimal, parts: int) -> list[Decimal]:
    total = round_money(total)

    if parts <= 0:
        raise ValueError("A quantidade de partes deve ser maior que zero.")

    base_value = round_money(total / Decimal(parts))
    values = [base_value for _ in range(parts)]

    difference = total - sum_money(values)
    cents = int(difference * 100)

    for index in range(abs(cents)):
        adjustment = Decimal("0.01") if cents > 0 else Decimal("-0.01")
        values[index] = round_money(values[index] + adjustment)

    return values

def allocate_money_by_weights(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    total = round_money(total)

    if not weights:
        raise ValueError("A lista de pesos não pode ser vazia.")

    if any(weight < 0 for weight in weights):
        raise ValueError("Os pesos não podem ser negativos.")

    total_weight = sum(weights, Decimal("0.00"))

    if total_weight <= 0:
        raise ValueError("A soma dos pesos deve ser maior que zero.")

    raw_values = [
        total * weight / total_weight
        for weight in weights
    ]

    rounded_values = [
        round_money(value)
        for value in raw_values
    ]

    difference = total - sum_money(rounded_values)
    cents = int(difference / MONEY_QUANT)

    if cents == 0:
        return rounded_values

    if cents > 0:
        order = sorted(
            range(len(raw_values)),
            key=lambda index: raw_values[index] - rounded_values[index],
            reverse=True,
        )
        adjustment = MONEY_QUANT
    else:
        order = sorted(
            range(len(raw_values)),
            key=lambda index: raw_values[index] - rounded_values[index],
        )
        adjustment = -MONEY_QUANT

    for index in order[:abs(cents)]:
        rounded_values[index] = round_money(rounded_values[index] + adjustment)

    return rounded_values

def percentage_money(base_value: Decimal, percentage: Decimal) -> Decimal:
    base_value = round_money(base_value)
    result = base_value * percentage / Decimal("100")

    return round_money(result)

def unit_money(total_value: Decimal, quantity: Decimal) -> Decimal:
    if quantity <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")

    result = total_value / quantity

    return round_money(result)

def split_included_percentage(
    total_value: Decimal,
    percentage: Decimal,
) -> tuple[Decimal, Decimal]:
    total_value = round_money(total_value)

    divisor = Decimal("1") + (percentage / Decimal("100"))
    base_value = round_money(total_value / divisor)
    included_value = round_money(total_value - base_value)

    return base_value, included_value

def gross_up_percentage(
    net_value: Decimal,
    percentage: Decimal,
) -> tuple[Decimal, Decimal]:
    net_value = round_money(net_value)

    if percentage < 0:
        raise ValueError("O percentual não pode ser negativo.")

    if percentage >= 100:
        raise ValueError("O percentual deve ser menor que 100.")

    divisor = Decimal("1") - (percentage / Decimal("100"))
    gross_value = round_money(net_value / divisor)
    fee_value = round_money(gross_value - net_value)

    return gross_value, fee_value

def reconcile_money_values(
    expected_total: Decimal,
    values: list[Decimal],
) -> list[Decimal]:
    expected_total = round_money(expected_total)

    if not values:
        raise ValueError("A lista de valores não pode ser vazia.")

    reconciled_values = [
        round_money(value)
        for value in values
    ]

    actual_total = sum_money(reconciled_values)
    difference = round_money(expected_total - actual_total)

    if difference == Decimal("0.00"):
        return reconciled_values

    index_to_adjust = max(
        range(len(reconciled_values)),
        key=lambda index: abs(reconciled_values[index]),
    )

    reconciled_values[index_to_adjust] = round_money(
        reconciled_values[index_to_adjust] + difference
    )

    return reconciled_values

def line_total_money(
    unit_value: Decimal,
    quantity: Decimal,
) -> Decimal:
    if quantity <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")

    result = unit_value * quantity

    return round_money(result)

def net_money(
    base_value: Decimal,
    additions: list[Decimal] | None = None,
    deductions: list[Decimal] | None = None,
) -> Decimal:
    additions = additions or []
    deductions = deductions or []

    total_additions = sum_money(additions) if additions else Decimal("0.00")
    total_deductions = sum_money(deductions) if deductions else Decimal("0.00")

    result = round_money(base_value) + total_additions - total_deductions

    return round_money(result)

def assert_money_balance(
    expected_total: Decimal,
    values: list[Decimal],
) -> None:
    expected_total = round_money(expected_total)
    actual_total = sum_money(values)
    difference = round_money(expected_total - actual_total)

    if difference != Decimal("0.00"):
        raise ValueError(
            f"Diferença monetária encontrada. "
            f"Esperado: {expected_total}. "
            f"Calculado: {actual_total}. "
            f"Diferença: {difference}."
        )

def _validate_brazilian_integer_groups(integer_part: str) -> None:
    groups = integer_part.split(".")

    if any(group == "" for group in groups):
        raise ValueError("Formato monetário brasileiro inválido.")

    if not all(group.isdigit() for group in groups):
        raise ValueError("Formato monetário brasileiro inválido.")

    if len(groups) == 1:
        return

    first_group = groups[0]
    other_groups = groups[1:]

    if not 1 <= len(first_group) <= 3:
        raise ValueError("Formato monetário brasileiro inválido.")

    if not all(len(group) == 3 for group in other_groups):
        raise ValueError("Formato monetário brasileiro inválido.")

def parse_brazilian_money(value: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Valor monetário brasileiro deve ser string.")

    text = value.strip().replace("\xa0", " ")

    if not text:
        raise ValueError("Valor monetário brasileiro vazio.")

    negative = False

    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()

    text = text.replace("R$", "").replace("r$", "").strip()
    text = "".join(text.split())

    if not text:
        raise ValueError("Valor monetário brasileiro vazio.")

    if text.startswith("-"):
        negative = True
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]

    if not text:
        raise ValueError("Valor monetário brasileiro vazio.")

    if not all(char.isdigit() or char in ".," for char in text):
        raise ValueError("Formato monetário brasileiro inválido.")

    if not any(char.isdigit() for char in text):
        raise ValueError("Formato monetário brasileiro inválido.")

    if text.count(",") > 1:
        raise ValueError("Formato monetário brasileiro inválido.")

    if "," in text and "." in text:
        if text.rfind(",") < text.rfind("."):
            raise ValueError(
                "Formato monetário brasileiro inválido. Use vírgula como separador decimal."
            )

    if "," in text:
        integer_part, decimal_part = text.split(",", 1)

        if decimal_part == "":
            raise ValueError("Parte decimal ausente.")

        if not decimal_part.isdigit():
            raise ValueError("Parte decimal inválida.")

        _validate_brazilian_integer_groups(integer_part)

        normalized = f"{integer_part.replace('.', '')}.{decimal_part}"
    else:
        _validate_brazilian_integer_groups(text)

        normalized = text.replace(".", "")

    result = Decimal(normalized)

    if negative:
        result = -result

    return round_money(result)




