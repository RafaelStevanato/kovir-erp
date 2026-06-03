from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.modules.imports.schemas import ImportTarget, ImportTemplate, ImportTemplateColumn
from app.shared.money import parse_brazilian_money


TEMPLATES: dict[ImportTarget, ImportTemplate] = {
    ImportTarget.PARTICIPANTS: ImportTemplate(
        target=ImportTarget.PARTICIPANTS,
        label="Participantes",
        description="Clientes, fornecedores, transportadoras, bancos, gateways e terceiros.",
        columns=[
            ImportTemplateColumn(key="participant_type", label="Tipo", required=True, description="customer, supplier, carrier, service_provider, marketplace, gateway, bank ou other.", example="customer"),
            ImportTemplateColumn(key="person_type", label="Pessoa", required=True, description="individual, company, foreign ou unknown.", example="company"),
            ImportTemplateColumn(key="name", label="Nome/Razao social", required=True, description="Nome oficial do participante.", example="Cliente Exemplo LTDA"),
            ImportTemplateColumn(key="trade_name", label="Nome fantasia", description="Nome comercial opcional.", example="Cliente Exemplo"),
            ImportTemplateColumn(key="document", label="Documento", description="CPF/CNPJ sem obrigatoriedade de pontuacao.", example="12345678000190"),
            ImportTemplateColumn(key="email", label="E-mail", description="E-mail principal.", example="contato@cliente.com.br"),
            ImportTemplateColumn(key="phone", label="Telefone", description="Telefone principal.", example="11999999999"),
            ImportTemplateColumn(key="status", label="Status", description="draft, active, inactive ou blocked.", example="active"),
            ImportTemplateColumn(key="origin", label="Origem", description="Origem do cadastro; quando vazio, usa import.", example="import"),
            ImportTemplateColumn(key="tags", label="Tags", description="Lista separada por virgula ou ponto e virgula.", example="legado; cliente"),
            ImportTemplateColumn(key="street", label="Logradouro", description="Endereco opcional."),
            ImportTemplateColumn(key="number", label="Numero", description="Endereco opcional."),
            ImportTemplateColumn(key="district", label="Bairro", description="Endereco opcional."),
            ImportTemplateColumn(key="city", label="Cidade", description="Endereco opcional."),
            ImportTemplateColumn(key="state", label="UF", description="Endereco opcional.", example="SP"),
            ImportTemplateColumn(key="zip_code", label="CEP", description="Endereco opcional.", example="01001000"),
            ImportTemplateColumn(key="taxpayer_type", label="Tipo contribuinte", description="taxpayer, non_taxpayer, exempt ou unknown.", example="taxpayer"),
            ImportTemplateColumn(key="tax_regime", label="Regime tributario", description="Regime tributario textual do participante.", example="simples_nacional"),
            ImportTemplateColumn(key="state_registration", label="Inscricao estadual", description="Inscricao estadual opcional."),
            ImportTemplateColumn(key="notes", label="Observacoes", description="Observacoes internas."),
        ],
    ),
    ImportTarget.PRODUCTS: ImportTemplate(
        target=ImportTarget.PRODUCTS,
        label="Produtos",
        description="Produtos do catalogo; servicos ficam fora deste target.",
        columns=[
            ImportTemplateColumn(key="name", label="Nome", required=True, description="Nome do produto.", example="Produto Exemplo"),
            ImportTemplateColumn(key="sku", label="SKU", description="Codigo interno unico por empresa.", example="PROD-001"),
            ImportTemplateColumn(key="barcode", label="Codigo de barras", description="Codigo de barras unico por empresa."),
            ImportTemplateColumn(key="unit", label="Unidade", description="Unidade comercial.", example="UN"),
            ImportTemplateColumn(key="brand", label="Marca", description="Marca opcional."),
            ImportTemplateColumn(key="category", label="Categoria", description="Categoria opcional."),
            ImportTemplateColumn(key="ncm", label="NCM", required=True, description="NCM com 8 digitos e previamente cadastrado na classificacao fiscal.", example="01012100"),
            ImportTemplateColumn(key="sale_price", label="Preco de venda", description="Valor monetario em formato brasileiro ou decimal.", example="129,90"),
            ImportTemplateColumn(key="cost_price", label="Custo", description="Valor monetario em formato brasileiro ou decimal.", example="80,00"),
            ImportTemplateColumn(key="track_stock", label="Controla estoque", description="sim/nao, true/false ou 1/0.", example="sim"),
            ImportTemplateColumn(key="stock_unit", label="Unidade estoque", description="Obrigatoria quando controla estoque.", example="UN"),
            ImportTemplateColumn(key="minimum_stock", label="Estoque minimo", description="Quantidade minima opcional.", example="5"),
            ImportTemplateColumn(key="status", label="Status", description="draft, active, inactive ou blocked.", example="active"),
            ImportTemplateColumn(key="notes", label="Observacoes", description="Observacoes internas."),
        ],
    ),
    ImportTarget.FISCAL_CLASSIFICATIONS: ImportTemplate(
        target=ImportTarget.FISCAL_CLASSIFICATIONS,
        label="Classificacoes fiscais",
        description="Cadastro fiscal estrutural usado por produtos e regras futuras.",
        columns=[
            ImportTemplateColumn(key="name", label="Nome", required=True, description="Nome da classificacao fiscal.", example="NCM 01012100"),
            ImportTemplateColumn(key="item_type", label="Aplicacao", required=True, description="product, service, both ou operation.", example="product"),
            ImportTemplateColumn(key="tax_regime", label="Regime", description="simples_nacional, lucro_presumido, lucro_real, mei, producer, foreign, unknown ou not_applicable.", example="simples_nacional"),
            ImportTemplateColumn(key="ncm", label="NCM", description="Obrigatorio para product.", example="01012100"),
            ImportTemplateColumn(key="nbs", label="NBS", description="Obrigatorio para service."),
            ImportTemplateColumn(key="cest", label="CEST", description="CEST opcional."),
            ImportTemplateColumn(key="ex_tipi", label="EX TIPI", description="EX TIPI opcional."),
            ImportTemplateColumn(key="origem_mercadoria", label="Origem mercadoria", description="Codigo de origem da mercadoria.", example="0"),
            ImportTemplateColumn(key="cfop_default", label="CFOP padrao", description="CFOP padrao opcional.", example="5102"),
            ImportTemplateColumn(key="cst_icms", label="CST ICMS", description="CST ICMS opcional."),
            ImportTemplateColumn(key="cst_pis", label="CST PIS", description="CST PIS opcional."),
            ImportTemplateColumn(key="cst_cofins", label="CST COFINS", description="CST COFINS opcional."),
            ImportTemplateColumn(key="cst_ibs_cbs", label="CST IBS/CBS", description="CST IBS/CBS opcional."),
            ImportTemplateColumn(key="cclass_trib", label="cClassTrib", description="Classificacao tributaria da reforma."),
            ImportTemplateColumn(key="subject_to_icms", label="Sujeito a ICMS", description="sim/nao.", example="sim"),
            ImportTemplateColumn(key="subject_to_iss", label="Sujeito a ISS", description="sim/nao.", example="nao"),
            ImportTemplateColumn(key="subject_to_pis_cofins", label="Sujeito a PIS/COFINS", description="sim/nao.", example="sim"),
            ImportTemplateColumn(key="subject_to_ibs_cbs", label="Sujeito a IBS/CBS", description="sim/nao.", example="sim"),
            ImportTemplateColumn(key="subject_to_is", label="Sujeito a IS", description="sim/nao.", example="nao"),
            ImportTemplateColumn(key="valid_from", label="Vigente de", description="Data YYYY-MM-DD ou DD/MM/YYYY."),
            ImportTemplateColumn(key="valid_to", label="Vigente ate", description="Data YYYY-MM-DD ou DD/MM/YYYY."),
            ImportTemplateColumn(key="status", label="Status", description="draft, active, inactive, blocked ou expired.", example="draft"),
            ImportTemplateColumn(key="source_reference", label="Referencia da fonte", description="Referencia da tabela legada/importada."),
            ImportTemplateColumn(key="notes", label="Observacoes", description="Observacoes internas."),
        ],
    ),
}


