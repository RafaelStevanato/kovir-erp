# REGRAS DE NEGOCIO

Status: documento oficial de regras de negocio para a fase local do Kovir ERP 1.0.0.

Este documento consolida as regras vigentes a partir dos modulos reais do backend,
frontend, banco de dados, testes de regressao e documentos historicos ainda
aderentes ao codigo atual. O desenvolvimento continua local. O deploy AWS foi
cancelado por enquanto; qualquer documento antigo que trate AWS como ambiente
ativo deve ser lido como historico.

## 1. Hierarquia de fonte de verdade

Em caso de conflito entre fontes:

1. Codigo backend, migrations Alembic e testes de regressao.
2. `docs/MAPA_GLOBAL_BANCO_DE_DADOS.md`.
3. `docs/MAPA_GLOBAL_BACKEND.md`.
4. Este documento.
5. `docs/MAPA_GLOBAL_FRONTEND.md`.

Regras criticas nunca podem depender apenas de frontend, planilha, documento
antigo ou estado visual da interface.

## 2. Principios transversais

- O backend e a fonte oficial de regra financeira, fiscal, estoque, seguranca,
  auditoria, status e isolamento multiempresa.
- Toda entidade operacional pertence a uma empresa (`company_id`) quando fizer
  parte do dominio de negocio.
- A sessao Bearer define a empresa ativa e as permissoes do usuario.
- Queries de dominio devem filtrar por `company_id`; o middleware global reduz
  risco, mas nao substitui filtro em service/repository.
- IDs enviados pelo cliente devem ser validados por prefixo e ownership.
- Dinheiro usa `Decimal` e arredondamento a 2 casas. Nao usar `float`.
- Quantidades de estoque usam 4 casas decimais.
- Operacoes que alteram mais de uma tabela devem ser transacionais.
- Fatos financeiros, fiscais, estoque, conciliacao e auditoria nao devem ser
  apagados como fluxo normal. Corrigir por status, cancelamento, estorno ou
  registro reverso.
- Listagens devem ter `limit`, `offset`, filtros e ordenacao previsivel.
- Cadastros podem ter `deleted_at`; fatos operacionais preservam trilha.
- Snapshots devem preservar o contexto de venda, compra, participante,
  item, fiscal, pagamento e origem externa no momento do fato.
- Regras futuras nao implementadas nao podem ser tratadas como comportamento
  disponivel ao usuario.

## 3. Seguranca, usuarios e permissoes

### 3.1 Autenticacao

- Login gera sessao Bearer persistida em banco por hash de token.
- Sessao padrao expira em 30 minutos.
- Logout revoga a sessao.
- Login possui rate limit em memoria por IP, empresa e email.
- Bootstrap admin so e permitido quando `BOOTSTRAP_ADMIN_ENABLED=true`, token
  de bootstrap valido, token com pelo menos 32 caracteres e banco sem usuarios.

### 3.2 Autorizacao

- Permissoes nunca podem vir do navegador como fonte de verdade.
- Rotas protegidas usam `get_current_principal` ou `require_permission_dependency`.
- Views do frontend (`view.<aba>`) controlam exposicao visual, nao autorizacao
  final de recurso.
- Toda acao sensivel deve validar permissao, empresa ativa e ownership do
  recurso.

Permissoes criticas:

| Acao | Permissao |
|---|---|
| Gerenciar usuarios, papeis e catalogo de seguranca | `users.manage` |
| Alterar empresa | `company.write` |
| Ver empresa | `view.company` |
| Gravar cadastros financeiros | `finance.write` |
| Ler financeiro | `finance.read` |
| Pagar titulo a pagar | `payables.pay` |
| Ler alcadas | `approval.read` |
| Decidir alcadas | `approval.decide` |
| Ler relatorios | `reports.read` |
| Criar/alterar participantes | `participants.write` |
| Criar/alterar catalogo | `catalog.write` |
| Criar/alterar fiscal | `fiscal.write` |
| Emitir/sincronizar/cancelar fiscal | `fiscal.issue` |
| Movimentar estoque | `stock.move` |
| Registrar entrada de compra no estoque | `stock.purchase_entry` |
| Ver pedidos | `sales.view` |
| Criar/editar pedido em orcamento | `sales.create` |
| Fechar pedido | `sales.close` |
| Cancelar pedido | `sales.cancel` |
| Endpoint legado de receber pedido | `sales.pay` |
| Configurar/reabrir com senha mestre | `sales.unlock_closed` |
| Registrar baixa de recebivel | `cash.receive` |
| Estornar baixa/movimento manual | `cash.reverse` |
| Executar importacoes | `imports.run` |
| Executar diagnosticos internos | `technical.run` |

