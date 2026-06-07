# PROJETO_LOG.md

Historico consolidado do Kovir ERP, organizado em sprints.

Status base deste log:

- Projeto: Kovir ERP.
- Linha atual: v1.0.0 local.
- Deploy AWS do ERP: cancelado por enquanto.
- Nome legado em documentos antigos: Fluxor ERP.

## Sprint 0 - Nucleo tecnico

Objetivo:

- Criar base tecnica reutilizavel para dinheiro, datas, IDs, auditoria e
  respostas padronizadas.

Entregas:

- Backend FastAPI modular.
- PostgreSQL com SQLAlchemy e Alembic.
- `app/shared/money.py` para calculos monetarios com Decimal.
- Helpers de data, timezone Brasil e competencia.
- IDs tecnicos prefixados.
- Auditoria funcional e tecnica.
- Health check do banco.
- Tratamento padronizado de excecoes.

Regras consolidadas:

- Nunca usar `float` para dinheiro.
- Usar UTC internamente e America/Sao_Paulo para datas locais.
- IDs tecnicos nao devem ser a informacao principal para o usuario final.
- Dados sensiveis devem ser mascarados em auditoria e logs.

## Sprint 1 - Empresa e multiempresa

Objetivo:

- Estruturar empresa como tenant operacional do ERP.

Entregas:

- Cadastro de empresas.
- Campos fiscais e preferencias operacionais.
- Empresa ativa no frontend.
- Seletor global de empresa.
- Remount seguro de paginas ao trocar empresa.
- Correcao de buscas para respeitar empresa ativa real.

Regras consolidadas:

- Toda entidade operacional relevante deve pertencer a uma empresa.
- Nao usar `company_id` hardcoded.
- Dados entre empresas nao podem se misturar em busca, listagem, relatorio,
  exportacao ou cache.

## Sprint 2 - Participantes

Objetivo:

- Criar cadastro base de clientes, fornecedores, bancos, gateways,
  transportadoras e terceiros.

Entregas:

- Modulo backend `participants`.
- Feature frontend `participants`.
- Campos extras para operacao, fiscal e contato.
- Busca e selecao integradas aos demais modulos.

Regras consolidadas:

- Participante ativo e da mesma empresa e pre-requisito para vendas, compras e
  financeiro.
- Participante nao deve ser duplicado por fluxo operacional.

## Sprint 3 - Catalogo e classificacao fiscal

Objetivo:

- Criar base de produtos, servicos e classificacoes fiscais.

Entregas:

- Modulo `catalog`.
- Modulo `fiscal_classification`.
- Produtos e servicos.
- Marca/categoria.
- Perfis fiscais, NCM/CFOP e regras fiscais por item.
- Base de campos para NF-e.

Regras consolidadas:

- Produto controlado por estoque nao pode ignorar saldo/lote quando aplicavel.
- Fiscal no Kovir e preparacao e classificacao; nao prometer conformidade fiscal
  completa sem homologacao.

## Sprint 4 - Pedidos, vendas e ciclo comercial

Objetivo:

- Implementar ciclo de venda com numeracao, status, PDFs e integracao futura com
  financeiro/estoque.

Entregas:

- Modulo `sales`.
- Feature `orders`.
- Ciclo `QUOTE -> CLOSED -> PAID/CANCELLED`.
- `POST /sales/{id}/confirm`.
- Numeracao `PED-XXXXXX`.
- Historico de status.
- PDFs de proposta e commercial invoice.
- Senha mestre para reabrir pedido fechado.
- Permissao `sales.unlock_closed`.

Regras consolidadas:

- Venda nao e recebimento.
- Confirmacao de venda e evento transacional.
- Reabertura de pedido fechado exige controle forte.
- Recebimento direto por pedido foi desativado na v1.0; baixa deve ocorrer pelo
  modulo financeiro.

## Sprint 5 - Estoque operacional

Objetivo:

- Integrar estoque ao ciclo de vendas e compras.

Entregas:

- Modulo `stock`.
- Locais de estoque.
- Lotes.
- Movimentos.
- Saldos.
- Entrada de estoque por compra.
- Baixa de estoque ao confirmar venda.
- Reversao controlada no cancelamento.
- Testes de performance e regressao de estoque.

Regras consolidadas:

- Estoque exige rastreabilidade por movimento.
- Nao alterar saldo sem registrar fato de estoque.
- Operacoes concorrentes exigem transacao e lock.

## Sprint 6 - Cadastros financeiros base

Objetivo:

- Criar cadastros mestres financeiros antes dos fatos financeiros.

Entregas:

