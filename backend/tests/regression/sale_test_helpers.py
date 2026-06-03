"""Helpers de fixtures de venda para testes de regressao.

Cria catalogo, classificacao fiscal, participante e monta payloads de venda
prontos para fechar (origin=manual, servico, classificacao fiscal ativa).
"""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def ensure_service_fixtures(client: TestClient, company_id: str, headers: dict) -> dict:
    """Garante item de servico, classificacao fiscal e participante para o tenant de testes.

    Retorna dict com ``item_id``, ``fiscal_classification_id`` e ``participant_id``.
    O servico e criado por chamada para manter preco deterministico.
    """
    # --- participante (cliente) ---
    parts_resp = client.get(
        "/participants",
        params={"company_id": company_id, "participant_type": "customer", "limit": 1},
        headers=headers,
    )
    assert parts_resp.status_code == 200
    parts_data = parts_resp.json()["data"]
    parts = parts_data.get("items", parts_data) if isinstance(parts_data, dict) else parts_data
    if parts:
        participant_id = parts[0]["id"]
    else:
        part_create = client.post(
            "/participants",
            json={
                "company_id": company_id,
                "participant_type": "customer",
                "person_type": "individual",
                "name": "Cliente Regressao v1",
                "status": "active",
            },
            headers=headers,
        )
        assert part_create.status_code == 201, part_create.text
        participant_id = part_create.json()["data"]["id"]

    # --- item de catalogo (servico) ---
    # Nao reutiliza qualquer servico existente: massa local pode ter preco
    # diferente e quebrar o plano de pagamento fixo dos testes.
    create_resp = client.post(
        "/catalog/items",
        json={
            "company_id": company_id,
            "item_type": "service",
            "name": f"Servico Regressao v1 {uuid4().hex[:8]}",
            "financial_settings": {"default_sale_price": "100.00"},
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    item_id = create_resp.json()["data"]["id"]

    # --- classificacao fiscal (servico, ativa) ---
    fc_resp = client.get(
        "/fiscal/classifications",
        params={"company_id": company_id, "item_type": "service", "status_filter": "active", "limit": 1},
        headers=headers,
    )
    assert fc_resp.status_code == 200
    fc_data = fc_resp.json()["data"]
    fcs = fc_data.get("items", fc_data) if isinstance(fc_data, dict) else fc_data
    if fcs:
        fc_id = fcs[0]["id"]
    else:
        fc_create = client.post(
            "/fiscal/classifications",
            json={
                "company_id": company_id,
                "name": "FC Regressao v1",
                "item_type": "service",
                "nbs": "1.05.01.4",
                "status": "active",
            },
            headers=headers,
        )
        assert fc_create.status_code == 201, fc_create.text
        fc_id = fc_create.json()["data"]["id"]

    return {
        "item_id": item_id,
        "fiscal_classification_id": fc_id,
        "participant_id": participant_id,
    }


def build_sale_payload(
    company_id: str,
    item_id: str,
    fiscal_classification_id: str,
    participant_id: str,
) -> dict:
    """Payload minimo para criar venda de servico pronta para fechamento."""
    return {
        "company_id": company_id,
        "sale_type": "service",
        "origin": "manual",
        "participant_id": participant_id,
        "payment_plans": [
            {
                "amount": "100.00",
                "payment_method_code": "pix",
            }
        ],
        "items": [
            {
                "item_id": item_id,
                "fiscal_classification_id": fiscal_classification_id,
                "quantity": "1",
            }
        ],
    }


def create_closeable_sale(client: TestClient, company_id: str, headers: dict) -> str:
    """Cria uma venda de servico com status QUOTE pronta para ser fechada.

    Retorna o ``sale_id``.
    """
    fixtures = ensure_service_fixtures(client, company_id, headers)
    payload = build_sale_payload(
        company_id,
        fixtures["item_id"],
        fixtures["fiscal_classification_id"],
        fixtures["participant_id"],
    )
    resp = client.post("/sales", json=payload, headers=headers)
    assert resp.status_code == 201, f"Falha ao criar venda: {resp.text}"
    return resp.json()["data"]["id"]