### 3.3 Roles padrao

| Role | Escopo |
|---|---|
| `admin` | Todas as permissoes. |
| `finance_manager` | Financeiro, pagamentos, alcadas e relatorios. |
| `finance_operator` | Operacao financeira com pagamentos e leitura de alcadas. |
| `viewer` | Leitura minima. |

## 4. Tenant scope e ownership

- Usuario pode pertencer a mais de uma empresa, mas a sessao ativa aponta para
  uma empresa por vez.
- Request que mistura empresa da sessao com `company_id` ou recurso de outra
  empresa deve ser bloqueado.
- Recursos identificados por prefixo tecnico devem ter ownership resolvido no
  banco quando usados em path/body/query.
- Nao confiar em `company_id` vindo do frontend para liberar acesso.
- Integracoes externas e importacoes tambem precisam respeitar empresa ativa.

## 5. Auditoria e rastreabilidade

- Alteracoes relevantes devem gerar `audit_events` ou `security_audit_events`.
- Eventos devem registrar ator real (`actor_id`/`user_id`), empresa, entidade,
  request/correlation quando disponiveis e antes/depois quando aplicavel.
- Logs e auditoria nao devem armazenar senha, token, chave de API, secret,
  string de conexao ou payload sensivel integral.
- Status historicos devem ficar nas tabelas especificas: vendas, compras e
  titulos financeiros possuem historico proprio.

## 6. Periodos financeiros fechados

- `financial_period_closures` bloqueia operacoes financeiras dentro do intervalo
  fechado.
- Fechamentos ativos nao podem ter sobreposicao para a mesma empresa.
- Criacao, cancelamento, pagamento, baixa, estorno, conciliacao e geracao de
  titulo devem consultar `assert_period_open` quando houver data financeira.
- Desativar fechamento muda status para `inactive`; nao remove historico.

## 7. Empresa

- Empresa e a raiz do tenant.
- CNPJ, quando informado, deve ter 14 digitos e ser unico.
- Razao social e obrigatoria.
- Configuracoes fiscais, financeiras e operacionais pertencem a empresa.
- Moeda deve usar codigo ISO de 3 letras, padrao `BRL`.
- Serie fiscal aceita apenas numeros.
- `uses_imports`/`allow_imports` controla se importacoes podem ser executadas.
- Empresa inativa/bloqueada nao deve ser usada como contexto operacional novo.

## 8. Participantes

- Participante pode ser cliente, fornecedor, transportador, prestador, marketplace,
  gateway, banco ou outro.
- Documento e unico por empresa quando informado.
- Nome/razao social e obrigatorio.
- Documento deve ser normalizado e validado; telefone deve ter tamanho minimo.
- Endereco fiscal relevante deve ter UF, cidade e codigo IBGE quando necessario
  para emissao fiscal.
- Venda exige participante do tipo `customer` ativo.
- Compra/despesa exige participante ativo ou em rascunho, conforme fluxo atual.
- Participante bloqueado/inativo nao deve ser usado em nova operacao critica.

Status:

```text
draft | active | inactive | blocked
```

## 9. Catalogo de produtos e servicos

- Catalogo separa `product` e `service`.
- SKU e codigo de barras sao unicos por empresa quando informados.
- Produto fiscalmente classificado deve usar NCM de 8 digitos.
- Servico fiscalmente classificado deve usar NBS de 9 digitos.
- Produto nao deve usar NBS; servico nao deve usar NCM.
- Servico nao pode controlar estoque.
- Item com controle de estoque deve informar unidade de estoque.
- Itens inativos/bloqueados nao podem ser vendidos ou movimentados.
- Quando produto informa NCM, o backend tenta sincronizar classificacao fiscal
  vigente da empresa.
- Preco padrao de venda do catalogo e usado como referencia de venda; override
  manual deve continuar controlado pelo backend.

Status:

```text
draft | active | inactive | blocked
```

## 10. Fiscal, classificacao e documentos

### 10.1 Classificacao fiscal