- Plano de contas.
- Categorias financeiras.
- Centros de custo.
- Contas financeiras.
- Condicoes de pagamento.
- Periodos financeiros.
- Defaults financeiros.

Regras consolidadas:

- Cadastro financeiro mestre vem antes de lancamento.
- Conta sintetica nao deve receber lancamento direto.
- Categoria, centro de custo e plano de contas nao sao a mesma coisa.
- Saldo inicial nao deve ser recriado como movimento comum depois de saldo
  materializado.

## Sprint 7 - Contas a receber

Objetivo:

- Transformar vendas e lancamentos manuais em titulos a receber.

Entregas:

- Modulo `accounts_receivable`.
- Tabela `financial_titles`.
- Historico de titulos.
- Vinculo `sale_financial_links`.
- Criacao manual de titulo.
- Geracao por venda.
- Cancelamento de titulo aberto.
- Listagem com filtros e paginacao.
- Testes de seguranca e performance.

Regras consolidadas:

- Titulo a receber nao e dinheiro em caixa.
- Geracao por venda deve ser idempotente.
- Titulo com baixa/movimento ativo nao deve ser cancelado diretamente.
- Titulo pertence a empresa da sessao.

## Sprint 8 - Caixa, baixas e movimentos

Objetivo:

- Registrar baixas, recebimentos e movimentos financeiros internos.

Entregas:

- Modulo `cash`.
- `settlements`.
- `financial_movements`.
- `financial_account_balances`.
- Recebimento de conta a receber.
- Movimento financeiro de entrada.
- Estorno com movimento reverso.
- Atualizacao de saldo interno.

Regras consolidadas:

- Baixa reduz saldo em aberto do titulo.
- Movimento financeiro altera saldo interno.
- Estorno nao apaga historico.
- Movimento conciliado nao deve ser revertido antes de desfazer conciliacao.

## Sprint 9 - Conciliacao bancaria

Objetivo:

- Separar extrato bancario de movimentos internos e criar conciliacao rastreavel.

Entregas:

- Modulo `reconciliation`.
- Importacao de extrato.
- Linhas de extrato.
- Matches de conciliacao.
- Sugestao de match.
- Confirmacao de match exato.
- Match com diferenca controlada.
- Estorno de match.
- Linha ignorada com justificativa.
- OFX parser inicial.

Regras consolidadas:

- Extrato nao altera saldo interno.
- Match exige mesma empresa, conta financeira, direcao e status conciliavel.
- Match duplicado deve ser bloqueado.
- Conciliacao divergente exige justificativa.

## Sprint 10 - Fluxo de caixa

Objetivo:

- Criar leitura consolidada de previsao, realizado, pendencias e conciliacao.

Entregas:

- Modulo `cash_flow`.
- Visao geral.
- Por dia.
- Por conta.
- Pendencias.
- Concilicao.
- Drill-down/evidencias.
- Exportacoes CSV/XLSX.
- Stress test de fluxo financeiro.

Regras consolidadas:

- Fluxo de caixa nao e DRE.
- Saldo interno vem de movimentos e saldos internos.
- Entrada/saida prevista vem de titulos.
- Realizado vem de baixas/movimentos.
- Dashboard nao corrige dado ruim; aponta onde corrigir.

## Sprint 11 - Compras, despesas e contas a pagar

Objetivo:

- Implementar ciclo de compras/despesas ate pagamento e movimento financeiro.

Entregas:

- Modulo `purchases_payables`.
- Compras/despesas.
- Titulos a pagar.
- Pagamento de titulo.
- Integracao com conta financeira.
- Overview de compras e contas a pagar.
- Melhoria da UI de filtros e exportacao.
- Stress financeiro end-to-end.

Regras consolidadas:

- Compra/despesa nao e pagamento.
- Titulo a pagar nao e dinheiro movimentado.
- Pagamento exige permissao `payables.pay`.
- Pagamento acima de alcada exige aprovacao.
- Pagamento gera movimento; conciliacao segue separada.

## Sprint 12 - Seguranca, usuarios e alcadas

Objetivo:

- Criar base multiusuario com permissoes, sessoes e aprovacao.

Entregas:

- Usuarios.
- Roles.
- Permissions.
- Company users.
- User sessions.
- Approval policies.
- Approval requests.
- Approval decisions.
- Security audit events.
- Master passwords.
- Dependencias de permissao.
- Tenant scope global.

Regras consolidadas:

- Autenticacao, autorizacao e ownership sao validacoes diferentes.
- Permissao do frontend nao e confiavel.
- Pagamento acima do limite exige aprovacao valida.
- Auditoria deve registrar ator real.
- Bootstrap admin e apenas setup local controlado.

