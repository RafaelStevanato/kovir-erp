# CLAUDE.md - Kovir ERP

Contrato operacional para Claude Code. Este arquivo nao e documentacao humana.
Execute como regras de trabalho, com foco em codigo seguro, correto, local e
validado.

## 0. Regras absolutas

- Responda sempre em portugues do Brasil.
- Trabalhe somente dentro da raiz deste repositorio.
- Nao leia, crie ou edite worktrees separadas.
- Nao reverta alteracoes existentes do usuario sem pedido explicito.
- Nao use comandos destrutivos (`git reset --hard`, checkout de arquivos,
  delecao recursiva ampla) sem pedido explicito e verificacao do alvo.
- Faca exatamente o pedido. Nao amplie escopo por iniciativa propria.
- Prefira editar arquivos existentes. Nao crie docs novas sem pedido explicito.
- Use `rg`/`rg --files` antes de alternativas mais lentas.
- Leia primeiro os arquivos relevantes; nao abra arquivos aleatorios.
- Preserve arquitetura, contratos de API, tenant scope, auditoria e testes.
- Antes de finalizar, rode validacao compativel ou informe o motivo real.
- Se o usuario restringir o output, obedeca literalmente.
- Toda alteracao efetiva no projeto, a partir desta regra, deve terminar com
  commit e push para o GitHub, salvo bloqueio tecnico real informado ao usuario.

## 1. Estado oficial do projeto

- Produto oficial: Kovir ERP, STVN Software.
- Nome legado: Fluxor ERP. Pode existir em historico/codigo; nao introduzir novo
  branding legado.
- Linha atual: desenvolvimento local da versao 1.0.0.
- Deploy AWS do ERP: cancelado por enquanto. Nao tratar AWS, RDS, ALB,
  CloudFront, CloudWatch, S3, staging ou app.erpkovir.com.br como ativos.
- Docker: permitido como opcao futura/local, mas o setup Docker/deploy anterior
  foi descartado. Qualquer Docker novo deve ser desenhado e validado do zero.
- `Contextos/`: historico/apoio. Nao usar como fonte ativa se os 4 mapas em
  `docs/` e o codigo real forem suficientes.

## 2. Fontes de verdade e protocolo de leitura

Ordem em caso de conflito:

1. Codigo backend, migrations Alembic e testes de regressao.
2. `docs/MAPA_GLOBAL_BANCO_DE_DADOS.md`.
3. `docs/MAPA_GLOBAL_BACKEND.md`.
4. `docs/REGRAS_DE_NEGOCIO.md`.
5. `docs/MAPA_GLOBAL_FRONTEND.md`.
6. README/PROJETO_LOG/contextos historicos, apenas como apoio.

Mapas oficiais:

- Banco: `docs/MAPA_GLOBAL_BANCO_DE_DADOS.md`.
- Backend: `docs/MAPA_GLOBAL_BACKEND.md`.
- Frontend: `docs/MAPA_GLOBAL_FRONTEND.md`.
- Negocio: `docs/REGRAS_DE_NEGOCIO.md`.

Antes de alterar:

- Backend/API: leia `MAPA_GLOBAL_BACKEND`, `REGRAS_DE_NEGOCIO` e o modulo real.
- Banco/schema: leia `MAPA_GLOBAL_BANCO_DE_DADOS`, migrations, modelos e testes.
- Frontend: leia `MAPA_GLOBAL_FRONTEND`, feature real e contrato de API.
- Regra financeira/fiscal/estoque/seguranca: leia `REGRAS_DE_NEGOCIO` e backend.
- Se documento e codigo divergirem, confie no codigo/migration/teste e sinalize.

## 2.1 Sprint, documentacao e GitHub obrigatorios

Toda mudanca deve ser tratada como uma sprint curta, mesmo quando for pequena.
Antes de editar, defina mentalmente:

- Objetivo final desejado.
- Escopo exato da mudanca.
- Atividades necessarias para chegar ao objetivo.
- Riscos de seguranca, dados, performance, tenant scope e regressao.
- Documentos que precisam ser atualizados.
- Validacoes minimas.
- Arquivos que devem entrar no commit.

Documentacao obrigatoria:

