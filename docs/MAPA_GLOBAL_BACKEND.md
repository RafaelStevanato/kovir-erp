# MAPA GLOBAL DO BACKEND

Status: documento oficial do backend para a fase local do Kovir ERP 1.0.0.

Este mapa foi consolidado a partir de `backend/app`, `backend/alembic`,
`backend/tests`, ferramentas locais e documentos tecnicos ainda aderentes ao
codigo atual. O backend e a fonte oficial das regras criticas do sistema; o
frontend nunca deve ser tratado como fonte de verdade.

## 1. Escopo atual

- Produto: Kovir ERP.
- Execucao atual: desenvolvimento local.
- Deploy AWS: cancelado por enquanto; qualquer referencia antiga a AWS deve ser lida como historica.
- Framework: FastAPI.
- Banco: PostgreSQL via SQLAlchemy 2.x e Alembic.
- Schemas: Pydantic v2.
- Autenticacao: sessao Bearer persistida em banco.
- Autorizacao: RBAC, permissoes e views por empresa.
- Modulos: empresa, participantes, catalogo, fiscal, vendas, estoque, financeiro, contas a receber, caixa, conciliacao, fluxo de caixa, compras/pagar, relatorios, importacoes, seguranca, integracoes preparatorias e ferramentas internas.

## 2. Stack backend

| Area | Tecnologia |
|---|---|
| API | `fastapi==0.136.1`, `uvicorn[standard]==0.46.0` |
| ORM/migrations | `sqlalchemy==2.0.49`, `alembic==1.18.4` |
| Banco/driver | PostgreSQL, `psycopg[binary]==3.3.3` |
| Validacao/config | `pydantic==2.13.3`, `pydantic-settings==2.14.0`, `python-dotenv` |
| Datas/timezone | `tzdata==2026.2`, utilitarios em `app/shared/datetime.py` |
| PDF/planilhas/importacao | `reportlab`, `openpyxl`, `python-multipart` |
| HTTP externo | `httpx` |
| Seguranca | `bcrypt`, `cryptography.Fernet`, middlewares proprios |
| Testes | `pytest`, `httpx` |

## 3. Entrada da aplicacao

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/main.py` | Cria o app FastAPI, aplica middlewares, registra exception handlers, healthcheck e roteador global. |
| `backend/app/core/routes.py` | Agrega os routers dos modulos e aplica `enforce_session_tenant_scope` globalmente. |
| `backend/app/core/config.py` | Settings por variavel de ambiente, CORS, seguranca, bootstrap, migracao opt-in e validacao de ambiente. |
| `backend/app/core/database.py` | Engine SQLAlchemy, `SessionLocal`, `get_db` e healthcheck minimo. |
| `backend/app/db/base.py` | Importa todos os modelos SQLAlchemy para Alembic/metadata oficial. |
| `backend/alembic/env.py` | Usa `settings.resolved_database_url` e `Base.metadata` com `compare_type` e `compare_server_default`. |

Fluxo de startup:

```text
main.py
-> configure_logging()
-> validate_runtime_configuration()
-> se AUTO_MIGRATE_ON_STARTUP=true e nao for producao: alembic upgrade head
-> se DDL_FALLBACK_ENABLED=true somente local/dev: fallback DDL legado opt-in
-> include_router(core.routes.router)
```

Regra: Alembic e o caminho oficial de schema. O fallback DDL existe apenas como mecanismo legado local, opt-in, bloqueado fora de desenvolvimento.

## 4. Estrutura real

```text
backend/
  app/
    main.py
    core/
    db/
    shared/
    modules/
  alembic/
  tests/regression/
  tools/
  scripts/
