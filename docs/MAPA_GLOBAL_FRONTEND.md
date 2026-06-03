# MAPA GLOBAL DO FRONTEND

Status: documento oficial do frontend para a fase local do Kovir ERP 1.0.0.

Este mapa foi consolidado a partir de `frontend/src`, `frontend/package.json`,
`frontend/vite.config.ts`, configuracoes publicas, assets e documentos de UI
ainda aderentes ao codigo atual. O frontend e camada de interface: ele orienta a
operacao, mas nao e fonte de verdade para regra financeira, fiscal, estoque,
autorizacao, auditoria ou tenant scope.

## 1. Escopo atual

- Produto: Kovir ERP.
- Execucao atual: desenvolvimento local.
- Deploy AWS: cancelado por enquanto; referencias antigas a deploy remoto devem ser lidas como historicas.
- App principal: SPA React com Vite.
- Roteamento: estado interno por `AppView`, sem React Router.
- Autenticacao visual: `SecurityPage` quando nao ha sessao valida.
- Autorizacao visual: `allowedViews`, roles e permissoes vindas do backend.
- Autorizacao real: sempre no backend.
- Empresa ativa: travada pela empresa da sessao Bearer quando existe sessao.
- API local: `/api`, com proxy Vite para `http://127.0.0.1:8000`.

## 2. Stack real

| Area | Tecnologia |
|---|---|
| UI | React 19, React DOM 19 |
| Build/dev | Vite 8 |
| Linguagem | TypeScript 6 |
| Estilo | Tailwind CSS 4 via `@tailwindcss/vite` + CSS variables globais |
| Icones | `lucide-react` |
| Exportacao XLSX | helper proprio com `fflate` |
| Qualidade | ESLint 10, typescript-eslint, react-hooks, react-refresh |

Nao implementado no estado atual:

- shadcn/ui;
- React Router;
- TanStack Query;
- React Hook Form;
- Zod;
- PWA/service worker;
- app mobile/Capacitor/React Native;
- layout dedicado de maquininha;
- testes automatizados do frontend.

## 3. Estrutura real

```text
frontend/
  index.html
  package.json
  vite.config.ts
  public/
    _headers
    _redirects
    favicon.svg
    kovir-logo.png
    kovir-pulse-logo.png
    kovir-tasks-logo.png
    stvn-software-logo.png
  src/
    App.tsx
    main.tsx
    index.css
    components/
    config/
    data/
    features/
    layouts/
    lib/
    pages/
    routes/
```

Padrao predominante por feature:

```text
<Feature>Page.tsx
<feature>Api.ts
types.ts
```

Excecoes reais:

- `biAnalytics` possui paineis auxiliares (`BiInsightsPanel`, `CashFlowForecastPanel`).
- `orders` possui `ReopenOrderModal`.
- `demo` possui `DemoProductPanel`, mas nao e view principal montada.
- `ai` e `easyManagement` sao paginas sem API propria.
- `sales` exporta `ProductSalesPage`, `ServiceSalesPage` e `SalesPage`, mas so `productSales` esta no lazy registry.

## 4. Entrada, rotas e navegacao

| Arquivo | Responsabilidade |
|---|---|
| `src/main.tsx` | Monta React em `#root` com `StrictMode`. |
| `src/App.tsx` | Decide rotas publicas por `window.location.pathname` e app autenticado. |
| `src/pages/DashboardPage.tsx` | View principal autenticada, cards de modulos e renderizacao lazy. |
| `src/layouts/AppShell.tsx` | Shell autenticado, sidebar, topo, tema e area de conteudo. |
| `src/layouts/Sidebar.tsx` | Navegacao lateral agrupada por dominio, logout e preload por hover/focus. |
| `src/routes/lazyViews.ts` | Lazy loading com `preload()` por `AppView`. |

Rotas publicas por path:

| Path/host | Pagina |
|---|---|
| `/sobre` ou `/erpkovir` | `KovirAboutPage` |
| `/onboarding` | `OnboardingPage` |
| host `stvnsoftware.com.br` ou path `/stvn`, `/stvnsoftware` | `StvnSoftwarePage` |
| demais paths | app autenticado ou `SecurityPage` |

Enquanto nao houver dominio remoto ativo do ERP, CTAs de acesso da pagina
publica apontam para `/`, usando o app local/autenticado atual.

Fluxo autenticado:

```text
App.tsx
-> checkAuth()
-> se sem sessao/token valido: SecurityPage
-> se autenticado: DashboardPage
-> AppShell + Sidebar
-> activeView em estado local
-> LazyViewRenderer carrega feature por AppView
```

## 5. Sessao, empresa ativa e controle visual

### 5.1 Sessao

Arquivo: `src/config/authSession.ts`.

- Armazena sessao em `sessionStorage` sob `kovir_auth_session_v1`.
- Migra storage legado quando encontrado.
- Remove sessao expirada no cliente.
- Dispara evento `kovir:auth-session-changed`.
- Guarda `accessToken`, `expiresAt`, `companyId`, usuario, roles, permissoes e `allowedViews`.

Regra: storage no navegador nao e seguranca. O frontend usa a sessao para UX; backend valida token, sessao, permissoes e tenant.

### 5.2 Empresa ativa

Arquivos:

- `src/config/activeCompany.ts`
- `src/config/useActiveCompany.ts`

Estado atual:

- Quando ha sessao, `companyId` vem de `AuthSession.companyId`.
- `VITE_ACTIVE_COMPANY_ID` e `localStorage` sao fallback local/demo quando nao ha sessao.
- `useActiveCompany()` carrega a empresa da sessao via `getCompany(sessionCompanyId)`.
- `AppShell` remonta conteudo por `companyId`, reduzindo dados presos de empresa anterior.
- `ActiveCompanySwitcher` existe, mas o `AppShell` atual nao monta seletor; ele exibe apenas o nome da empresa ativa.

Regra: nenhuma tela deve depender de empresa fixa/fantasma. Em operacao autenticada, a empresa efetiva vem da sessao e do backend.

### 5.3 Controle visual de acesso

Arquivo: `src/config/accessControl.ts`.

`canAccessView()` verifica:

- view habilitada em `moduleScope`;
- sessao presente;
- role `admin`;
- `allowedViews`;
- permissao `view.<view>`;
- regras especificas para financeiro, relatorios e seguranca.

Regra: `canAccessView()` so esconde/mostra UI. Toda rota sensivel ainda precisa de autorizacao backend.

## 6. Views v1.0 e internas

### 6.1 Views v1.0 habilitadas

Definidas em `src/config/moduleScope.ts`:

```text
overview
company
participants
catalog
fiscalClassification
imports
orders
stock
financial
accountsReceivable
cash
reconciliation
cashFlow
purchasesPayables
managementReports
security
```

### 6.2 Views internas

So habilitam quando `VITE_ENABLE_INTERNAL_MODULES=true`:

```text
biAnalytics
easyManagement
ai
productSales
marketplaces
mercadoPago
technicalRegression
stressTests
```

Em build de producao, `VITE_ENABLE_INTERNAL_MODULES=true` e bloqueado pelo `vite.config.ts`.

## 7. Contrato de API

Arquivo central: `src/lib/api.ts`.

Contrato esperado do backend:

```ts
type ApiResponse<T> = {
  success: boolean
  message: string
  data: T
}
```

Regras do client:

- `API_BASE_URL` vem de `VITE_API_BASE_URL` ou `/api`.
- `buildApiUrl()` normaliza base e path.
- `apiRequest<T>()` usa `fetch`.
- Envia `Content-Type: application/json`.
- Adiciona `Authorization: Bearer <token>` se houver token.
- Adiciona `x-request-id` e `x-correlation-id` com `crypto.randomUUID()`.
- Para erro HTTP, tenta preservar `message`, `detail` string ou erros Pydantic 422.
- `apiDownloadBlob()` baixa PDFs/arquivos com Bearer token.