ALIASES: dict[ImportTarget, dict[str, set[str]]] = {
    ImportTarget.PARTICIPANTS: {
        "participant_type": {"tipo", "tipo_participante", "participant_type"},
        "person_type": {"pessoa", "tipo_pessoa", "person_type"},
        "name": {"nome", "razao_social", "nome_razao_social", "name"},
        "trade_name": {"nome_fantasia", "fantasia", "trade_name"},
        "document": {"documento", "cpf", "cnpj", "cpf_cnpj", "document"},
        "email": {"email", "e_mail"},
        "phone": {"telefone", "celular", "phone"},
        "secondary_phone": {"telefone_secundario", "secondary_phone"},
        "website": {"site", "website"},
        "contact_name": {"contato", "nome_contato", "contact_name"},
        "contact_phone": {"telefone_contato", "contact_phone"},
        "contact_email": {"email_contato", "contact_email"},
        "origin": {"origem", "origin"},
        "tags": {"tags", "marcadores"},
        "status": {"status", "situacao"},
        "street": {"logradouro", "rua", "endereco", "street"},
        "number": {"numero", "number"},
        "complement": {"complemento", "complement"},
        "district": {"bairro", "district"},
        "city": {"cidade", "municipio", "city"},
        "state": {"uf", "estado", "state"},
        "zip_code": {"cep", "zip_code"},
        "country": {"pais", "country"},
        "ibge_municipality_code": {"codigo_ibge", "ibge_municipality_code"},
        "taxpayer_type": {"tipo_contribuinte", "taxpayer_type"},
        "tax_regime": {"regime_tributario", "tax_regime"},
        "main_cnae": {"cnae", "main_cnae"},
        "state_registration": {"inscricao_estadual", "ie", "state_registration"},
        "municipal_registration": {"inscricao_municipal", "im", "municipal_registration"},
        "suframa_registration": {"suframa", "suframa_registration"},
        "is_foreign": {"estrangeiro", "is_foreign"},
        "fiscal_notes": {"observacoes_fiscais", "fiscal_notes"},
        "default_payment_method": {"forma_pagamento_padrao", "default_payment_method"},
        "default_payment_terms": {"prazo_pagamento_padrao", "default_payment_terms"},
        "bank_name": {"banco", "bank_name"},
        "bank_branch": {"agencia", "bank_branch"},
        "bank_account": {"conta_bancaria", "bank_account"},
        "pix_key": {"chave_pix", "pix_key"},
        "credit_limit": {"limite_credito", "credit_limit"},
        "payment_priority": {"prioridade_pagamento", "payment_priority"},
        "notes": {"observacoes", "obs", "notes"},
    },
    ImportTarget.PRODUCTS: {
        "item_type": {"tipo_item", "tipo", "item_type"},
        "name": {"nome", "produto", "descricao_produto", "name"},
        "description": {"descricao", "description"},
        "sku": {"sku", "codigo", "codigo_interno"},
        "barcode": {"codigo_barras", "ean", "gtin", "barcode"},
        "unit": {"unidade", "un", "unit"},
        "status": {"status", "situacao"},
        "origin": {"origem", "origin"},
        "brand": {"marca", "brand"},
        "category": {"categoria", "category"},
        "ncm": {"ncm"},
        "nbs": {"nbs"},
        "cest": {"cest"},
        "cfop_default": {"cfop", "cfop_padrao", "cfop_default"},
        "sale_price": {"preco_venda", "valor_venda", "sale_price"},
        "cost_price": {"custo", "preco_custo", "cost_price"},
        "track_stock": {"controla_estoque", "track_stock"},
        "stock_unit": {"unidade_estoque", "stock_unit"},
        "minimum_stock": {"estoque_minimo", "minimum_stock"},
        "allow_negative_stock": {"permite_estoque_negativo", "allow_negative_stock"},
        "notes": {"observacoes", "obs", "notes"},
    },
    ImportTarget.FISCAL_CLASSIFICATIONS: {
        "name": {"nome", "classificacao", "name"},
        "description": {"descricao", "description"},
        "item_type": {"tipo_item", "aplicacao", "item_type"},
        "tax_regime": {"regime_tributario", "tax_regime"},
        "ncm": {"ncm"},
        "nbs": {"nbs"},
        "cest": {"cest"},
        "ex_tipi": {"ex_tipi", "ex"},
        "origem_mercadoria": {"origem_mercadoria", "origem"},
        "cfop_default": {"cfop", "cfop_padrao", "cfop_default"},
        "cst_icms": {"cst_icms"},
        "cst_pis": {"cst_pis"},
        "cst_cofins": {"cst_cofins"},
        "cst_ibs_cbs": {"cst_ibs_cbs"},
        "cclass_trib": {"cclass_trib", "cclasstrib"},
        "subject_to_icms": {"sujeito_icms", "subject_to_icms"},
        "subject_to_iss": {"sujeito_iss", "subject_to_iss"},
        "subject_to_pis_cofins": {"sujeito_pis_cofins", "subject_to_pis_cofins"},
        "subject_to_ibs_cbs": {"sujeito_ibs_cbs", "subject_to_ibs_cbs"},
        "subject_to_is": {"sujeito_is", "subject_to_is"},
        "valid_from": {"vigente_de", "valid_from"},
        "valid_to": {"vigente_ate", "valid_to"},
        "status": {"status", "situacao"},
        "source": {"fonte", "source"},
        "source_reference": {"referencia_fonte", "source_reference"},
        "notes": {"observacoes", "obs", "notes"},
    },
}