```

Padrao predominante por modulo:

```text
db_models.py     modelo SQLAlchemy quando o modulo persiste dados
schemas.py       entrada/saida Pydantic
repository.py    fronteira com banco
service.py       regra de negocio
routes.py        camada HTTP fina
models.py        enums/modelos de dominio quando necessario
```

Excecoes reais:

- `management_reports` e `bi_analytics`: leitura agregada/relatorios, com SQL controlado.
- `imports`: parser, templates e commit de dados para dominios existentes.
- `demo`, `stress_tests`, `technical_regression`: modulos internos/diagnosticos.
- `sales`: possui geradores de PDF e pre-check fiscal.
- `fiscal_documents`: possui cliente HTTP Focus NFe.

## 5. Nucleo compartilhado

| Arquivo | Uso |
|---|---|
| `shared/money.py` | Decimal, arredondamento `ROUND_HALF_UP`, rateio e reconciliacao de centavos. Nunca usar `float` para dinheiro. |
| `shared/datetime.py` | UTC interno, America/Sao_Paulo para datas locais, vencimentos e competencias. |
| `shared/ids.py` | IDs internos no formato `<prefix>_<uuid-v4>` e validacoes de prefixo. |
| `shared/audit.py` | Modelo comum para eventos de auditoria, entity types, fontes e mascaramento conceitual. |
| `shared/audit_repository.py` | Persistencia de auditoria em `audit_events`. |
| `shared/schemas.py` | Contrato `ApiResponse`: `success`, `message`, `data`. |
| `shared/exceptions.py` | `KovirException` e `NotFoundException`. |
| `shared/db_models.py` | Modelos compartilhados, incluindo auditoria. |

## 6. Seguranca e tenant scope

### 6.1 Publico e autenticado

Rotas publicas:

- `/`
- `/auth/login`
- `/docs`
- `/redoc`
- `/openapi.json`

Bootstrap inicial:

- `/auth/bootstrap-admin` so passa se `BOOTSTRAP_ADMIN_ENABLED=true`, token `X-Bootstrap-Token` valido, token com pelo menos 32 caracteres e banco ainda sem usuarios.

Todas as demais rotas passam por:

```text
Authorization: Bearer <token>
-> resolve_principal_by_token()
-> company_id da sessao ativa
-> permissoes do usuario naquela empresa
-> enforce_session_tenant_scope()
```

### 6.2 Isolamento por empresa

`app/core/tenant_scope.py` aplica controle global:

- coleta `company_id` explicito em query/body/path;
- coleta IDs tecnicos por prefixo;
- resolve a empresa dona do recurso por tabela mapeada;
- bloqueia request que tente misturar empresa da sessao com empresa de outro recurso;
- ignora apenas `OPTIONS`, rotas publicas e bootstrap controlado.

Regra obrigatoria: services e repositories ainda devem filtrar por `company_id`. O middleware reduz risco, mas nao substitui autorizacao por recurso.

### 6.3 Permissoes principais

| Permissao | Uso |
|---|---|
| `users.manage` | Usuarios, roles, permissoes, membros e modulos internos administrativos. |
| `company.write` / `view.company` | Escrita/leitura de empresa. |
| `finance.read` / `finance.write` | Financeiro base e leitura financeira. |
| `payables.pay` | Pagamento de contas a pagar. |
| `approval.read` / `approval.decide` | Alcadas. |
| `reports.read` | Relatorios gerenciais. |
| `sales.view`, `sales.create`, `sales.close`, `sales.cancel`, `sales.pay`, `sales.unlock_closed` | Ciclo de vendas. |
| `participants.write`, `catalog.write`, `fiscal.write` | Escrita de cadastros especificos. |
| `stock.move`, `stock.purchase_entry` | Estoque. |
| `cash.receive`, `cash.reverse` | Baixas e estornos. |
| `fiscal.issue` | Emissao/sincronizacao/cancelamento fiscal. |
| `imports.run`, `view.imports` | Importacoes. |
| `technical.read`, `technical.run` | Diagnosticos internos. |
| `view.<aba>` | Permissao de exposicao de views do frontend. |

Roles padrao:

- `admin`: todas as permissoes.
- `finance_manager`: financeiro, alcadas e relatorios.
- `finance_operator`: financeiro operacional e alcadas de leitura.
- `viewer`: leitura minima.

Sessao:

- Token Bearer armazenado como hash.
- Duracao padrao: 30 minutos.
- Logout revoga sessao.
- Login tem rate limit em memoria por email/IP.

## 7. Middlewares e respostas seguras

| Middleware/handler | Regra |
|---|---|
| `RequestContextMiddleware` | Gera/propaga `X-Request-ID` e `X-Correlation-ID`. |
| `RequestSizeLimitMiddleware` | Bloqueia corpo acima de `MAX_REQUEST_BODY_BYTES` (default 10 MB). |
| `SecurityHeadersMiddleware` | Aplica CSP, no-store, frame/options/referrer/policies e HSTS quando configurado. |
| `CORSMiddleware` | Origem local padrao: `http://localhost:5173`, `http://127.0.0.1:5173`. |
| `exception_handlers.py` | 404/400 controlados; erro inesperado retorna 500 seguro sem stack trace ao cliente. |
| `logging.py` | Logs JSON/text com redacao de tokens, senhas, secrets e `DATABASE_URL`. |