- `PROJETO_LOG.md`: toda alteracao efetiva deve registrar uma entrada clara de
  sprint/atividade com objetivo, decisoes tecnicas, arquivos afetados,
  validacao e commit quando disponivel.
- `docs/MAPA_GLOBAL_BANCO_DE_DADOS.md`: atualizar quando houver mudanca de
  schema, migration, relacionamento, indice, constraint, persistencia, seed,
  reset ou regra estrutural de banco.
- `docs/MAPA_GLOBAL_BACKEND.md`: atualizar quando houver mudanca em API,
  modulo backend, service, repository, seguranca, permissao, integracao,
  configuracao, teste backend ou comportamento operacional.
- `docs/MAPA_GLOBAL_FRONTEND.md`: atualizar quando houver mudanca em tela,
  navegacao, feature frontend, contrato de consumo de API, permissao visual,
  estado, exportacao, UX operacional ou build frontend.
- `docs/REGRAS_DE_NEGOCIO.md`: atualizar quando houver mudanca de regra
  financeira, fiscal, estoque, vendas, compras, conciliacao, seguranca,
  alcada, workflow, status, auditoria ou limite funcional.
- `README.md`: atualizar quando houver mudanca em setup, execucao local,
  dependencias, comandos, requisitos ou fluxo de bootstrap.

Git obrigatorio:

- Nunca misture alteracoes fora do escopo no mesmo commit.
- Antes de stagear, rode `git status --short` e identifique arquivos ja sujos.
- Stage apenas arquivos do escopo da sprint atual.
- Nunca stagear `.env`, caches, `.venv`, build artifacts, logs, credenciais,
  dumps, backups ou arquivos gerados sem necessidade.
- Depois de validar, criar commit tecnico e objetivo.
- Depois do commit, fazer push para o GitHub no branch atual.
- Se push/commit falhar por credencial, rede, hook, conflito ou worktree
  impossivel de isolar, informe claramente o bloqueio e o proximo passo.
- Se houver alteracoes antigas de usuario no mesmo arquivo e nao for possivel
  separar com seguranca, pare e pergunte antes de commit.

## 3. Stack e estrutura real

Backend:

- FastAPI, PostgreSQL, SQLAlchemy 2.x, Alembic, Pydantic v2,
  pydantic-settings, pytest, bcrypt, cryptography/Fernet.
- Entrada: `backend/app/main.py`.
- Router global: `backend/app/core/routes.py`.
- Config: `backend/app/core/config.py`.
- Tenant scope: `backend/app/core/tenant_scope.py`.
- Seguranca: `backend/app/modules/security/`.
- Metadata Alembic: `backend/app/db/base.py`.

Frontend:

- React 19, TypeScript 6, Vite 8, Tailwind CSS 4, lucide-react, ESLint 10.
- Entrada: `frontend/src/main.tsx`.
- App/sessao/navegacao: `frontend/src/App.tsx`, `frontend/src/pages/DashboardPage.tsx`,
  `frontend/src/layouts/`.
- API client: `frontend/src/lib/api.ts`.
- Lazy views: `frontend/src/routes/lazyViews.ts`.

Estrutura esperada:

```text
backend/
  app/core/
  app/db/
  app/shared/
  app/modules/
  alembic/versions/
  tests/regression/
  scripts/
  tools/
frontend/
  src/components/
  src/config/
  src/features/
  src/layouts/
  src/lib/
  src/pages/
  src/routes/
docs/
  MAPA_GLOBAL_BANCO_DE_DADOS.md
  MAPA_GLOBAL_BACKEND.md
  MAPA_GLOBAL_FRONTEND.md
  REGRAS_DE_NEGOCIO.md
```

## 4. Modulos atuais

Backend oficiais:

- `company`, `participants`, `catalog`, `fiscal_classification`,
  `fiscal_documents`, `sales`, `stock`, `financial`,
  `accounts_receivable`, `cash`, `reconciliation`, `cash_flow`,
  `purchases_payables`, `management_reports`, `imports`, `security`.

Backend internos/preparatorios:

- `marketplaces`, `mercado_pago`, `bi_analytics`, `technical_regression`,
  `stress_tests`, `demo`.