ENUM_ALIASES: dict[str, dict[str, str]] = {
    "participant_type": {
        "cliente": "customer",
        "customer": "customer",
        "fornecedor": "supplier",
        "supplier": "supplier",
        "transportadora": "carrier",
        "carrier": "carrier",
        "prestador": "service_provider",
        "prestador_servico": "service_provider",
        "service_provider": "service_provider",
        "marketplace": "marketplace",
        "gateway": "gateway",
        "banco": "bank",
        "bank": "bank",
        "outro": "other",
        "other": "other",
    },
    "person_type": {
        "fisica": "individual",
        "pessoa_fisica": "individual",
        "pf": "individual",
        "individual": "individual",
        "juridica": "company",
        "pessoa_juridica": "company",
        "pj": "company",
        "empresa": "company",
        "company": "company",
        "estrangeiro": "foreign",
        "foreign": "foreign",
        "desconhecido": "unknown",
        "unknown": "unknown",
    },
    "status": {
        "rascunho": "draft",
        "draft": "draft",
        "ativo": "active",
        "active": "active",
        "inativo": "inactive",
        "inactive": "inactive",
        "bloqueado": "blocked",
        "blocked": "blocked",
        "expirado": "expired",
        "expired": "expired",
    },
    "origin": {
        "direto": "direct",
        "direct": "direct",
        "marketplace": "marketplace",
        "indicacao": "referral",
        "referral": "referral",
        "importacao": "import",
        "importado": "import",
        "import": "import",
        "organico": "organic",
        "organic": "organic",
        "manual": "manual",
        "outro": "other",
        "other": "other",
    },
    "catalog_origin": {
        "manual": "manual",
        "importado": "imported",
        "importacao": "imported",
        "imported": "imported",
        "integracao": "integration",
        "integration": "integration",
        "documento_fiscal": "fiscal_document",
        "fiscal_document": "fiscal_document",
        "unknown": "unknown",
        "desconhecido": "unknown",
    },
    "taxpayer_type": {
        "contribuinte": "taxpayer",
        "taxpayer": "taxpayer",
        "nao_contribuinte": "non_taxpayer",
        "non_taxpayer": "non_taxpayer",
        "isento": "exempt",
        "exempt": "exempt",
        "desconhecido": "unknown",
        "unknown": "unknown",
    },
    "item_type": {
        "produto": "product",
        "product": "product",
        "servico": "service",
        "service": "service",
        "ambos": "both",
        "both": "both",
        "operacao": "operation",
        "operation": "operation",
    },
    "tax_regime": {
        "simples_nacional": "simples_nacional",
        "lucro_presumido": "lucro_presumido",
        "lucro_real": "lucro_real",
        "mei": "mei",
        "produtor": "producer",
        "producer": "producer",
        "estrangeiro": "foreign",
        "foreign": "foreign",
        "desconhecido": "unknown",
        "unknown": "unknown",
        "nao_se_aplica": "not_applicable",
        "not_applicable": "not_applicable",
    },
    "source": {
        "manual": "manual",
        "contador": "accountant",
        "accountant": "accountant",
        "regra_oficial": "official_rule",
        "official_rule": "official_rule",
        "tabela_importada": "imported_table",
        "imported_table": "imported_table",
        "integracao": "integration",
        "integration": "integration",
        "legado": "legacy",
        "legacy": "legacy",
        "desconhecido": "unknown",
        "unknown": "unknown",
    },
}