## 8. Configuracao operacional

Principais variaveis:

| Variavel | Regra |
|---|---|
| `ENVIRONMENT` | `development`, `dev`, `local`, `test`, `production` ou `prod`. |
| `DATABASE_URL` | Sobrescreve `POSTGRES_*`; usar localmente apenas quando necessario. |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` / `POSTGRES_PORT` | Conexao local do backend quando `DATABASE_URL` nao estiver definido. Para o helper Docker local, usar `localhost:5433`. |
| `KOVIR_ERP_POSTGRES_DB` / `KOVIR_ERP_POSTGRES_USER` / `KOVIR_ERP_POSTGRES_PASSWORD` / `KOVIR_ERP_POSTGRES_HOST_PORT` | Variaveis exclusivas do `backend/docker-compose.yml` para subir somente PostgreSQL isolado do Kovir ERP. |
| `AUTO_MIGRATE_ON_STARTUP` | Permitido apenas fora de producao; default `false`. |
| `DDL_FALLBACK_ENABLED` | Legado local opt-in; default `false`. |
| `ENABLE_INTERNAL_MODULES` | Habilita modulos internos apenas fora de producao. |
| `BOOTSTRAP_ADMIN_ENABLED` / `BOOTSTRAP_ADMIN_TOKEN` | Setup inicial controlado. |
| `SECRET_ENCRYPTION_KEY` | Chave Fernet para segredos criptografados; obrigatoria para segredos em producao. |
| `CORS_ALLOWED_ORIGINS` | Deve ficar restritivo. |
| `FOCUS_NFE_TOKEN` / `FOCUS_NFE_ENVIRONMENT` | Integracao Focus NFe; preferir token por empresa criptografado quando aplicavel. |

Observacao: exemplos de producao em `.env.example` sao genericos e nao definem
deploy ativo. Nesta fase, o projeto continua local e sem dependencia de AWS/RDS.

PostgreSQL local via Docker:

- `backend/docker-compose.yml` e apenas helper de banco, nao stack completa.
- Porta padrao no host: `5433`, apontando para `5432` dentro do container.
- Container, volume e rede sao exclusivos: `kovir-erp-postgres`,
  `kovir_erp_postgres_data` e `kovir_erp_postgres_net`.
- Backend e frontend continuam rodando localmente via Python/FastAPI e Vite.

## 9. Modulos oficiais atuais

| Modulo | Prefixos/rotas | Papel | Persistencia |
|---|---|---|---|
| `company` | `/companies`, `/system/company-*` | Empresa, parametros fiscais/operacionais e auditoria. | Sim |
| `participants` | `/participants`, `/system/participant-*` | Clientes, fornecedores e terceiros. | Sim |
| `catalog` | `/catalog` | Produtos/servicos, SKU, barcode, fiscal/financeiro/estoque. | Sim |
| `fiscal_classification` | `/fiscal` | Perfis, classificacoes e regras fiscais item+natureza. | Sim |
| `sales` | `/sales` | Pedidos, ciclo quote/closed/paid/cancelled, PDFs, fiscal readiness. | Sim |
| `fiscal_documents` | `/fiscal-documents`, `/sales/{id}/invoice` | NF-e/NFC-e parcial via Focus NFe. | Sim |
| `stock` | `/stock` | Locais, saldos, lotes, movimentos, entradas e vinculos de venda. | Sim |
| `financial` | `/financial` | Plano financeiro base: contas, categorias, centros, termos e fechamento. | Sim |
| `accounts_receivable` | `/accounts-receivable` | Titulos a receber, historico, cancelamento e geracao a partir de venda. | Sim |
| `cash` | `/cash` | Baixas, movimentos internos, saldos e estornos. | Sim |
| `reconciliation` | `/reconciliation` | Importacao de extrato/OFX, linhas, sugestoes e matches. | Sim |
| `cash_flow` | `/cash-flow` | Visao agregada de caixa, previsoes e evidencias. | Leitura agregada |
| `purchases_payables` | `/purchases-payables` | Compras/despesas, contas a pagar, pagamento e exportacao. | Sim |
| `management_reports` | `/management-reports` | Saude MVP, ciclo financeiro, fechamento e pacote contador. | Leitura agregada |
| `imports` | `/imports` | Templates, preview e commit de importacao cadastral. | Escreve em dominios existentes |
| `security` | `/auth`, `/security` | Login, sessoes, roles, permissoes, alcadas e senha mestre. | Sim |

## 10. Modulos internos/condicionais

Estes routers sao registrados no app, mas protegidos por `require_internal_modules_enabled`.
Com `ENABLE_INTERNAL_MODULES=false` ou ambiente de producao, retornam 404.

| Modulo | Prefixo | Uso |
|---|---|---|
| `marketplaces` | `/marketplaces` | Fundacao de marketplace generico; ainda nao e fluxo produtivo completo. |
| `mercado_pago` | `/mercado-pago` | Fundacao de Mercado Pago; sem integracao financeira real completa. |
| `bi_analytics` | `/bi` | KPIs/exports analiticos internos. |
| `technical_regression` | `/technical-regression` | Diagnosticos e verificacoes tecnicas. |
| `stress_tests` | `/stress-tests` | Massa/stress controlado. |
| `demo` | `/demo` | Geracao/arquivamento de empresas demo. |

Regra: nao usar modulos internos como dependencia de operacao normal da v1.0 local.

## 11. Mapa de rotas por prefixo

Inventario extraido do app FastAPI:

| Prefixo | Rotas | Metodos |
|---|---:|---|
| `/accounts-receivable` | 11 | GET, PATCH, POST |
| `/auth` | 4 | GET, POST |
| `/bi` | 29 | GET |
| `/cash` | 11 | GET, POST |
| `/cash-flow` | 8 | GET |
| `/catalog` | 8 | GET, PATCH, POST |
| `/companies` | 5 | GET, PATCH, POST |
| `/demo` | 4 | GET, POST |
| `/financial` | 27 | GET, PATCH, POST |
| `/fiscal` | 12 | GET, PATCH, POST |
| `/fiscal-documents` | 3 | DELETE, GET, POST |
| `/health` | 1 | GET |
| `/imports` | 4 | GET, POST |
| `/management-reports` | 11 | GET |
| `/marketplaces` | 8 | GET, PATCH, POST |
| `/mercado-pago` | 12 | GET, PATCH, POST |
| `/participants` | 6 | GET, PATCH, POST |
| `/purchases-payables` | 20 | GET, PATCH, POST |
| `/reconciliation` | 13 | GET, POST |
| `/sales` | 22 | GET, PATCH, POST |
| `/security` | 16 | GET, PATCH, POST, PUT |
| `/stock` | 17 | GET, PATCH, POST |
| `/stress-tests` | 3 | GET, POST |
| `/system` | 14 | GET |
| `/technical-regression` | 6 | GET |

## 12. Fluxos criticos implementados

### 12.1 Venda

```text
POST /sales
-> cria pedido em quote
-> PATCH /sales/{id} permitido enquanto editavel
-> POST /sales/{id}/confirm
   -> lock transacional da venda
   -> valida itens, fiscal, estoque e natureza
   -> gera sale_number por empresa
   -> baixa estoque quando item controla estoque
   -> gera contas a receber por plano de pagamento
   -> grava historico/auditoria