- Perfil e classificacao fiscal pertencem a empresa.
- Nome de perfil deve ser unico por empresa quando aplicavel.
- `valid_to` nao pode ser anterior a `valid_from`.
- NCM, NBS, CFOP, CST e cClassTrib sao strings, nao numeros.
- Produto deve ter NCM quando a classificacao for de produto.
- Servico deve ter NBS quando a classificacao for de servico.
- Classificacao ativa e vigente deve ser usada para operacoes reais.
- Regras fiscais por item+natureza definem a classificacao usada no item da venda.
- Toda regra fiscal deve preservar vigencia, fonte e rastro de alteracao.

Status:

```text
draft | active | inactive | blocked | expired
```

### 10.2 Prontidao fiscal da venda

- Readiness fiscal e somente leitura: nao emite nota e nao calcula tributo.
- Venda so pode ser emitida fiscalmente quando nao houver bloqueio de empresa,
  cliente, item ou classificacao.
- Empresa precisa de razao social, CNPJ, regime tributario, ambiente fiscal, UF,
  municipio e codigo IBGE quando NF-e for exigida.
- Cliente precisa de nome, tipo de pessoa, documento quando aplicavel, endereco
  fiscal e status ativo.
- Item precisa estar ativo, vinculado a classificacao fiscal existente, ativa e
  vigente.
- Produto fiscal deve ter NCM; servico fiscal deve ter NBS; regras tributarias
  obrigatorias dependem de ICMS/ISS/PIS/COFINS/IBS/CBS/IS marcados.

### 10.3 Documento fiscal

- Documento fiscal nao e venda, nao e titulo financeiro, nao e baixa e nao e
  movimento de estoque.
- Documento fiscal com impacto financeiro deve ter vinculo com venda/titulo
  quando o fluxo estiver implementado.
- Integracao Focus NFe atual e parcial: monta payload a partir da venda e persiste
  `fiscal_documents`.
- A service de documentos fiscais nao decide regra tributaria; apenas mapeia
  dados validados pela readiness layer.
- Emissao cria documento pendente, chama provedor e atualiza status conforme
  retorno.
- Cancelamento fiscal e separado de cancelamento de venda e precisa de permissao
  `fiscal.issue`.

Status internos principais:

```text
pending | processing | issued | authorized | cancelled | error
```

## 11. Vendas e pedidos

### 11.1 Ciclo de status

```text
quote -> closed -> cancelled
closed -> quote  (somente reabertura com senha mestre)
closed -> fiscal/documentos/recebiveis conforme fluxo
paid   (legado, nao usado para novo recebimento direto)
```

Status:

```text
quote | closed | paid | cancelled
```

### 11.2 Criacao e edicao

- Venda fora de PDV exige participante.
- Participante deve ser cliente ativo e da mesma empresa.
- Itens devem existir, estar ativos e pertencer a empresa.
- Operacao deve ter natureza valida.
- Naturezas `bonus`, `sample`, `exchange`, `courtesy`, `replacement` e `other`
  exigem motivo.
- Venda normal limpa motivo de natureza.
- Desconto pode ser valor ou percentual.
- Qualquer desconto exige categoria e motivo.
- Percentual de desconto deve ser maior que zero e menor ou igual a 100.
- Soma dos planos de pagamento deve bater com total a receber.
- Venda separa valor comercial, valor a receber e valor previsto para documento
  fiscal.

### 11.3 Naturezas comerciais

| Natureza | Receita | Contas a receber | Estoque | Fiscal | Motivo |
|---|---:|---:|---:|---:|---:|
| `normal_sale` | Sim | Sim | Sim | Sim | Nao |
| `bonus` | Nao | Nao | Sim | Sim | Sim |
| `sample` | Nao | Nao | Sim | Sim | Sim |
| `exchange` | Nao | Nao | Sim | Sim | Sim |
| `courtesy` | Nao | Nao | Sim | Sim | Sim |
| `replacement` | Nao | Nao | Sim | Sim | Sim |
| `other` | Sim | Sim | Sim | Sim | Sim |

### 11.4 Fechamento

- Fechar pedido exige status `quote`.
- Fechamento usa lock na venda.
- Fechamento gera numero sequencial por empresa (`PED-XXXXXX`).
- Fechamento aplica efeitos de estoque dentro da mesma transacao.
- Fechamento gera titulos a receber quando existe valor financeiro a receber.
- Venda com valor a receber precisa ter plano de pagamento.
- Geracao de recebiveis e idempotente por `company_id + source_type + source_id`.
- Fechamento registra historico e auditoria.

