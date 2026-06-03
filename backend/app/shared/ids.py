import uuid


ID_SEPARATOR = "_"

ALLOWED_ID_PREFIXES = {
    "emp",
    "part",
    "item",
    "fprof",
    "fclass",
    "sale",
    "salehist",
    "saleitem",
    "opnat",
    "fiscalrule",
    "paym",
    "term",
    "cat",
    "acc",
    "coa",
    "cc",
    "bankacc",
    "pix",
    "salepay",
    "loc",
    "stmov",
    "stocklink",
    "stpin",
    "stpini",
    "mkacc",
    "mksync",
    "mkord",
    "mkpay",
    "mpacc",
    "mpoauth",
    "mpweb",
    "mppay",
    "mprel",
    "mpref",
    "mpchg",
    "mppref",
    "mplog",
    "buy",
    "buyitem",
    "buyhist",
    "aplink",
    "ar",
    "arlink",
    "arhist",
    "ap",
    "aphist",
    "cash",
    "cashbal",
    "sett",
    "stmtimp",
    "stmtln",
    "recmatch",
    "doc",
    "tax",
    "user",
    "role",
    "perm",
    "urole",
    "rperm",
    "cmpusr",
    "apol",
    "apreq",
    "apdec",
    "sess",
    "saevt",
    "audit",
    "fdoc",
    "sseq",
    "mpwd",
    "lot",
    "stlot",
}


def generate_uuid() -> str:
    return str(uuid.uuid4())


def generate_id(prefix: str) -> str:
    if prefix not in ALLOWED_ID_PREFIXES:
        raise ValueError(f"Prefixo de ID inválido: {prefix}")

    return f"{prefix}{ID_SEPARATOR}{generate_uuid()}"


def is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False

    return True


def split_id(value: str) -> tuple[str, str]:
    if ID_SEPARATOR not in value:
        raise ValueError("ID inválido. Separador não encontrado.")

    prefix, raw_uuid = value.split(ID_SEPARATOR, 1)

    if prefix not in ALLOWED_ID_PREFIXES:
        raise ValueError(f"Prefixo de ID inválido: {prefix}")

    if not is_valid_uuid(raw_uuid):
        raise ValueError("UUID inválido.")

    return prefix, raw_uuid


def is_valid_id(value: str, expected_prefix: str | None = None) -> bool:
    try:
        prefix, _ = split_id(value)
    except ValueError:
        return False

    if expected_prefix is not None and prefix != expected_prefix:
        return False

    return True


def assert_valid_id(value: str, expected_prefix: str | None = None) -> None:
    if not is_valid_id(value, expected_prefix):
        if expected_prefix:
            raise ValueError(f"ID inválido. Prefixo esperado: {expected_prefix}.")

        raise ValueError("ID inválido.")
    

def normalize_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("ID deve ser string.")

    return value.strip().lower()


def assert_valid_id_list(
    values: list[str],
    expected_prefix: str | None = None,
) -> None:
    if not isinstance(values, list):
        raise ValueError("Lista de IDs inválida.")

    for value in values:
        assert_valid_id(value, expected_prefix)


def ensure_unique_ids(values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError("Lista contém IDs duplicados.")


def assert_same_prefix(values: list[str]) -> None:
    prefixes = set()

    for value in values:
        prefix, _ = split_id(value)
        prefixes.add(prefix)

    if len(prefixes) > 1:
        raise ValueError("IDs com prefixos diferentes na mesma operação.")


def assert_id_prefix(value: str, expected_prefix: str) -> None:
    prefix, _ = split_id(value)

    if prefix != expected_prefix:
        raise ValueError(
            f"Prefixo inválido. Esperado: {expected_prefix}, recebido: {prefix}."
        )