## Sprint 13 - Relatorios gerenciais e saude do MVP

Objetivo:

- Dar visibilidade ao ciclo financeiro e as pendencias operacionais.

Entregas:

- Modulo `management_reports`.
- Saude do MVP.
- Ciclo financeiro.
- Pendencias operacionais.
- Titulos com referencia humana.
- Regras do backend.
- Exportacao CSV/XLSX.
- Frontend `ManagementReportsPage`.

Regras consolidadas:

- Relatorio nao substitui regra transacional.
- Pendencia operacional e informacao de produto, nao ruido visual.
- Relatorio deve preservar tenant scope e filtros.

## Sprint 14 - Importacoes

Objetivo:

- Permitir entrada controlada de dados por planilhas-base.

Entregas:

- Modulo `imports`.
- Templates e parser.
- Tela de importacao.
- Validacoes e permissao `imports.run`.

Regras consolidadas:

- Importacao nao pode confirmar fato sem validacao do backend.
- Campos devem ser normalizados e validados antes de persistir.
- Falhas devem ser reportadas de forma segura e acionavel.

## Sprint 15 - Fiscal documental

Objetivo:

- Criar fundacao de documentos fiscais preparatorios.

Entregas:

- Modulo `fiscal_documents`.
- Tabela `fiscal_documents`.
- Campos NF-e em empresas e classificacoes.
- Cliente Focus NFe preparado.
- Rotas protegidas por permissao fiscal.

Regras consolidadas:

- Documento fiscal e fato proprio.
- Documento fiscal nao cria baixa nem movimento financeiro automaticamente.
- Emissao fiscal completa/homologada nao deve ser prometida sem validacao
  especifica.

## Sprint 16 - Demo, stress e regressao tecnica

Objetivo:

- Criar ferramentas internas para validar massa realista, integridade e regressao.

Entregas:

- `backend/tools/stress_super_integration.py`.
- `backend/tools/stress_real_company_financial_demo.py`.
- `backend/tools/stress_financial_paths_end_to_end.py`.
- Modulos internos `stress_tests`, `technical_regression` e `demo`.
- Geracao de empresa demo realista.
- Arquivamento seguro de demos antigas.
- Testes de regressao para vendas, estoque, financeiro, seguranca, auditoria,
  relatorios e startup.

Regras consolidadas:

- Dados demo devem ser sinteticos.
- Demo deve usar services reais do backend.
- Operacoes demo/stress sao internas e nao entram no escopo comercial sem
  decisao explicita.

## Sprint 17 - Preparacao AWS cancelada

Objetivo original:

- Preparar deploy economico em AWS para staging/producao piloto.

Entregas historicas:

- Dockerfile backend.
- Scripts de deploy/rollback/migrations.
- Nginx para SPA + proxy `/api`.
- Runbooks AWS.
- Desenho de RDS, ALB, CloudWatch, S3, ASG e Cloudflare.
- Smoke test de staging.

Status atual:

- Cancelado por enquanto.
- Nao usar como fonte operacional ativa.
- Nao tratar `staging.erpkovir.com.br` ou `app.erpkovir.com.br` como ambiente
  vigente do ERP.
- Desenvolvimento segue local a partir da linha v1.0.0.
- O setup Docker/deploy anterior foi descartado na limpeza do projeto. Docker pode
  ser usado futuramente, mas qualquer novo desenho deve partir do zero, com nova
  revisao de seguranca, secrets, migracoes, healthchecks, volumes e operacao.

## Sprint 18 - Consolidacao documental

Objetivo:

- Reduzir documentacao ativa da raiz para tres arquivos oficiais.

Entregas:

- `CLAUDE.md` atualizado com estado real, regras para agentes e AWS cancelado.
- `README.md` criado para setup local e visao objetiva.
- `PROJETO_LOG.md` criado com historico por sprints.

Pendencias:

- Limpar ou arquivar documentos legados fora do conjunto oficial.
- Corrigir referencias AWS historicas em exemplos de ambiente quando solicitado.
- Alinhar versoes tecnicas de config com a linha documental v1.0.0 quando for
  decidido.

## Sprint 19 - Governanca operacional de mudancas

Objetivo:

- Tornar toda alteracao futura rastreavel, documentada, validada e commitada no
  GitHub.

Entregas:

- `CLAUDE.md` atualizado com ciclo obrigatorio de sprint curta para qualquer
  mudanca no projeto.