-> POST /sales/{id}/cancel
   -> exige motivo
   -> reverte estoque se necessario
   -> cancela recebiveis se nao houver baixa ativa
-> POST /sales/{id}/reopen
   -> exige permissao sales.unlock_closed e senha mestre
```

`POST /sales/{id}/pay` existe como endpoint legado/controlado; a baixa oficial deve passar por `cash/settlements`.

### 12.2 Contas a receber e caixa

```text
financial_titles(direction='receivable')
-> POST /cash/settlements
   -> lock do titulo
   -> valida periodo aberto
   -> cria settlement
   -> cria financial_movement
   -> atualiza financial_account_balances
-> POST /cash/settlements/{id}/reverse ou /cash/movements/{id}/reverse
   -> cria reversao/estorno
   -> preserva trilha
```

### 12.3 Compras e contas a pagar

```text
POST /purchases-payables/purchases
-> POST /purchases-payables/purchases/{id}/confirm
   -> valida periodo aberto
   -> gera financial_titles(direction='payable')
   -> cria purchase_financial_links e historico
-> POST /purchases-payables/payments
   -> exige payables.pay
   -> quando acima da alcada, exige approval_request aprovado
   -> cria baixa/movimento interno
```

### 12.4 Conciliacao

```text
POST /reconciliation/statement-imports ou /ofx-text
-> bank_statement_imports + bank_statement_lines
-> sugestoes por linha
-> POST /reconciliation/matches
   -> lock da linha e movimento
   -> valida mesma empresa, conta, direcao, status e tolerancia
   -> cria reconciliation_match
   -> atualiza status da linha e movimento
