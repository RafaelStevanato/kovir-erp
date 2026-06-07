# Kovir ERP

ERP modular da STVN Software para PMEs brasileiras, focado em operacao local da
versao 1.0.0.

O Kovir organiza cadastros, produtos, estoque, pedidos, financeiro, contas a
receber, contas a pagar, caixa, conciliacao bancaria, relatorios e seguranca em
uma base multiusuario e multiempresa.

## Status oficial

- Desenvolvimento atual: local.
- Linha de trabalho: v1.0.0.
- Deploy AWS do ERP: cancelado por enquanto.
- Documentos antigos sobre AWS, staging, RDS, ALB, CloudWatch, S3 ou
  app.erpkovir.com.br sao historicos e nao representam ambiente ativo.
- Docker segue permitido como opcao futura, mas o setup Docker/deploy anterior do
  Kovir ERP foi descartado. Se Docker for recriado, deve partir do zero.
- Nome legado: Fluxor ERP. Pode aparecer em historico, scripts ou documentos
  antigos, mas a marca oficial e Kovir ERP.

## Stack

Backend:

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Pydantic v2
- pytest

Frontend:

- React 19
- TypeScript 6
- Vite 8
- Tailwind CSS 4
- lucide-react
- ESLint 10

## Estrutura

```text
backend/
  app/main.py
  app/core/
  app/shared/
  app/modules/
  alembic/
  tests/regression/
  tools/

frontend/
  src/App.tsx
  src/main.tsx
  src/features/
  src/layouts/
  src/lib/
  src/config/
  src/routes/
```

Documentacao oficial consolidada na raiz:

```text
CLAUDE.md
README.md
PROJETO_LOG.md
```

## Modulos principais

Escopo operacional da v1.0.0:

- Empresa e contexto multiempresa.
- Usuarios, sessoes Bearer, RBAC, permissoes e alcadas.
- Participantes.
- Catalogo de produtos e servicos.
- Classificacao fiscal base.
- Importacoes por planilhas.
- Pedidos/vendas.
- Estoque com movimentos, lotes e rastreabilidade.
- Financeiro base: plano de contas, categorias, centros de custo, contas
  financeiras e condicoes.
- Contas a receber.
- Caixa, baixas e movimentos financeiros.
- Conciliacao bancaria.
- Fluxo de caixa.
- Compras, despesas e contas a pagar.
- Relatorios gerenciais.

Modulos preparados, internos ou futuros:

- Mercado Pago real.
- Marketplaces reais.
- BI/KPIs avancados.
- IA.
- Gestao facil.
- Stress tests e regressao tecnica como ferramentas internas.
- Emissao fiscal completa/homologada.

## Regras de dominio

- Venda nao e recebimento.
- Compra/despesa nao e pagamento.
- Titulo financeiro nao e dinheiro movimentado.
- Baixa nao e conciliacao.
- Extrato bancario e evidencia externa; nao altera saldo interno sozinho.
- Conciliacao vincula extrato a movimento interno.
- Documento fiscal nao substitui venda, compra, titulo, baixa, movimento, estoque
  ou conciliacao.
- Relatorios e fluxo de caixa exibem saude, pendencias e divergencias; nao
  corrigem dado ruim.

## Setup local

### PostgreSQL local via Docker

Opcionalmente, o PostgreSQL local pode rodar isolado em Docker. Este helper usa
container, volume, rede e porta do host exclusivos do Kovir ERP, evitando
interferencia com outros projetos como o Kovir Cash.

Porta padrao no host:

```text
localhost:5433 -> container:5432
```

Subir somente o PostgreSQL:

```powershell
cd backend
$env:KOVIR_ERP_POSTGRES_PASSWORD="<senha-local-forte>"
docker compose up -d postgres
```

Variaveis opcionais do compose:

```text
KOVIR_ERP_POSTGRES_DB=kovir_erp
KOVIR_ERP_POSTGRES_USER=kovir_erp_app
KOVIR_ERP_POSTGRES_HOST_PORT=5433
```

No `backend/.env`, aponte o backend para a mesma porta e credenciais:

```text
POSTGRES_DB="kovir_erp"
POSTGRES_USER="kovir_erp_app"
POSTGRES_PASSWORD="<senha-local-forte>"
POSTGRES_HOST="localhost"
POSTGRES_PORT="5433"
```

Se `DATABASE_URL` estiver definido, ele sobrescreve `POSTGRES_*`. Nesse caso,
ajuste para:

```text
DATABASE_URL="postgresql+psycopg://kovir_erp_app:<senha-local-forte>@localhost:5433/kovir_erp"
```

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt pytest
alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

Backend local:

```text
http://127.0.0.1:8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend local:

```text
http://localhost:5173
```

O frontend usa `/api` por padrao, com proxy do Vite para
`http://127.0.0.1:8000`.

## Bootstrap local

O bootstrap inicial deve ser usado apenas em ambiente local controlado:

```text
BOOTSTRAP_ADMIN_ENABLED=true
BOOTSTRAP_ADMIN_TOKEN=<token-forte>
```

Depois do primeiro administrador:

```text
BOOTSTRAP_ADMIN_ENABLED=false
```

Nunca versionar tokens, senhas, strings de banco ou chaves privadas.

## Validacao

Backend:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\regression -q
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
```

Migrations:

```powershell
cd backend
alembic upgrade head
```

Quando alterar modelos SQLAlchemy:

```powershell
cd backend
alembic revision --autogenerate -m "<mensagem>"
alembic upgrade head
```

## Seguranca

- O frontend nunca e fonte de verdade.
- Toda regra critica deve ser validada no backend.
- Toda rota protegida deve validar autenticacao, autorizacao e tenant scope.
- Listagens devem ter limite.
- Operacoes financeiras, estoque, status, conciliacao e numeracao devem considerar
  transacao, lock e idempotencia quando aplicavel.
- Logs nao devem expor senhas, tokens, chaves, dados bancarios ou payloads
  sensiveis completos.

## Docker

Docker nao e o caminho operacional atual para rodar o Kovir ERP completo.

O desenvolvimento oficial segue local com Python, PostgreSQL e Vite. Os artefatos
anteriores de Docker/deploy/AWS foram descartados durante a limpeza do projeto.
O `backend/docker-compose.yml` atual e apenas um helper local isolado para
PostgreSQL, com porta padrao `5433`, volume `kovir_erp_postgres_data`, rede
`kovir_erp_postgres_net` e container `kovir-erp-postgres`.

Se um novo setup Docker completo for necessario, ele deve ser desenhado do zero,
incluindo politica de secrets, rede, volumes, migrations, healthchecks, build de
frontend, logs e validacao de seguranca.

## Observacoes

- `backend/.env.example` e `frontend/.env.example` ainda podem conter referencias
  historicas a deploy externo; para o ERP, considere desenvolvimento local como
  estado vigente.
- Materiais antigos de AWS/deploy foram removidos ou deixados apenas como
  contexto legado fora da operacao vigente.