- Internos dependem de `ENABLE_INTERNAL_MODULES`; nao habilitar em producao.
- Marketplaces/Mercado Pago sao fundacoes, nao operacao completa pronta.

Frontend segue `frontend/src/features/<dominio>/` e usa `AppView` interno, sem
React Router no app autenticado.

## 5. Invariantes de seguranca

- Nunca confie no frontend.
- Nunca confie em `company_id`, permissao, role, status, preco, saldo, desconto,
  ID, localStorage, campo oculto ou botao desabilitado vindo do cliente.
- Toda rota protegida exige Bearer token, principal, empresa ativa e permissao.
- Toda acao sensivel valida autorizacao, ownership e estado atual no backend.
- Toda query operacional filtra por `company_id` no service/repository; middleware
  global nao substitui filtro de dominio.
- Proteger contra IDOR/BOLA, Broken Access Control, mass assignment, SQLi, XSS,
  SSRF, CSRF quando aplicavel, path traversal, upload inseguro, CORS permissivo,
  erros verbosos, logs com segredo e vazamento entre tenants.
- Segredos ficam em `.env` local ou cofre externo. Nunca versionar credenciais.
- Logs/auditoria nao podem gravar senha, token, secret, chave de API, string de
  conexao, dados bancarios sensiveis ou payload sensivel integral.

## 6. Invariantes de negocio

- Venda nao e recebimento.
- Compra/despesa nao e pagamento.
- Titulo financeiro nao e dinheiro movimentado.
- Baixa/settlement nao e conciliacao.
- Extrato bancario e evidencia externa; nao altera saldo interno sozinho.
- Conciliacao vincula extrato a movimento interno; nao cria a operacao original.
- Documento fiscal nao substitui venda, compra, titulo, baixa, estoque ou caixa.
- Fluxo de caixa, BI e relatorios sao leitura/diagnostico; nao corrigem dado ruim.
- Fatos financeiros, fiscais, estoque, conciliacao e auditoria nao sao apagados no
  fluxo normal; use status, cancelamento, estorno, reversao ou historico.
- Dinheiro usa `Decimal`/`Numeric(18, 2)` e nunca `float`.
- Quantidade de estoque usa precisao adequada, normalmente 4 casas.
- Regras futuras nao implementadas nao podem ser prometidas como disponiveis.

Fluxos criticos:

- Venda: `QUOTE -> CLOSED -> PAID/CANCELLED`.
- `POST /sales/{id}/confirm`: fecha pedido, numera, gera efeitos integrados.
- Reabertura de venda fechada exige senha mestre com bcrypt e permissao
  `sales.unlock_closed`.
- Recebimento direto de pedido e legado/desativado na v1.0; baixa correta passa
  pelo financeiro/caixa.
- Compra/despesa confirmada gera titulo a pagar quando aplicavel.
- Pagamento a pagar exige `payables.pay`; acima de alcada exige aprovacao.
- Baixa gera movimento interno; conciliacao e etapa separada.
- Estoque deve ser alterado por movimento rastreavel, transacional e por empresa.

## 7. Backend - padrao obrigatorio

Padrao por modulo quando aplicavel:

```text
db_models.py
schemas.py
repository.py
service.py
routes.py
models.py
```

Obrigatorio:

- Rotas finas; regra de negocio em service.
- Pydantic para entrada/saida.
- Repositories para persistencia quando o modulo ja usa esse padrao.
- Validacao allowlist de campos; rejeitar mass assignment.
- DTOs/respostas explicitas; nao retornar entidade interna crua sem criterio.
- Exceptions compartilhadas e resposta segura ao usuario.
- Auditoria/historico em mudanca sensivel.
- Transacao em operacoes que alteram multiplas tabelas.
- Locks/controle concorrente em venda, estoque, pagamento, baixa, conciliacao,
  status e numeracao.

Proibido:

- Regra critica apenas na rota ou frontend.
- Endpoint de listagem sem limite se dados puderem crescer.
- SQL bruto sem necessidade.
- `print` em codigo de producao.
- Excecao engolida.
- Alterar modelo sem migration.
- Remover validacao/autorizacao para melhorar performance.

## 8. Banco de dados