### 11.5 Recebimento

- Pedido fechado nao e recebimento.
- `POST /sales/{id}/pay` existe apenas por compatibilidade e retorna erro
  controlado na v1.0.
- Baixa financeira oficial deve ocorrer em Caixa e Baixas.

### 11.6 Cancelamento

- Venda cancelada nao pode ser cancelada novamente.
- Motivo de cancelamento e obrigatorio.
- Cancelar venda fechada/paga exige que recebiveis vinculados possam ser
  cancelados.
- Venda com baixa ativa, movimento ativo ou valor recebido nao pode ser cancelada
  antes de estornar/regularizar o financeiro.
- Cancelamento de venda fechada reverte efeitos de estoque e cancela recebiveis
  vinculados quando permitido.
- Cancelamento gera historico e auditoria.

### 11.7 Reabertura

- Somente pedido `closed` pode ser reaberto.
- Reabertura exige permissao `sales.unlock_closed` e senha mestre valida.
- Senha mestre e hash bcrypt por empresa; senha em claro nunca deve ser persistida.
- Tentativa invalida gera evento de seguranca.
- Reabertura reverte estoque, cancela recebiveis vinculados e volta status para
  `quote`.
- Reabertura gera auditoria operacional e de seguranca.

## 12. Estoque

- Estoque real e movimento; saldo e lote sao materializacoes derivadas.
- `stock_movements` e a trilha auditavel.
- `stock_balances` e `stock_lots` devem ser atualizados na mesma transacao do
  movimento.
- Alteracao de saldo usa lock (`FOR UPDATE`) para evitar race condition.
- Produto sem `track_stock` nao movimenta estoque em venda.
- Servico nunca movimenta estoque.
- Produto com `track_stock=true` exige lote em movimentacoes.
- Validade sem vencimento usa sentinela interna.
- Saida que deixaria saldo/lote negativo e bloqueada quando o item nao permite
  estoque negativo.
- Saldo inicial so pode ser registrado uma vez por produto/local e apenas quando
  nao existe saldo/movimento previo.
- Movimento manual aceita apenas saldo inicial, ajuste de entrada e ajuste de
  saida nesta fase.
- Venda fechada gera `sale_out`; cancelamento/reabertura gera
  `sale_out_reversal`.
- Entrada por documento de compra gera entrada, itens, lote, movimento
  `purchase_in` e atualizacao de saldo.
- XML de NF-e de compra apenas sugere dados; nao cria produto automaticamente e
  nao grava estoque sem confirmacao operacional.
- Entrada duplicada por chave de acesso ou fornecedor+documento+serie deve ser
  bloqueada.

Movimentos:

```text
initial_balance | adjustment_in | adjustment_out | sale_out |
sale_out_reversal | purchase_in | transfer_in | transfer_out
```

Status:

```text
posted | reversed | cancelled
```

## 13. Cadastros financeiros base

- Cadastros financeiros mestres vem antes de lancamentos financeiros.
- Conta bancaria/caixa/gateway, categoria, plano de contas, centro de custo e
  condicao de pagamento nao devem ser texto solto.
- Cadastro financeiro inativo, bloqueado ou arquivado nao deve receber novo
  vinculo operacional.
- Conta sintetica nao recebe lancamento direto.
- Centro de custo nao substitui plano de contas.
- Categoria financeira nao substitui classificacao fiscal.
- Forma de pagamento define como; condicao de pagamento define quando.
- Categoria que afeta fluxo de caixa deve ter `cash_flow_group` valido.
- Conta financeira bancaria exige instituicao.
- Chave Pix exige tipo quando informada.
- Uma unica conta financeira default receivable/payable deve prevalecer por
  empresa; marcar uma limpa as demais.
- Saldo inicial de conta financeira nao pode ser alterado depois de saldo
  materializado ou movimentacao.
- Conta financeira em uso nao pode ser inativada, bloqueada ou arquivada.
- Condicao a vista deve ter uma parcela, D+0 e intervalo zero.
- Condicao parcelada deve ter intervalo maior que zero.

Status:

```text
draft | active | inactive | blocked | archived
```

Grupos de fluxo de caixa:

```text
operating_inflows | operating_outflows |
investing_inflows | investing_outflows |
financing_inflows | financing_outflows
```

## 14. Contas a receber

- Conta a receber representa direito financeiro, nao dinheiro realizado.
- Titulo a receber nao e movimento de caixa.
- Titulo a receber nao e conciliacao bancaria.
- Documento fiscal nao e titulo financeiro.
- Baixa de titulo ocorre em Caixa e Baixas.
- Titulo guarda vinculo e snapshot da origem e do participante.
- Titulo manual exige participante ativo e valor bruto maior que zero.
- Valor liquido nao pode ficar negativo.
- Centro de custo deve ser analitico e ativo quando informado.
- Categoria, conta financeira prevista e forma de pagamento devem pertencer a
  empresa e estar ativos quando informados.
- Status inicial depende de vencimento e saldo aberto: `open`, `overdue` ou
  `received`.
- Titulo encerrado (`cancelled`, `received`, `written_off`) nao pode ser alterado.
- Cancelamento de titulo com valor recebido, baixa ativa ou movimento ativo e
  bloqueado.
- Cancelar recebivel de venda exige periodo aberto na data atual e na data de
  referencia do titulo.

Status:

```text
draft | open | overdue | partially_received | received |
cancelled | written_off | renegotiated
```

Status de cobranca:

```text
not_started | scheduled | reminder_sent | in_collection |
promised | disputed | paused | closed
```

Status fiscal:

```text
pending_document | linked | not_required | divergent
```

Fluxo:

```text
sales -> sale_payment_plans -> financial_titles(receivable)
-> settlements -> financial_movements -> reconciliation_matches
```

## 15. Caixa, baixas e movimentos financeiros

- Venda nao e recebimento.
- Titulo a receber nao e dinheiro no banco.
- Baixa reduz saldo em aberto do titulo.
- Movimento financeiro interno altera saldo interno da conta financeira.
- Conciliacao fica pendente apos movimento.
- Baixa exige periodo aberto na data da baixa e competencia.
- Conta financeira deve estar ativa e pertencer a empresa.
- Forma de pagamento deve estar ativa quando informada.
- Baixa precisa ter valor recebido ou abatimento maior que zero.
- Movimento financeiro da baixa nao pode ficar negativo.
- Baixa nao pode exceder saldo em aberto do titulo.
- `source_type + source_id` evita duplicidade quando informado.
- Baixa cria `settlement`, `financial_movement` e atualiza
  `financial_account_balances` na mesma transacao.
- Estorno de baixa exige motivo.
- Estorno de baixa conciliada/divergente e bloqueado ate estornar o match.
- Estorno cria movimento reverso, marca settlement como `reversed`, ajusta saldo
  e reabre/parcializa o titulo.
- Movimento manual deve ter descricao, valor maior que zero e direcao valida.
- Movimento manual conciliado/divergente nao pode ser estornado antes do match.
- Somente movimento manual sem titulo/baixa vinculada pode ser estornado pela
  rotina de movimento manual.

Settlement:

```text
active | reversed | cancelled
```

Movimento:

```text
posted | reversed | cancelled
```

Direcao:

```text
inflow | outflow
```

## 16. Compras, despesas e contas a pagar

### 16.1 Compra/despesa

- Compra/despesa pertence a empresa e fornecedor/participante.
- Participante precisa estar ativo ou em rascunho para criar compra/despesa.
- Total calculado dos itens precisa ser maior que zero.
- Valor informado no documento deve bater com o total calculado quando informado.
- Criacao em rascunho gera historico e auditoria.
- Apenas compra/despesa `draft` pode ser confirmada.
- Confirmacao exige periodo aberto na data de referencia.
- Confirmacao exige cadastros financeiros validos.
- Soma das parcelas deve bater com `payable_total_amount`.
- Confirmacao gera titulo(s) a pagar em `financial_titles` com
  `direction='payable'`.
- Cada parcela gera snapshot, vinculo financeiro, historico e auditoria.
- Cancelamento de compra com titulos vinculados ativos/vencidos/parciais/pagos e
  bloqueado; primeiro cancelar/estornar os titulos.

Status de compra:

```text
draft | confirmed | cancelled
```

Tipos:

```text
inventory_purchase | expense | service | tax | asset | other
```

### 16.2 Conta a pagar