Regra: novas chamadas devem passar por `lib/api.ts` ou wrapper equivalente do dominio. Nao duplicar `fetch` cru em telas.

## 8. Inventario de features

| Feature | View/pagina | API | Papel |
|---|---|---|---|
| `company` | `CompanyPage` | `companyApi.ts` | Empresa, configuracao e auditoria. |
| `participants` | `ParticipantsPage` | `participantsApi.ts` | Clientes, fornecedores e terceiros. |
| `catalog` | `CatalogPage` | `catalogApi.ts` | Produtos/servicos, filtros e auditoria. |
| `fiscalClassification` | `FiscalClassificationPage` | `fiscalClassificationApi.ts` | Perfis e classificacoes fiscais. |
| `imports` | `ImportsPage` | `importsApi.ts` | Templates, preview e commit de importacao. |
| `orders` | `OrdersPage` | `ordersApi.ts` | Pedidos sobre backend `/sales`, PDFs, fechamento/cancelamento/reabertura. |
| `sales` | `ProductSalesPage`/`SalesPage` | `salesApi.ts` | Frente de venda/produto, readiness e documentos fiscais. |
| `stock` | `StockPage` | `stockApi.ts` | Locais, saldos, lotes, movimentos e entradas. |
| `financial` | `FinancialMasterDataPage` | `financialApi.ts` | Plano financeiro base e fechamento. |
| `accountsReceivable` | `AccountsReceivablePage` | `accountsReceivableApi.ts` | Titulos a receber. |
| `cash` | `CashPage` | `cashApi.ts` | Baixas, movimentos, saldos e estornos. |
| `reconciliation` | `ReconciliationPage` | `reconciliationApi.ts` | Extratos, OFX, sugestoes, matches e reversoes. |
| `cashFlow` | `CashFlowPage` | `cashFlowApi.ts` | Visao prevista/realizada/agregada. |
| `purchasesPayables` | `PurchasesPayablesPage` | `purchasesPayablesApi.ts` | Compras, contas a pagar, filtros, exportacao e pagamento. |
| `managementReports` | `ManagementReportsPage` | `managementReportsApi.ts` | Relatorios gerenciais e fechamento. |
| `security` | `SecurityPage` | `securityApi.ts` | Login, usuarios, permissoes, alcadas e senha mestre. |
| `marketplaces` | `MarketplacesPage` | `marketplacesApi.ts` | Fundacao interna para marketplaces. |
| `mercadoPago` | `MercadoPagoPage` | `mercadoPagoApi.ts` | Fundacao interna para Mercado Pago. |
| `biAnalytics` | `BiAnalyticsPage` | `biApi.ts` | BI/KPIs e exports analiticos internos. |
| `technicalRegression` | `TechnicalRegressionPage` | `technicalRegressionApi.ts` | Diagnosticos tecnicos internos. |
| `stressTests` | `StressTestsPage` | `stressTestsApi.ts` | Massa/stress interno. |
| `ai` | `AiPage` | sem API propria | Placeholder interno. |
| `easyManagement` | `EasyManagementPage` | sem API propria | Placeholder interno. |
| `demo` | `DemoProductPanel` | `demoApi.ts` | Painel/ferramenta demo, nao montado como view principal atual. |

## 9. Design system real

Arquivo principal: `src/index.css`.

Tokens centrais:

| Token | Uso |
|---|---|
| `--color-bg`, `--color-bg-soft` | fundo global |
| `--color-surface`, `--color-surface-elevated` | paineis e cards |
| `--color-border`, `--color-border-soft` | bordas |
| `--color-primary`, `--color-primary-soft`, `--color-primary-border` | acao primaria e foco |
| `--color-text`, `--color-text-muted`, `--color-text-weak` | hierarquia de texto |
| `--color-success`, `--color-warning`, `--color-danger`, `--color-info` | estados |

Temas:

- Default/escuro: fundo escuro, superficies verde-petroleo, primaria emerald `#10b981`.
- Claro: fundo verde em gradiente, superficies brancas, texto escuro, primaria `#16a34a`.
- Sidebar permanece escura.
- `ThemeToggle` grava `kovir-theme` e migra chave legada.

Padroes visuais:

- Usar tokens CSS em vez de cores hardcoded sempre que a tela fizer parte do app autenticado.
- Usar `lucide-react` para icones.
- Manter grupos de navegacao por dominio com acentos diferentes.
- Cards e paineis usam superficies, bordas suaves, sombras controladas e estados hover.
- Form fields usam classes globais como `input-like`, `field-input` ou padrao equivalente por token.
- Tabelas devem ter overflow horizontal controlado, cabecalho claro e empty state.

Observacao: paginas publicas de marketing/onboarding usam paleta propria com assets Kovir/STVN e CTAs externos.

## 10. Componentes compartilhados

| Componente | Papel |
|---|---|
| `ActiveCompanySwitcher` | Seletor de empresa com agrupamento demo/operacional; existe, mas nao esta montado no shell atual. |
| `ModuleCard` | Card reutilizavel de modulo. |
| `SearchableSelect` | Select com busca para formularios operacionais. |
| `StatusBadge` | Badge de status. |
| `StatusItem` | Item visual de status/resumo. |
| `ThemeToggle` | Alternancia dark/light. |

Regra: antes de criar componente local novo, procurar componente compartilhado existente. Criar componente global apenas quando houver reutilizacao real.

## 11. Exportacoes

Arquivos:

- `src/lib/exportTable.ts`
- `src/lib/exportStandard.ts`

Recursos:

- CSV com BOM UTF-8 e separador `;`.
- XLSX gerado no browser via XML + ZIP.
- Celulas tipadas: data, datetime, dinheiro, numero e inteiro.
- Datas formatadas em `dd/mm/yyyy`.
- Valores monetarios preservados como numero em XLSX.
- Nome de arquivo padronizado com data.

Regra: exports devem respeitar filtros aplicados na tela e tenant retornado pelo backend. Para volumes altos, preferir endpoint backend/export ou job futuro.

## 12. Regras de UX operacional

- Loading, erro, vazio e sucesso precisam ser explicitos.
- Mensagens de bloqueio do backend devem ser exibidas sem esconder causa operacional.
- Botao desabilitado e apenas UX; backend continua validando.
- Campos monetarios podem formatar/prevalidar, mas backend recalcula/regra final.
- Busca remota deve usar debounce quando chamar endpoint a cada digitacao.
- Listagens grandes devem usar filtros server-side, `limit` e `offset`.
- Dashboard/card nao deve ser fonte de total oficial se o backend nao retornou agregado.
- Nao misturar conceitos na UI: venda, recebimento, baixa, conciliacao, documento fiscal e estoque sao etapas diferentes.

## 13. Seguranca frontend

Obrigatorio:

- Nao colocar secrets em `VITE_*`.
- Nao expor token Focus NFe, banco, chaves privadas, tokens externos ou `DATABASE_URL`.
- Nao usar `dangerouslySetInnerHTML` sem necessidade extrema e sanitizacao formal.
- Nao registrar token/payload sensivel em `console`.
- Tratar `localStorage` e `sessionStorage` como conveniencia de UX, nao seguranca.
- Esconder view por permissao apenas melhora UX; backend valida tudo.
- Nao aceitar `company_id` do usuario como verdade; backend valida sessao e tenant.
- Nao criar regra critica de permissao, alcada, status ou dinheiro somente no frontend.

Protecoes atuais:

- `vite.config.ts` bloqueia variaveis publicas com nomes/valores sensiveis em build de producao.
- `vite.config.ts` bloqueia API absoluta insegura em producao.
- `vite.config.ts` bloqueia `VITE_ENABLE_INTERNAL_MODULES=true` em producao.
- `vite.config.ts` bloqueia `VITE_ACTIVE_COMPANY_ID` preenchido em producao.
- `public/_headers` define headers de seguranca para hosting estatico compativel.
- `public/_redirects` redireciona SPA para `/index.html`.