- Obrigatoriedade de atualizar `PROJETO_LOG.md` para toda alteracao efetiva.
- Obrigatoriedade de atualizar os quatro mapas oficiais em `docs/` quando a
  mudanca afetar banco, backend, frontend ou regra de negocio.
- Obrigatoriedade de commit tecnico e push para o GitHub ao final de cada
  sprint, sem misturar arquivos fora do escopo.

Regras consolidadas:

- Toda decisao deve ser pensada como atividade de sprint orientada ao objetivo
  final.
- O stage deve conter apenas arquivos do escopo atual.
- Alteracoes antigas, locais ou do usuario nao devem ser misturadas no commit.
- Se commit ou push falhar, o bloqueio deve ser reportado objetivamente.

## Sprint 20 - Marco Zero do repositorio novo

Objetivo:

- Preparar o projeto para um repositorio GitHub novo, limpo e alinhado com a
  identidade Kovir ERP.

Decisoes:

- O novo repositorio deve se chamar `kovir-erp`.
- O historico publico do novo repositorio deve iniciar fresco, sem reaproveitar
  o remoto antigo `fluxor-erp`.
- O remoto antigo `origin` apontando para `RafaelStevanato/fluxor-erp` foi
  removido localmente.
- O primeiro commit do repositorio novo deve representar o Marco Zero limpo do
  projeto, com mensagem sugerida: `chore: bootstrap kovir erp v1 local`.

Regras consolidadas:

- Nao reconectar o projeto ao remoto antigo.
- Antes do primeiro push do repositorio novo, concluir limpeza, seguranca,
  documentacao oficial e validacoes locais.
- O primeiro commit publico deve conter somente fonte ativa, documentacao oficial
  e arquivos necessarios para manutencao/evolucao local.

## Sprint 21 - Escopo versionavel do Marco Zero

Objetivo:

- Garantir que o repositorio novo contenha somente fonte ativa, documentacao
  oficial e configuracoes essenciais para manutencao local.

Entregas:

- Raiz reduzida a arquivos operacionais oficiais e pastas ativas do produto.
- `docs/` reduzida aos quatro mapas oficiais:
  `MAPA_GLOBAL_BANCO_DE_DADOS.md`, `MAPA_GLOBAL_BACKEND.md`,
  `MAPA_GLOBAL_FRONTEND.md` e `REGRAS_DE_NEGOCIO.md`.
- Documentos legados, contexto antigo, deploy AWS cancelado, scripts de deploy,
  assets obsoletos, READMEs internos e resultados JSON antigos foram removidos
  do escopo versionavel.
- `.gitignore` raiz reforcado para manter fora `Contextos/`, `deploy/`,
  backups, dumps, caches, ambientes locais e artefatos compactados.
- `backend/.gitignore` ajustado para nao bloquear `backend/tools/` nem
  `backend/docker-compose.yml`, pois ambos continuam como fontes locais ativas
  ou configuracoes versionaveis.

Regras consolidadas:

- `Contextos/`, `deploy/`, backups, dumps, caches, `.env`, `.venv`,
  `node_modules/` e builds locais nao entram no repositorio novo.
- Docker permanece permitido no repositorio, mas apenas como base local/futura
  explicitamente comentada; nenhum deploy AWS antigo deve ser tratado como ativo.
- O Marco Zero deve ser commitado com apenas arquivos ativos e verificaveis.

## Sprint 22 - Revisao de ignores antes do primeiro push

Objetivo:

- Garantir que o repositorio novo bloqueie arquivos locais, sensiveis, caches e
  artefatos gerados antes do primeiro push publico.

Entregas:

- `.gitignore` raiz reforcado para ambientes Python, Node, caches, cobertura,
  logs, dumps, backups, compactados e arquivos temporarios.
- `backend/.gitignore` reforcado para `.env`, `.venv`, bytecode, caches de teste,
  cobertura, logs, bancos locais, dumps e temporarios.
- `frontend/.gitignore` reforcado para `node_modules`, builds, cobertura,
  arquivos locais de ambiente e temporarios.

Regras consolidadas:

- `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `dist`, `node_modules`, logs,
  dumps, backups e arquivos temporarios nao entram no repositorio.
- `.env.example` continua permitido como contrato de configuracao local.
- `backend/tools/`, `backend/docker-compose.yml` e arquivos Docker comentados
  continuam versionaveis porque fazem parte do suporte local/futuro.

## Sprint 23 - Varredura de seguranca do Marco Zero

Objetivo:

- Remover sinais operacionais obsoletos e reduzir risco de publicar segredos,
  endpoints antigos ou branding legado no repositorio novo.

Entregas:

- Varredura em arquivos versionados para chaves privadas, tokens reais,
  credenciais, `DATABASE_URL`, URLs AWS antigas, dominio remoto cancelado e
  residuos fortes de branding legado.
- Nenhum padrao forte de chave privada ou token real foi identificado em fonte
  versionada.
- Exemplos de ambiente backend/frontend foram atualizados para producao futura
  generica, sem AWS/RDS/domino remoto antigo.
- Validacao de runtime em producao continua exigindo PostgreSQL remoto seguro,
  TLS, usuario nao-superuser, HTTPS/CORS restritivo e secrets obrigatorios, mas
  sem depender de RDS/AWS.
- Testes de startup/producao foram ajustados para exemplos genericos.
- Ferramentas locais trocaram variaveis/frase `Fluxor` por `Kovir`.
- CTA publico do frontend deixou de apontar para dominio remoto cancelado.

Regras consolidadas:

- AWS e dominios antigos podem aparecer apenas como historico de cancelamento,
  nunca como endpoint ativo ou exemplo operacional.
- Producao futura deve ser segura por invariantes tecnicos, nao por acoplamento
  a um provedor especifico.
- Branding legado nao deve permanecer em ferramentas operacionais.

## Sprint 24 - Validacao pre-push do Marco Zero

Objetivo:

- Executar a validacao local prevista antes do primeiro push publico do
  repositorio novo.

Validacoes executadas:

- `git status --short`: arvore versionada limpa no inicio da etapa.
- `git diff --check`: aprovado.
- `npm run lint`: aprovado.
- `npm run build`: aprovado.
- `python -m pytest tests/regression --collect-only -q`: aprovado, com 177 testes
  coletados.
- `python -m pytest tests/regression/test_production_startup.py -q`: ja aprovado
  na Sprint 23, com 35 testes.

Bloqueio:

- `python -m pytest tests/regression -q` nao concluiu porque testes que exigem
  contexto autenticado/banco ficaram bloqueados sem PostgreSQL local ativo.
- O servico Windows `postgresql-x64-17` existe, mas estava parado e nao iniciou
  neste ambiente.
- `127.0.0.1:5432` nao aceitou conexao.
- Tentativa com SQLite temporario confirmou que a regressao completa depende de
  schema migrado, falhando por ausencia da tabela `companies`.

Decisao:

- Frontend, documentacao/configuracao e testes de startup/seguranca de runtime
  estao validados.
- A regressao backend completa fica pendente ate um PostgreSQL local migrado
  estar disponivel.
- Antes do primeiro push publico final, subir PostgreSQL local, rodar
  `alembic upgrade head` e repetir `python -m pytest tests/regression -q`.

## Sprint 25 - Helper Docker isolado para PostgreSQL local

Objetivo:

- Permitir subir somente o PostgreSQL do Kovir ERP em Docker sem interferir em
  outros projetos locais, especialmente instancias que usem a porta `5432`.

Entregas:

- `backend/docker-compose.yml` mantido como helper exclusivo de PostgreSQL, nao
  como stack completa do ERP.
- Porta padrao do host alterada para `5433`, mantendo `5432` apenas dentro do
  container.
- Container, volume e rede dedicados: `kovir-erp-postgres`,
  `kovir_erp_postgres_data` e `kovir_erp_postgres_net`.
- Variaveis do compose passaram a usar prefixo `KOVIR_ERP_POSTGRES_*`, evitando
  colisao com variaveis genericas de outros projetos.
- `README.md`, `backend/.env.example` e mapas oficiais atualizados com o fluxo
  local.

Decisoes tecnicas:

- Backend e frontend continuam rodando localmente por Python/FastAPI e Vite.
- A senha do PostgreSQL local permanece obrigatoria e nao versionada.
- `DATABASE_URL`, quando definido, continua tendo precedencia sobre
  `POSTGRES_*`.

Validacao:

- `docker compose config`: aprovado com senha temporaria de validacao, sem subir
  container.
- `git diff --check`: aprovado.

## Pendencias conhecidas

- Branding Fluxor deve permanecer apenas como mencao historica controlada.
- Referencias AWS devem permanecer apenas como historico de cancelamento.
- Regressao backend completa pendente de PostgreSQL local ativo e migrado.
- Mercado Pago real ainda nao esta ativo.
- Marketplaces reais ainda nao estao ativos.
- BI, IA e Gestao Facil sao frentes futuras/internas.
- Fiscal completo/homologado depende de validacao normativa e tecnica adicional.
- Alguns guias antigos ainda misturam arquitetura-alvo, historico e estado real.