def get_templates() -> list[ImportTemplate]:
    return list(TEMPLATES.values())


def get_template(target: ImportTarget) -> ImportTemplate:
    return TEMPLATES[target]


def normalize_header(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def normalize_raw_row(target: ImportTarget, raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    alias_map: dict[str, str] = {}
    for canonical, aliases in ALIASES[target].items():
        alias_map[normalize_header(canonical)] = canonical
        for alias in aliases:
            alias_map[normalize_header(alias)] = canonical

    row: dict[str, Any] = {}
    warnings: list[str] = []

    for key, value in raw.items():
        normalized_key = normalize_header(str(key))
        if not normalized_key:
            continue
        canonical = alias_map.get(normalized_key)
        if canonical is None:
            warnings.append(f"Coluna ignorada: {key}")
            continue
        row[canonical] = clean_scalar(value)

    return row, warnings


def clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return value


def value_as_text(value: Any) -> str | None:
    value = clean_scalar(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, "f").rstrip("0").rstrip(".")
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip() or None


def value_as_digits(value: Any) -> str | None:
    text = value_as_text(value)
    if text is None:
        return None
    digits = "".join(char for char in text if char.isdigit())
    return digits or None


def value_as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = normalize_header(str(value))
    if text in {"sim", "s", "true", "t", "1", "yes", "y"}:
        return True
    if text in {"nao", "n", "false", "f", "0", "no"}:
        return False
    raise ValueError(f"Valor booleano invalido: {value}")


def value_as_money_text(value: Any) -> str | None:
    text = value_as_text(value)
    if text is None:
        return None
    normalized = text.replace("R$", "").replace("r$", "").strip()
    if "." in normalized and "," not in normalized:
        return str(Decimal(normalized))
    return str(parse_brazilian_money(text))


def value_as_decimal_text(value: Any) -> str | None:
    text = value_as_text(value)
    if text is None:
        return None
    cleaned = text.replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    Decimal(cleaned)
    return cleaned


def value_as_date_text(value: Any) -> str | None:
    text = value_as_text(value)
    if text is None:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", text):
        day, month, year = text.split("/")
        return f"{year}-{month}-{day}"
    excel_date = excel_serial_date_to_iso(text)
    if excel_date is not None:
        return excel_date
    return text


def excel_serial_date_to_iso(value: str) -> str | None:
    cleaned = value.strip()
    if not re.fullmatch(r"\d{4,5}(?:\.0+)?", cleaned):
        return None

    serial = int(Decimal(cleaned))
    if serial < 30000 or serial > 60000:
        return None

    return (date(1899, 12, 30) + timedelta(days=serial)).isoformat()


def normalize_enum(field: str, value: Any, default: str | None = None) -> str | None:
    text = value_as_text(value)
    if text is None:
        return default
    normalized = normalize_header(text)
    aliases = ENUM_ALIASES.get(field, {})
    return aliases.get(normalized, normalized)


def split_tags(value: Any) -> list[str]:
    text = value_as_text(value)
    if text is None:
        return []
    return [item.strip() for item in re.split(r"[,;]", text) if item.strip()]


def without_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}