```

Extrato externo nunca altera saldo interno sozinho.

### 12.5 Estoque

```text
stock_locations
-> stock_purchase_entries / stock_movements
-> stock_balances e stock_lots atualizados transacionalmente
-> venda confirmada gera saida vinculada
-> venda cancelada gera reversao
```

O movimento e a trilha auditavel; saldos e lotes sao derivados.

### 12.6 Fiscal

```text
/sales/{id}/invoice-readiness
-> valida readiness fiscal
/sales/{id}/invoice
-> fiscal_documents.service
-> monta payload Focus NFe
-> usa token global ou token da empresa descriptografado
-> persiste resposta/status em fiscal_documents
```

Status: implementacao parcial via Focus NFe. Nao ha ainda subsistema fiscal completo com itens fiscais documentais, eventos fiscais, XML estruturado persistido, contingencia e inutilizacao.

### 12.7 Importacoes

```text
GET /imports/templates
POST /imports/{target}/preview
POST /imports/{target}/commit
```

Targets atuais: participantes, produtos e classificacoes fiscais. O commit respeita empresa ativa, `company.allow_imports`, duplicidade e valida os schemas de destino.

## 13. Regras de performance backend

- Toda listagem operacional deve filtrar por `company_id`.
- Listagens devem usar `limit` e `offset`; padrao comum: 50, teto comum: 200.
- Excecoes com teto 5000 existem para exportacao/evidencia operacional, nao para UI normal.
- Dashboards e cards devem vir de endpoints agregados, nao de soma local de pagina.
- Repositories devem filtrar no SQL, nao carregar tudo e filtrar em memoria.
- Evitar query dentro de loop; usar join, agregacao ou mapa carregado em consulta unica.
- Novos indices devem acompanhar filtros reais, especialmente `(company_id, status)`, datas, participante, conta, item e source.
- Exports grandes devem ter limite, filtro ou evoluir para job assincrono.

## 14. Regras de transacao e concorrencia

Usar transacao/lock quando houver:

- confirmacao/cancelamento/reabertura de venda;
- consumo ou reversao de estoque/lote;
- baixa, pagamento, estorno e movimento financeiro;
- conciliacao ou reversao de match;
- importacao com varias linhas;
- integracao externa com idempotencia por `source_id` ou ID externo.

Padroes reais ja usados:

- `with_for_update()` em venda, titulos, movimentos, saldos, lotes e reconciliacao.
- `company_id + source_type + source_id` para idempotencia financeira.
- unique de IDs externos em marketplaces/Mercado Pago.
- historicos de status para vendas, compras e titulos.
- auditoria com actor/source/request/correlation quando disponivel.

## 15. Contrato de API

Contrato comum:

```json
{
  "success": true,
  "message": "Mensagem operacional.",
  "data": {}
}
```

Regras:

- Entrada deve usar schema Pydantic ou parametros `Query` com limites.
- Resposta nao deve expor hash, salt, token, segredo ou payload sensivel bruto.
- Erro inesperado deve retornar mensagem generica e registrar log redigido.
- Rotas sensiveis precisam de permissao explicita.
- Rotas de detalhe precisam validar tenant/ownership.
- Rotas de escrita devem validar estado atual do recurso no service.

## 16. Testes e ferramentas

Testes versionados:

```text
backend/tests/regression/
```

Cobertura real inclui:

- autenticacao, permissoes e tenant scope;
- auditoria e redacao de logs;
- ciclo de venda, cancelamento, reabertura, PDFs e numeracao concorrente;
- estoque/lote em vendas;
- financeiro base, contas a receber, caixa, fluxo, conciliacao, compras/pagar;
- performance de modulos financeiros/estoque;
- relatorios gerenciais e BI;
- imports;
- startup/configuracao de producao.

Ferramentas locais:

```text
backend/tools/
backend/scripts/
```

Uso:

- stress local;
- diagnostico tecnico;
- reset de dados de desenvolvimento preservando uma empresa;
- seeds locais.

Regra: ferramentas locais nao sao API, nao substituem testes de regressao e nao devem ser usadas em producao. O reset local preserva `alembic_version`, mantem uma empresa escolhida e limpa dados operacionais; exige dry-run/confirmacao propria.

Comandos padrao locais:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\regression -q
alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

## 17. Gaps e riscos atuais

| Risco | Impacto | Acao recomendada |
|---|---|---|
| `financial_titles.title_name` existe em migration e relatorios, mas nao no modelo SQLAlchemy atual. | Relatorios podem falhar em schemas recriados por metadata ou testes. | Alinhar modelo/schemas/services ou remover dependencia da coluna. |
| Rotas internas aparecem registradas no app. | Superficie de OpenAPI/descoberta maior, embora bloqueada por 404 quando desabilitada. | Manter `ENABLE_INTERNAL_MODULES=false` por padrao e avaliar ocultar de schema se necessario. |
| `fiscal_documents` e Focus NFe estao parciais. | Risco de confundir emissao basica com modulo fiscal completo. | Evoluir fiscal com camada documental completa antes de prometer operacao oficial ampla. |
| Mercado Pago e marketplaces sao fundacoes. | Ainda nao ha baixa financeira externa completa, webhooks seguros e reprocessamento real. | Manter interno ate contrato financeiro transacional estar pronto. |
| Alguns endpoints de evidencia/export usam limite alto. | Risco de carga se usados como UI normal. | Usar filtros, paginacao e futuramente job assincrono para volumes maiores. |
| Fallback DDL legado existe. | Risco de drift se usado como rotina. | Usar somente local/dev opt-in; Alembic segue oficial. |

## 18. Checklist para evoluir backend

- Consultar `docs/MAPA_GLOBAL_BANCO_DE_DADOS.md` antes de alterar schema.
- Confirmar modulo existente antes de criar modulo novo.
- Criar/atualizar migration Alembic para qualquer schema change.
- Validar entrada com Pydantic e regra de negocio no service.
- Nunca confiar em `company_id`, permissao, status ou valores vindos do frontend sem revalidar.
- Aplicar `company_id` em repository e validar ownership em detalhe/escrita.
- Definir permissao backend por rota sensivel.
- Usar transacao e lock nos fluxos financeiros, estoque, conciliacao e venda.
- Registrar auditoria/historico em mudanca sensivel.
- Manter listagens paginadas e com limites.
- Usar Decimal/Numeric para dinheiro.
- Nao registrar secrets em logs.
- Rodar teste regressivo compativel com o modulo alterado.