- Conta a pagar usa `financial_titles` com `direction='payable'`.
- Pagamento exige permissao `payables.pay`.
- Sessao deve pertencer a empresa do pagamento.
- Pagamento exige comprovante, extrato ou justificativa em `evidence_reference`.
- Titulo encerrado (`cancelled`, `paid`, `written_off`) nao aceita novo pagamento.
- Pagamento exige periodo aberto na data do pagamento e competencia.
- Pagamento deve reduzir saldo do titulo.
- Pagamento nao pode exceder saldo em aberto.
- Movimento financeiro de pagamento deve ser maior que zero.
- Pagamento acima da politica de alcada exige solicitacao aprovada.
- Pagamento gera settlement outflow, movement outflow, atualiza saldo e titulo.
- Titulo com pagamento (`paid`, `partially_paid`, `written_off`) nao deve ser
  cancelado sem estorno controlado.

Status de titulo a pagar:

```text
draft | open | overdue | partially_paid | paid | cancelled | written_off
```

Fluxo:

```text
purchases -> purchase_financial_links -> financial_titles(payable)
-> settlements(payment) -> financial_movements(outflow)
-> financial_account_balances -> reconciliation_matches
```

## 17. Alcadas de pagamento

- Alcada atual implementada cobre pagamento de contas a pagar.
- Politica tem `action_key='payables.payment'`, moeda, valor limite, permissao
  requerida e regra de autoaprovacao.
- Consultar politica exige `approval.read`.
- Atualizar politica exige `users.manage`.
- Criar solicitacao de pagamento exige `payables.pay`.
- Decidir solicitacao exige `approval.decide` e permissao requerida na politica.
- Se politica estiver desativada ou valor for menor/igual ao limite, pagamento
  segue sem `approval_request_id`.
- Se valor exceder limite, pagamento exige solicitacao aprovada.
- Solicitacao precisa pertencer a mesma empresa, estar `approved`, apontar para o
  mesmo titulo e ter valor aprovado maior ou igual ao valor do pagamento.
- Autoaprovacao e bloqueada quando `allow_self_approval=false`.
- Toda criacao/decisao gera auditoria de seguranca.

Status de solicitacao:

```text
pending | approved | rejected
```

## 18. Conciliacao bancaria

- Movimento interno nao e extrato bancario.
- Baixa nao e conciliacao.
- Extrato importado e evidencia externa; nao altera saldo interno sozinho.
- Conciliacao e vinculo auditavel entre `bank_statement_lines` e
  `financial_movements`.
- Match nao cria titulo, baixa, movimento ou saldo.
- Linha de extrato deve pertencer a mesma empresa e conta financeira do movimento.
- Linha e movimento devem ter mesma direcao.
- Linha precisa estar `pending` ou `divergent`.
- Movimento precisa estar `posted` e `reconciliation_status` `pending` ou
  `divergent`.
- Nao pode haver match ativo para a mesma linha ou movimento.
- Confirmar match exige periodo aberto na data da linha e do movimento.
- Diferenca acima da tolerancia e bloqueada.
- Conciliacao com diferenca exige justificativa e fica sinalizada como
  divergente.
- Estorno de match exige motivo, reabre linha e movimento para `pending` e
  registra auditoria.
- Linha pendente/divergente pode ser ignorada com motivo.
- OFX e importacao basica de extrato; nao e Open Finance, CNAB ou Pix real.

Status da linha:

```text
pending | matched | divergent | ignored
```

Status do match:

```text
confirmed | confirmed_with_difference | reversed
```

Fluxo:

```text
financial_movements(pending) + bank_statement_lines(pending)
-> reconciliation_matches
-> financial_movements.reconciliation_status matched/divergent
```

## 19. Fluxo de caixa, BI e relatorios

- Fluxo de caixa e visao gerencial derivada; nao e DRE e nao e razao contabil.
- Relatorio nao corrige dado ruim; aponta origem da divergencia.
- Entrada prevista vem de `financial_titles` receivable em aberto por vencimento.
- Saida prevista vem de `financial_titles` payable em aberto por vencimento.
- Realizado vem de `settlements` e `financial_movements` postados.
- Saldo interno vem de `financial_account_balances` e movimentos financeiros.
- Extrato externo e evidencia; nao compoe saldo interno sozinho.
- Conciliacao em relatorio vem de status de movimentos, linhas e matches.
- Pendencia deve ser resolvida no modulo de origem.
- BI agrega fatos existentes; nao cria venda, compra, titulo, baixa, movimento
  ou conciliacao.