## 14. Performance frontend

- Features sao carregadas por `lazyWithPreload`.
- Sidebar e cards chamam preload no hover/focus/navegacao.
- Views internas nao devem ser preloadadas quando desabilitadas.
- Evitar carregar todos os dominios na primeira tela.
- Evitar filtro pesado somente no cliente quando dado cresce.
- Evitar renderizar listas enormes sem paginacao.
- Exportacoes locais devem ser usadas para recortes filtrados, nao datasets ilimitados.
- Formularios com busca remota devem limitar resultados e evitar chamadas duplicadas.

## 15. Validacao local

Comandos padrao:

```powershell
cd frontend
npm install
npm run lint
npm run build
npm run dev
```

Backend local esperado:

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

URLs locais:

```text
Frontend dev: http://localhost:5173
Backend API:  http://127.0.0.1:8000
Proxy API:    http://localhost:5173/api -> http://127.0.0.1:8000
```

Smoke manual minimo:

1. Login em `/auth/login` via `SecurityPage`.
2. Confirmar empresa da sessao no topo.
3. Abrir `Empresa`, `Participantes`, `Produtos`, `Pedidos`, `Estoque`.
4. Abrir `Financeiro`, `Contas a Receber`, `Caixa`, `Fluxo`, `Conciliacao`, `Compras/Pagar`.
5. Abrir `Relatorios Gerenciais`, `Importacoes`, `Seguranca`.
6. Confirmar que modulos sem permissao nao aparecem.
7. Confirmar que erros do backend aparecem como mensagem operacional.

## 16. Gaps e riscos atuais

| Risco | Impacto | Acao recomendada |
|---|---|---|
| `ActiveCompanySwitcher` existe, mas nao esta montado no `AppShell`. | Documentos antigos podem sugerir troca global de empresa que a UI atual nao oferece. | Manter empresa pela sessao ou reativar seletor com contrato backend claro. |
| `activeSession.ts` ainda fornece usuario demo para parte da tela de vendas. | Pode confundir usuario visual/demo com actor real. | Nao usar para autorizacao/auditoria; substituir por `AuthSession` se aparecer para usuario real. |
| Views internas existem no registry/sidebar. | Risco de expor UI interna em ambiente errado. | Manter `VITE_ENABLE_INTERNAL_MODULES=false`; build de producao ja bloqueia true. |
| Paginas publicas possuem links externos/URLs de produto. | Podem ficar desatualizadas em fase local. | Revisar antes de qualquer publicacao real. |
| Nao ha testes automatizados frontend. | Regressao visual/fluxo depende de lint/build e smoke manual. | Criar testes quando fluxos estabilizarem. |
| Algumas telas ainda possuem helpers locais repetidos de dinheiro/data/export. | Risco de comportamento inconsistente. | Consolidar apenas quando houver duplicacao real e baixo risco. |
| Comentarios/classes antigas permanecem no CSS. | Confusao de historico, embora classes efetivas ja sejam Kovir. | Limpar em refactor visual controlado. |

## 17. Checklist para evoluir frontend

- Consultar `docs/MAPA_GLOBAL_BACKEND.md` antes de criar chamada ou fluxo novo.
- Criar API wrapper em `features/<dominio>/<dominio>Api.ts`.
- Tipar entrada/saida em `types.ts`; evitar `any`.
- Usar `apiRequest` e preservar mensagens do backend.
- Respeitar `AppView`, `moduleScope` e `accessControl`.
- Nunca usar permissao visual como unica barreira.
- Usar `useActiveCompany`/sessao, sem `company_id` hardcoded.
- Paginar e filtrar no backend para dados que crescem.
- Exibir loading/error/empty/success.
- Usar tokens de `index.css`, componentes compartilhados e `lucide-react`.
- Rodar `npm run lint` e `npm run build` antes de considerar a tela pronta.