- PostgreSQL e Alembic sao oficiais.
- Qualquer schema change exige migration em `backend/alembic/versions/`.
- Atualize `backend/app/db/base.py` se novo modelo precisar entrar no metadata.
- Use FKs, uniques, checks e indices para integridade critica sempre que possivel.
- Indices devem considerar `company_id`, filtros frequentes e ordenacao.
- Listagens exigem limite, filtros e ordenacao previsivel.
- Evite N+1, query em loop e carga grande em memoria.
- Saldos materializados (`stock_balances`, `stock_lots`,
  `financial_account_balances`) derivam de movimentos; nao trate como trilha
  primaria.
- Antes de mexer em financeiro, estoque, conciliacao ou fiscal, leia o mapa de
  banco e os testes relacionados.

Risco conhecido: `financial_titles.title_name` existe em migration/relatorios,
mas o modelo SQLAlchemy atual pode nao declarar a coluna. Verifique antes de
assumir contrato.

## 9. Frontend - padrao obrigatorio

- Frontend e interface; backend e fonte de verdade.
- Use `frontend/src/lib/api.ts` para chamadas HTTP.
- Preserve contrato `ApiResponse` quando o endpoint usar esse envelope.
- Tipos especificos; evite `any`. Use `unknown` + narrowing quando necessario.
- Estados obrigatorios: loading, erro, vazio, sucesso.
- Permissoes/allowedViews controlam UI, nao autorizacao final.
- Nao calcular dinheiro oficial, saldo, permissao final ou regra fiscal no
  frontend.
- Nao guardar secrets em `VITE_*`, localStorage ou codigo.
- Nao usar `console.log` em codigo final.
- Nao usar `dangerouslySetInnerHTML` sem justificativa forte e sanitizacao.
- Buscas/listagens grandes devem consultar backend com filtros, limite e debounce.
- Preserve UX operacional: telas densas, claras, sem marketing/hero desnecessario.

## 10. Performance, concorrencia e escala

- Codigo deve ser simples, mas nao ingenuo.
- Avalie custo de banco, trafego, memoria, renderizacao e concorrencia.
- Paginacao obrigatoria em listas crescentes.
- Use debounce em buscas do frontend.
- Evite chamadas duplicadas e renderizacoes desnecessarias.
- Export/import pesado deve considerar job/fila no futuro; nao bloquear request
  com volume grande sem limite.
- Cache somente com isolamento por usuario/empresa, TTL e invalidacao. Nunca cache
  global de dado multiempresa.
- Operacoes idempotentes precisam chave/constraint/deduplicacao quando podem ser
  repetidas por retry, webhook, importacao ou duplo clique.

## 11. Validacao local

Backend:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\regression -q
alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
npm run dev
```

Schema:

```powershell
cd backend
alembic revision --autogenerate -m "<mensagem>"
alembic upgrade head
```

Escolha validacao proporcional ao escopo:

- Docs/config: `git diff --check`.
- Backend modulo unico: teste regressivo especifico + relacionados.
- Backend compartilhado/schema/seguranca: suite regressiva mais ampla.
- Frontend: `npm run lint` e `npm run build`.
- E2E visual/local quando alterar fluxo de tela relevante.

Se nao rodar algo, diga exatamente o comando nao executado e o motivo.

## 12. Resposta ao usuario

Padrao curto:

```text
Feito.

Arquivos alterados:
- caminho/arquivo.ext - resumo curto

Validacao:
- comando - resultado

Observacoes:
- somente se necessario
```

Falha:

```text
Nao concluido.

Falha:
- ...

Causa provavel:
- ...

Proximo ajuste:
- ...
```

Em analise/review, liste achados primeiro, com arquivo/linha e severidade.

## 13. Checklist antes de finalizar

- Escopo pedido foi atendido sem refatoracao desnecessaria.
- Docs oficiais relevantes foram consultadas.
- Tenant scope, permissao e ownership foram preservados.
- Listagens continuam paginadas/limitadas.
- Operacoes criticas continuam transacionais/auditaveis.
- Schema e migration estao alinhados quando houve mudanca de banco.
- Frontend nao virou fonte de verdade.
- Nao ha secrets, logs perigosos, `print`, `console.log` ou `any` novo.
- Validacao compativel foi executada ou a impossibilidade foi reportada.