- Exports grandes devem respeitar filtros/limites; processamento pesado futuro
  deve migrar para fila/job.

Principais indicadores:

- saldo interno total;
- entradas previstas;
- saidas previstas;
- recebimentos/pagamentos realizados;
- titulos vencidos;
- movimentos pendentes de conciliacao;
- linhas de extrato pendentes;
- divergencias de conciliacao;
- saldo por conta financeira;
- previsao 13 semanas;
- capital de giro, DSO, DPO, CCC, runway e aging quando a base permitir.

## 20. Importacoes

- Importacao atual cobre participantes, produtos e classificacoes fiscais.
- Empresa da importacao e a empresa da sessao, salvo payload valido e autorizado.
- Empresa deve permitir importacoes.
- Preview valida antes de commit.
- Linhas invalidas nao devem ser gravadas.
- Commit deve gravar somente linhas validas e retornar falhas por linha.
- Participante importado nao pode duplicar documento na planilha ou na empresa.
- Produto importado nao aceita `item_type` diferente de `product`.
- Produto importado deve informar NCM.
- NCM do produto precisa existir no fiscal da empresa antes da importacao.
- SKU e barcode nao podem duplicar na planilha nem na empresa.
- Classificacao fiscal de produto exige NCM.
- Classificacao fiscal de servico exige NBS.
- Importacao deve usar source/auditoria `IMPORT`.

## 21. Marketplaces e Mercado Pago

### 21.1 Marketplaces

- Integracao externa nao deve gravar pedido diretamente como venda sem camada
  intermediaria.
- Conta de marketplace/gateway pertence a empresa e possui status proprio.
- Credenciais sensiveis nao devem ser armazenadas em texto puro.
- Pedido externo, pagamento externo, titulo financeiro, baixa e conciliacao sao
  conceitos diferentes.
- Toda sincronizacao futura deve gerar historico em `marketplace_sync_runs`.
- Pedidos externos devem ser idempotentes por provedor e ID externo.

### 21.2 Mercado Pago

- Mercado Pago e gateway/intermediador financeiro, nao marketplace de pedidos
  como canal de venda completo.
- Pagamento aprovado no Mercado Pago nao e conciliacao bancaria automatica.
- Webhook nao e fonte unica de verdade; deve ser idempotente, auditavel e
  reconciliavel com consultas/relatorios.
- Reembolso, chargeback, taxa, repasse e liberacao de dinheiro sao entidades
  separadas.
- `access_token`, `refresh_token` e `client_secret` nao devem ser gravados em
  texto puro.

## 22. Modulos internos e diagnosticos

- `demo`, `stress_tests`, `technical_regression`, `biAnalytics`,
  `easyManagement`, `ai`, `marketplaces` e `mercadoPago` podem existir como
  ferramentas internas/preparatorias.
- Modulos internos nao devem ficar habilitados em producao.
- Resultado de stress/diagnostico nao e regra operacional; serve para validar
  regressao e integridade.
- Rotas tecnicas exigem permissao tecnica ou usuarios administrativos conforme
  modulo.

## 23. Limites atuais da v1.0.0 local

Nao tratar como implementado:

- deploy AWS ativo;
- Open Finance;
- CNAB;
- Pix real;
- conciliacao N:N avancada;
- fechamento bancario mensal completo;
- split payment operacional;
- apuracao fiscal completa IBS/CBS/IS;
- SPED/contador automatizado;
- emissao fiscal homologada de ponta a ponta para todos os cenarios;
- fila/job assincrono para import/export pesado;
- PWA/app mobile;
- testes automatizados frontend.

## 24. Checklist obrigatorio ao evoluir regra de negocio

- Validar regra no backend, nao apenas no frontend.
- Confirmar permissao e ownership por recurso.
- Filtrar por `company_id`.
- Usar Pydantic para entrada/saida.
- Usar transacao quando alterar multiplas tabelas.
- Usar lock ou constraint quando houver risco concorrente.
- Preservar auditoria e historico.
- Nao apagar fato operacional sem trilha.
- Atualizar Alembic quando schema mudar.
- Atualizar os mapas oficiais quando contrato mudar.
- Cobrir regressao com testes de seguranca, fluxo feliz, estados invalidos,
  concorrencia e periodo fechado quando aplicavel.
