# Graph Program Specification — v5.3 (Proto + Startup)

## 0. Ментальная модель

Граф — это программа. Нода — функция с входами, выходами и параметрами. Рёбра соединяют выходы → входы.

6 примитивов. Всё остальное — композиция.

Каждый запуск графа производит два артефакта: **Explain Plan** (что будет) и **Execution Receipt** (что было). Это не опция — это часть рантайма.

Эта спецификация полностью покрывает **Proto** и **Startup** тиры. Midmarket и Enterprise описаны на уровне концепции (§17) и будут специфицированы по реальному фидбэку.

---

## 1. Базовые сущности

### 1.1 Graph

```typescript
{
  id: string
  version: string
  tier: "proto" | "startup"
  inputs: Port[]
  outputs: Port[]
  nodes: Node[]
  edges: Edge[]
  defaults?: GraphDefaults        // дефолты runtime для всех нод (§5)
  metadata?: Meta
  lockfile?: { [templateId: string]: string }
  expires?: string                // proto only: auto-deletion (max 30 дней)
  dlq?: DLQConfig                 // Dead Letter Queue (§8)
}
```

### 1.2 Node

```typescript
{
  id: string
  type: string                    // один из 6 примитивов ИЛИ template id
  label?: string
  params?: object
  runtime?: RuntimeOverrides      // retries, timeout (§5)
  on_error?: OnError              // fallback, compensation (§8)
  metadata?: Meta
  debug?: { break?: boolean, condition?: string }
}
```

Порты приходят из шаблона, не хранятся в инстансе.

### 1.3 Edge

```typescript
{
  from: { node: string, port: string }
  to: { node: string, port: string }
  strategy?: "direct" | "concat" | "zip" | "reduce"
  window?: WindowSpec
  priority?: number
}
```

### 1.4 Template (NodeSpec)

```typescript
{
  id: string                      // e.g. "Math.AddConst"
  version: string
  kind: "Compute" | "Route" | "Iterate" | "State" | "Scope" | "Subgraph"
  inputs: Port[]
  outputs: Port[]
  params?: ParamSchema
  entrypoint?: string             // "module.py:run" для Compute

  // Compute only
  security?: "raw" | "managed" | "safe"
  sandbox?: "wasm" | "pyodide" | "gvisor" | "seccomp"       // safe
  capabilities?: Capabilities                                 // managed

  // Флаги
  pure?: boolean
  stateful?: boolean
  async?: boolean
  idempotent?: boolean

  // Библиотека
  requirements?: string[]
  examples?: Example[]            // proto: optional, startup: recommended
  port_groups?: PortGroup[]
  deprecated_since?: string
  metadata?: Meta
}
```

**Port:**
```typescript
{ name: string, type: TypeName, optional?: boolean, default?: any }
```

Порт обязателен по умолчанию. `optional: true` — порт можно не подключать.

**PortGroup:**
```typescript
{
  name: string
  direction: "in" | "out"
  type: TypeName
  variadic: boolean
  min?: number
  max?: number
  n_param?: string
}
```

**ParamSchema:**
```typescript
{ [name: string]: { type: TypeName, default?: any, description?: string } }
```

**Capabilities (для security: "managed"):**
```typescript
{
  fs?: { read?: string[], write?: string[], temp?: boolean }
  net?: { allow?: string[], deny?: string[] }
  gpu?: { inference?: string[], via?: "rpc" | "direct" }
  secrets?: { allow?: string[] }
}
```

Proto: capabilities игнорируются (но рекомендуется заполнять).
Startup: capabilities обязательны, enforcement — soft (логирование нарушений).

---

## 2. Шесть примитивов

### 2.1 Compute

"Запустить код."

Один примитив, три уровня безопасности через поле `security`. Порядок — от самого свободного к самому строгому, как в реальном lifecycle проекта:

**Общий контракт:**
- `entrypoint: "pkg.module:run"`
- `def run(inputs: dict, params: dict) -> dict`

#### security: "raw"
- Изолированный контейнер, без ограничений
- **Proto:** свободно
- **Startup:** обязательно `params.reason: string` + warning в логах
- Типичный сценарий: быстрый прототип, legacy-код, нестандартные зависимости

#### security: "managed"
- Контейнер с enforcement capabilities
- Linux-first: bind-mounts для FS, egress proxy для NET
- Startup: soft enforcement (логирование) → переключение на hard по готовности
- Типичный сценарий: код с контролируемыми side-effects (API-вызовы, чтение файлов)

#### security: "safe"
- Sandbox: seccomp/gVisor (выбирается платформой по tier)
- Нет FS/NET/GPU, нет subprocess/ctypes/socket
- Hard limits: CPU/memory/time через cgroups
- Import allowlist
- Типичный сценарий: чистые вычисления, трансформации данных, бизнес-логика

**Эскалация безопасности** — закручивание гаек одним полем:
```diff
- security: "raw"
+ security: "managed"
+ capabilities: { net: { allow: ["https://api.example.com/**"] } }
```

Было: «делай что хочешь». Стало: «делай только это». Следующий шаг — `"safe"`, полная песочница.

### 2.2 Route

Условная маршрутизация.

- **Inputs:** `data` (any), optional `ctx`
- **Params:** `rules` — таблица правил (by value/type/regex), `default` branch
- **Outputs:** по одному на route label

Покрывает if/switch/match/regex.

### 2.3 Iterate

Один цикл для всего. В UI показывается через алиасы.

**Алиасы (компилируются в Iterate):**
- `Map(body)` → `Iterate{mode: "map"}`
- `Filter(body)` → `Iterate{mode: "filter"}`
- `Reduce(init, body)` → `Iterate{mode: "reduce"}`
- `For(count, body)` → `Iterate{mode: "for"}`
- `While(cond, body)` → `Iterate{mode: "while"}`

**Params:**
- `mode: "for" | "while" | "map" | "filter" | "reduce"`
- `body` — тело цикла: ссылка на subgraph template **или** inline subgraph

**Inline body** — для простых случаев, когда отдельный template избыточен:

```json
{
  "type": "Map",
  "params": {
    "body": {
      "nodes": [
        { "id": "sq", "type": "Math.Square" }
      ],
      "edges": [
        { "from": { "node": "$input", "port": "item" }, "to": { "node": "sq", "port": "x" } },
        { "from": { "node": "sq", "port": "result" }, "to": { "node": "$output", "port": "item" } }
      ]
    }
  }
}
```

Ссылка по template ID — для сложных или переиспользуемых тел:
```json
{ "type": "Map", "params": { "body": "normalize-row-subgraph" } }
```

**Ports:**
- Inputs: `data`, optional `state_in`
- Outputs: `result`, optional `state_out`

### 2.4 State

Явное управление состоянием.

**Params:**
```typescript
{
  backend: "memory" | "redis"
  op: "get" | "set" | "delete"
  key?: string
  ttl?: number              // секунды
}
```

**Ports:**
- Inputs: `key?`, `value?`
- Outputs: `value`, `ok`

**Атомарные операции над несколькими ключами:** используйте `Scope(atomic: true)` с несколькими State-нодами внутри (§2.5). Scope обеспечивает атомарность — State остаётся простым.

**Почему нет `file` backend:** файловый backend создаёт ложное чувство персистентности без гарантий. Для proto хватает memory, для startup — redis.

### 2.5 Scope

Обёртка ресурсов/транзакций.

**Params:**
- `atomic?: boolean`
- `resources?: string[]` — e.g. `["db", "session", "gpu"]`

Тело — subgraph. Открывает ресурсы на входе, закрывает на выходе (включая ошибки).

**Пример: атомарный апдейт двух ключей:**
```json
{
  "id": "atomic_update",
  "type": "Scope",
  "params": { "atomic": true },
  "body": {
    "nodes": [
      { "id": "set_balance", "type": "State", "params": { "op": "set", "backend": "redis" } },
      { "id": "set_timestamp", "type": "State", "params": { "op": "set", "backend": "redis" } }
    ]
  }
}
```

### 2.6 Subgraph

Инкапсуляция и переиспользование.

**Params:**
```typescript
{
  as?: "macro" | "pipeline"   // presentation hint
  sealed?: boolean            // запрет наследования
  extends?: string            // одиночное наследование
}
```

Inputs/outputs выводятся из boundary edges. Редактор позволяет переименовывать wrapper-порты.

**Одиночное наследование:** для композиции вместо множественного наследования — вкладывайте subgraph-ы друг в друга. Проще, предсказуемее, debuggable.

---

## 3. Система типов

### 3.1 Типы

- **Примитивы:** `int`, `float`, `bool`, `string`, `bytes`, `any`
- **Составные:** `list<T>`, `dict<K,V>`, `tuple<T1,...,Tn>`, `option<T>`
- **Потоки:** `stream<T>`
- **Объединения:** `T1 | T2`
- **Схемы:** `jsonschema:<URI>`

### 3.2 Совместимость

1. Exact match → ok
2. Widening: `int → float`, `T → any`, `list<T> → list<any>`
3. Optional: `T → option<T>` ok; обратное — через adapter
4. Union: `T → (T|X)` ok; `(A|B) → A` — через adapter
5. Stream: `stream<T> → stream<any>` ok; `stream<T> → list<T>` — через windowing

### 3.3 Адаптеры (подсказки)

Когда типы не совпадают, валидатор **предлагает** (никогда не вставляет автоматически):
- `Cast(int → float)`
- `Window(tumbling, size=N)` + `Materialize` для stream → batch
- `Default(T)` для `option<T> → T`

---

## 4. Система портов

### 4.1 Optional-порты

В шаблоне: `{ "name": "b", "type": "T", "optional": true }`

В инстансе: `"params": { "enable_ports": ["b"] }`

### 4.2 Variadic PortGroup

В шаблоне:
```json
{
  "name": "arg", "direction": "in", "type": "T",
  "variadic": true, "min": 1, "max": 8, "n_param": "arg_count"
}
```

В инстансе: `"params": { "arg_count": 3 }` → создаёт `arg1, arg2, arg3`

### 4.3 Derived Ports

Subgraph inputs/outputs вычисляются автоматически из boundary edges.

---

## 5. Runtime и Config

Runtime (как выполняется) и config (что делает) — разные вещи, живут в разных местах.

### 5.1 RuntimeOverrides (на ноде)

```typescript
{
  reliability?: {
    retries?: { max: number, backoff?: "exp" | "linear", jitter?: boolean }
    timeout_ms?: number
    circuit?: { failureRate: number, window: number, cooldown_ms: number }
  }
  flow?: {
    backpressure?: { mode: "block" | "drop" | "buffer", max_inflight?: number }
    batch?: { size: number }
  }
  observability?: {
    metrics?: "basic" | "full"
    trace?: boolean
  }
}
```

### 5.2 Config

Всё, что влияет на логику, живёт в `params`: seed, secrets mapping, domain-specific настройки.

### 5.3 GraphDefaults

```typescript
{
  runtime?: RuntimeOverrides
  preset?: "proto-lax" | "startup-safe" | string
}
```

### 5.4 Встроенные пресеты

**`proto-lax`** (дефолт для proto):
```json
{
  "reliability": { "retries": { "max": 0 }, "timeout_ms": 60000 },
  "flow": { "backpressure": { "mode": "drop" } },
  "observability": { "metrics": "basic", "trace": false }
}
```

**`startup-safe`** (дефолт для startup):
```json
{
  "reliability": { "retries": { "max": 2, "backoff": "exp", "jitter": true }, "timeout_ms": 30000 },
  "flow": { "backpressure": { "mode": "buffer", "max_inflight": 128 } },
  "observability": { "metrics": "full", "trace": true }
}
```

### 5.5 Приоритет

```
preset < graph.defaults.runtime < node.runtime
```

Мерж на уровне полей (не полная замена).

### 5.6 Edge.window

```typescript
{ type: "tumbling" | "sliding" | "session", size: string, slide?: string, grace?: string }
```

---

## 6. State Management

### 6.1 State Node vs Stateful Template

| | State Node (примитив) | Stateful Template (атрибут) |
|---|---|---|
| Что | Явная внешняя память (K/V) | Внутренняя мутабельность в `run()` |
| Lifetime | Переживает рестарты (redis) | Привязан к Scope/Graph-run |
| Кэширование | Да | Нет |
| Retry | Безопасно | Только с `idempotent: true` |
| Distributed | Через redis | Не поддерживается |

### 6.2 Правило

Между нодами или между запусками → State Node. Внутри одного `run()` → stateful template.

---

## 7. Runtime Execution

### 7.1 Фазы выполнения

1. **Validation:** проверка типов, обязательных входов, стратегий рёбер, capabilities
2. **Linting:** god-node detection, broad capabilities, stringly-typed (§10)
3. **Explain Plan:** генерация плана выполнения (§9)
4. **Planning:** топологическая сортировка с учётом priority и barriers
5. **Execution:** runtime wrapper → sandbox/capability enforcement → `run()` → сбор выходов
6. **Edge reduction:** strategy (direct/concat/zip/reduce) и window
7. **Output:** внешние выходы, логи, метрики
8. **Execution Receipt:** генерация отчёта о выполнении (§9)

### 7.2 Node Wrapper Order

```
backpressure → timeout → circuit-breaker → retries →
capability_enforcement → sandbox → run() → metrics/trace
```

Для `pure` нод: мемоизация по `hash(inputs, params, template_version, seed, code_hash)`.
Для `stateful` нод: мемоизация запрещена.

### 7.3 Capability Enforcement (security: "managed")

Linux-first (proto + startup):
- **FS:** bind-mounts с allowlist
- **NET:** egress proxy с allowlist URL
- **GPU:** device cgroup
- **Subprocess:** seccomp block

Proto: enforcement выключен (логирование).
Startup: soft enforcement (логирование нарушений) с возможностью hard mode.

### 7.4 Sandbox Selection (security: "safe")

```
Proto:   seccomp → basic container (что доступно)
Startup: gVisor (preferred) → seccomp (fallback)
```

### 7.5 Мини-скелет выполнения

```python
async def exec_graph(graph, inputs):
    # 1-2. Validation + Linting
    errors = validate(graph)
    warnings = lint(graph)
    if errors:
        raise ValidationError(errors)

    # 3. Explain Plan
    plan = build_explain_plan(graph, warnings)
    emit(plan)  # proto: stdout, startup: structured log

    if graph.explain_only:
        return plan

    # 4. Planning
    schedule = topological_sort(graph, plan)

    # 5-7. Execution
    receipt = ExecutionReceipt(plan_id=plan.id)
    results = {}

    for node in schedule:
        node_record = receipt.start_node(node.id)
        try:
            out = await exec_node(node, gather_inputs(node, results), graph.tier)
            results[node.id] = out
            node_record.finish(status="ok", outputs=summarize(out))
        except Exception as e:
            node_record.finish(status="error", error=str(e))
            handle_error(node, e, graph, receipt)

    # 8. Execution Receipt
    receipt.finish(status="ok" if not receipt.has_errors else "partial")
    emit(receipt)

    return results


async def exec_node(node, in_values, tier):
    rt = merge_runtime(graph.defaults.runtime, node.runtime)

    if node.security == "raw":
        if tier == "proto":
            log.warn(f"Raw node {node.id} in proto")
        elif tier == "startup":
            require(node.params.get("reason"), "Raw node requires reason")
            log.warn(f"Raw node {node.id}: {node.params['reason']}")

    with backpressure(rt.flow), metrics(node), tracing(rt.observability):
        with timeout(rt.reliability), circuit(rt.reliability):
            for attempt in retry_iter(rt.reliability):
                try:
                    with capability_context(node.capabilities, tier):
                        with sandbox_context(node.sandbox, tier):
                            out = await maybe_async(node.entry.run)(in_values, node.params)
                    return out
                except TransientError:
                    if not attempt.has_next():
                        raise
```

---

## 8. Обработка ошибок

### 8.1 Базовая модель

Исключение из `run()` → обогащается контекстом (node-id, inputs, params, stack).

### 8.2 OnError (на ноде)

Каждая нода сама декларирует своё поведение при ошибке:

```typescript
OnError = {
  action?: "stop_graph" | "stop_branch" | "skip"  // default: "stop_graph"
  fallback?: string       // template id: запустить с теми же inputs
  compensate?: string     // template id: откатить side-effects
}
```

```json
{ "id": "ml_predict", "type": "Compute", "on_error": { "action": "skip", "fallback": "rule_predict" } }
{ "id": "charge",     "type": "Compute", "on_error": { "compensate": "refund" } }
```

Fallback запускается **вместо** упавшей ноды с теми же inputs. Compensation запускается **после** провала downstream-ноды для отката side-effects.

### 8.3 Dead Letter Queue (на графе)

Когда нода падает после всех retries и `action: "skip"`:

```typescript
DLQConfig = {
  enabled: boolean
  backend: "memory" | "redis"
  max_size?: number
  ttl?: number
}
```

Сообщение (inputs + params + error + node_id + timestamp) уходит в DLQ. Граф продолжает. DLQ доступна для инспекции и replay.

### 8.4 Compensations

Если нода B упала, compensations всех успешно выполненных upstream-нод (у которых есть `compensate`) запускаются в обратном порядке.

**Ограничения (proto/startup):**
- Последовательно, в обратном порядке
- Best-effort (если compensation падает — логируется)
- Нет вложенных compensations

---

## 9. Explain Plan и Execution Receipt

Два артефакта, которые делают граф прозрачным: Plan показывает намерение, Receipt показывает реальность. Вместе они дают полную картину — от «что я ожидал» до «что произошло и почему».

### 9.1 Explain Plan

Генерируется **до** выполнения, после validation и linting. Это `--dry-run` для графа: читаешь план — понимаешь, что произойдёт, без запуска.

**Структура:**

```typescript
ExplainPlan = {
  id: string                        // уникальный id плана
  graph_id: string
  graph_version: string
  tier: "proto" | "startup"
  generated_at: string              // ISO timestamp
  
  // Порядок выполнения
  schedule: ScheduleEntry[]

  // Предупреждения линтера
  warnings: LintWarning[]

  // Сводка
  summary: PlanSummary
}

ScheduleEntry = {
  order: number                     // порядковый номер в топологической сортировке
  node_id: string
  node_type: string                 // e.g. "Compute", "Map", "Route"
  security?: "raw" | "managed" | "safe"
  
  // Effective runtime (preset + defaults + overrides, уже смерженный)
  effective_runtime: RuntimeOverrides
  
  // Что нода будет делать
  sandbox?: string                  // какой sandbox выберется
  capabilities?: Capabilities       // какие capabilities запрошены
  cacheable: boolean                // pure/idempotent → может быть кэширована
  
  // Error handling
  on_error?: OnError
  
  // Зависимости
  waits_for: string[]               // node_id[] — от каких нод зависит
  feeds_into: string[]              // node_id[] — кому передаёт результат
}

LintWarning = {
  node_id?: string                  // null для graph-level warnings
  rule: string                      // e.g. "god_node", "broad_capabilities"
  severity: "warning" | "error"
  message: string
}

PlanSummary = {
  total_nodes: number
  by_security: { raw: number, managed: number, safe: number }
  cacheable_nodes: number           // сколько нод могут быть кэшированы
  has_fallbacks: boolean
  has_compensations: boolean
  has_dlq: boolean
  estimated_parallelism: number     // макс. нод, выполняемых одновременно
}
```

**Пример вывода (human-readable, proto):**

```
══════════════════════════════════════════════
 EXPLAIN PLAN  etl-pipeline v0.1.0 (startup)
 Generated: 2024-01-15T10:30:00Z
 Plan ID: plan_a1b2c3
══════════════════════════════════════════════

 SCHEDULE (4 nodes)
──────────────────────────────────────────────
 #1  read          Compute/managed   → parse
     sandbox: —    capabilities: fs.read[/data/**]
     runtime: timeout=30s retries=2 (exp+jitter)
     cacheable: no (side-effects)

 #2  parse         Compute/safe      → transform
     sandbox: gVisor
     runtime: timeout=30s retries=2 (exp+jitter)
     cacheable: yes
     on_error: skip → fallback:Parse.TSV

 #3  transform     Map               → stats
     body: inline (1 node)
     runtime: timeout=30s retries=2 (exp+jitter)
     cacheable: yes

 #4  stats         Compute/safe      → $output
     sandbox: gVisor
     runtime: timeout=30s retries=2 (exp+jitter)
     cacheable: yes

 WARNINGS
──────────────────────────────────────────────
 ⚠ parse: no conformance tests (recommended for startup)

 SUMMARY
──────────────────────────────────────────────
 Nodes: 4 (0 raw, 1 managed, 3 safe)
 Cacheable: 3/4
 Fallbacks: yes (parse → Parse.TSV)
 DLQ: memory (max 500)
 Max parallelism: 1 (linear pipeline)
══════════════════════════════════════════════
```

**Режим explain-only:** `graph run --explain` генерирует план без выполнения.

### 9.2 Execution Receipt

Генерируется **после** выполнения. Это `git log` для одного запуска: что реально произошло, сколько заняло, где отклонилось от плана.

**Структура:**

```typescript
ExecutionReceipt = {
  id: string                        // уникальный id receipt
  plan_id: string                   // ссылка на Explain Plan
  graph_id: string
  graph_version: string
  tier: "proto" | "startup"
  started_at: string
  finished_at: string
  status: "ok" | "partial" | "failed"

  // Per-node результаты
  nodes: NodeRecord[]

  // Отклонения от плана
  deltas: Delta[]

  // Error handling activity
  fallbacks_triggered: FallbackRecord[]
  compensations_triggered: CompensationRecord[]
  dlq_entries: number

  // Сводка
  summary: ReceiptSummary
}

NodeRecord = {
  node_id: string
  status: "ok" | "skipped" | "failed"
  started_at: string
  finished_at: string
  duration_ms: number
  retries: number                   // сколько retry было
  retry_errors?: string[]           // причины retry
  from_cache: boolean               // результат из кэша?
  output_summary?: object           // краткое описание выхода (типы, размеры)
  error?: string                    // если failed
}

Delta = {
  type: "retry" | "fallback" | "compensation" | "timeout" | "circuit_open" | "cache_hit"
  node_id: string
  detail: string
}

FallbackRecord = {
  failed_node: string
  fallback_template: string
  status: "ok" | "failed"
  duration_ms: number
}

CompensationRecord = {
  trigger_node: string              // нода, чей провал запустил compensation
  compensated_node: string          // нода, которую откатываем
  template: string
  status: "ok" | "failed"
  duration_ms: number
}

ReceiptSummary = {
  total_duration_ms: number
  nodes_ok: number
  nodes_skipped: number
  nodes_failed: number
  cache_hits: number
  total_retries: number
  fallbacks_used: number
  compensations_run: number
}
```

**Пример вывода (human-readable):**

```
══════════════════════════════════════════════
 EXECUTION RECEIPT  etl-pipeline v0.1.0
 Plan: plan_a1b2c3
 Run:  run_x7y8z9
 Status: partial
══════════════════════════════════════════════

 NODES
──────────────────────────────────────────────
 ✓ read          143ms   managed   
 ✗ parse          27ms   safe      FAILED: InvalidCSV
   ↳ fallback Parse.TSV  89ms      OK
 ✓ transform     312ms   safe      (Map: 1547 items)
 ✓ stats          18ms   safe      cached

 DELTAS FROM PLAN
──────────────────────────────────────────────
 [fallback]  parse → Parse.TSV (InvalidCSV)
 [cache_hit] stats (inputs unchanged)

 SUMMARY
──────────────────────────────────────────────
 Duration:       589ms
 Nodes:          3 ok, 0 skipped, 1 failed
 Cache hits:     1/4
 Retries:        0
 Fallbacks:      1 (all succeeded)
 Compensations:  0
 DLQ entries:    0
══════════════════════════════════════════════
```

### 9.3 Формат вывода по тирам

| | Proto | Startup |
|---|---|---|
| **Explain Plan** | stdout (human-readable) | structured JSON log + human-readable |
| **Execution Receipt** | stdout (human-readable) | structured JSON log + human-readable |
| **Хранение** | не хранится (только вывод) | файл/redis, настраивается |
| **`--explain` mode** | да | да |
| **Receipt в CI/CD** | нет | да (артефакт сборки) |

### 9.4 Использование

**Во время разработки:**
```bash
# Посмотреть план без запуска
$ graph run --explain etl-pipeline.json

# Запустить и получить receipt
$ graph run etl-pipeline.json
# ... вывод ...
# Receipt saved: .gps/receipts/run_x7y8z9.json
```

**В CI/CD (startup):**
```bash
# Сравнить plan с предыдущим (детект неожиданных изменений)
$ graph plan-diff etl-pipeline.json --baseline .gps/plans/last.json
  + node "validate" added (Compute/safe)
  ~ parse: timeout 30s → 60s
  - node "legacy_transform" removed

# Прогнать и сохранить receipt как артефакт
$ graph run etl-pipeline.json --receipt-out artifacts/receipt.json
```

**В debugging:**
```bash
# Replay от конкретного receipt (пропускает cached/ok ноды)
$ graph replay --from .gps/receipts/run_x7y8z9.json --start-at parse
```

### 9.5 Plan → Receipt связь

Receipt всегда ссылается на Plan по `plan_id`. Это позволяет:
- Сравнить ожидание с реальностью (plan-diff)
- Найти все запуски одного и того же плана
- Воспроизвести точные условия запуска

В proto связь — через id в stdout. В startup — через JSON-файлы с перекрёстными ссылками.

---

## 10. Линтер

### 10.1 God Node

```python
if node.kind == "Compute" and node.loc > 200:
    error("God Node: разбейте на меньшие ноды")
```

### 10.2 Broad Capabilities

```python
if "/**" in capabilities or "/*" in capabilities:
    warning("Слишком широкие capabilities — сужайте перед продом")
```

### 10.3 Stringly Typed

```python
if edge.type == "string" and looks_like_json(edge.sample):
    warning("Возможно stringly typed — используйте dict или jsonschema")
```

### 10.4 Proto Leak

```python
if graph.tier == "proto" and deployment.target == "production":
    fatal("Proto графы нельзя деплоить в production")
```

### 10.5 Orphan State

```python
if node.kind == "State" and not has_consumers(node, "value"):
    warning("State без читателей")
```

Результаты линтера включаются в Explain Plan (§9.1) как `warnings`.

---

## 11. Версионирование

### 11.1 Lockfile

```json
{ "Math.Square": "1.0.0", "FS.ReadText": "1.2.3" }
```

Proto: optional. Startup: optional, рекомендуется.

### 11.2 Semver

MAJOR — ломает. MINOR — обратно совместимо. PATCH — багфиксы.

### 11.3 Сосуществование

`FS.ReadText@1.2.3` и `FS.ReadText@2.0.0` могут быть в одном графе.

---

## 12. Checkpoints

Только `pure` или `idempotent` ноды. Ключ: `hash(inputs, params, template_version, seed, code_hash)`.

Proto: local FS. Startup: local FS или Redis.

Secrets никогда не сериализуются. Cache hits отражаются в Execution Receipt.

---

## 13. Debugging

- **Breakpoints:** по node-id или condition
- **Step controls:** into/over/out (включая тело Iterate)
- **Why empty?:** объяснение на любом входе
- **Replay:** от receipt — пропускает cached/ok ноды, перевыполняет остальные
- **Plan-diff:** сравнение двух Explain Plans для отлова неожиданных изменений

---

## 14. Edge Strategies

- **direct:** один источник на вход
- **concat:** несколько источников → конкатенация
- **zip:** синхронное слияние (требует window)
- **reduce:** несколько источников → fold

---

## 15. Proto vs Startup

| Аспект | Proto | Startup |
|--------|-------|---------|
| **Цель** | Эксперименты | MVP / POC |
| **Compute Raw** | Свободно | Warning + `reason` |
| **Safe sandbox** | seccomp / что есть | gVisor preferred |
| **Managed capabilities** | Игнорируются | Soft enforcement |
| **Runtime overrides** | Без ограничений | Без ограничений |
| **Lockfile** | Не нужен | Рекомендуется |
| **Conformance tests** | Не нужны | Рекомендуются |
| **Expiry** | 30 дней | Нет |
| **Data** | Только синтетика | Любые |
| **Production deploy** | Запрещён | Разрешён |
| **DLQ** | memory | memory или redis |
| **Explain Plan** | stdout | stdout + JSON |
| **Execution Receipt** | stdout | stdout + JSON + CI artifact |

### Переход Proto → Startup

Прямого пути нет. Proto — одноразовый. Чеклист при переписывании:

1. Убрать `expires`
2. Добавить `reason` ко всем Raw нодам или заменить на Safe/Managed
3. Заполнить capabilities для Managed нод
4. Добавить examples к кастомным шаблонам
5. `tier: "startup"`

---

## 16. Примеры

### 16.1 Proto: быстрый эксперимент

```json
{
  "id": "quick-experiment",
  "version": "0.0.1",
  "tier": "proto",
  "expires": "2024-02-15T00:00:00Z",
  "inputs": [],
  "outputs": [{ "name": "result", "type": "any" }],
  "nodes": [
    { "id": "process", "type": "Compute", "params": { "security": "raw", "script": "hack.py" } }
  ],
  "edges": []
}
```

### 16.2 Startup: ETL с error handling

```json
{
  "id": "etl-pipeline",
  "version": "0.1.0",
  "tier": "startup",
  "inputs": [{ "name": "source_path", "type": "string" }],
  "outputs": [{ "name": "stats", "type": "dict<string, int>" }],
  "defaults": { "preset": "startup-safe" },
  "dlq": { "enabled": true, "backend": "memory", "max_size": 500 },
  "nodes": [
    { "id": "read", "type": "FS.ReadText" },
    {
      "id": "parse",
      "type": "Parse.CSV",
      "params": { "delimiter": "auto" },
      "on_error": { "action": "skip", "fallback": "Parse.TSV" }
    },
    {
      "id": "transform",
      "type": "Map",
      "params": {
        "body": {
          "nodes": [{ "id": "norm", "type": "Normalize.Row" }],
          "edges": [
            { "from": { "node": "$input", "port": "item" }, "to": { "node": "norm", "port": "row" } },
            { "from": { "node": "norm", "port": "result" }, "to": { "node": "$output", "port": "item" } }
          ]
        }
      }
    },
    { "id": "stats", "type": "Compute", "params": { "security": "safe", "entrypoint": "stats.py:run" } }
  ],
  "edges": [
    { "from": { "node": "$input", "port": "source_path" }, "to": { "node": "read", "port": "path" } },
    { "from": { "node": "read", "port": "text" }, "to": { "node": "parse", "port": "data" } },
    { "from": { "node": "parse", "port": "rows" }, "to": { "node": "transform", "port": "data" } },
    { "from": { "node": "transform", "port": "result" }, "to": { "node": "stats", "port": "data" } },
    { "from": { "node": "stats", "port": "result" }, "to": { "node": "$output", "port": "stats" } }
  ]
}
```

### 16.3 Scope: атомарный апдейт

```json
{
  "id": "update_balance",
  "type": "Scope",
  "params": { "atomic": true, "resources": ["redis"] },
  "body": {
    "nodes": [
      { "id": "set_bal", "type": "State", "params": { "op": "set", "key": "user:123:balance", "backend": "redis" } },
      { "id": "set_ts",  "type": "State", "params": { "op": "set", "key": "user:123:updated", "backend": "redis" } }
    ],
    "edges": []
  }
}
```

### 16.4 Compensation (saga-lite)

```json
{
  "id": "order-flow",
  "version": "0.1.0",
  "tier": "startup",
  "nodes": [
    { "id": "reserve", "type": "Inventory.Reserve", "on_error": { "compensate": "Inventory.Release" } },
    { "id": "charge",  "type": "Payment.Charge",    "on_error": { "compensate": "Payment.Refund" } },
    { "id": "ship",    "type": "Shipping.Create" }
  ],
  "edges": [
    { "from": { "node": "reserve", "port": "ok" }, "to": { "node": "charge", "port": "order" } },
    { "from": { "node": "charge", "port": "ok" }, "to": { "node": "ship", "port": "order" } }
  ]
}
```

Если `ship` падает → `Payment.Refund`, затем `Inventory.Release`. Всё записывается в Execution Receipt.

---

## 17. Roadmap: Midmarket и Enterprise

Midmarket и Enterprise тиры находятся **в разработке** и будут специфицированы по фидбэку от proto/startup пользователей. Ниже — концептуальная разница.

| Аспект | Proto | Startup | Midmarket | Enterprise |
|--------|-------|---------|-----------|------------|
| **Цель** | Эксперименты | MVP / POC | Production | Regulated / compliance |
| **Compute Raw** | Свободно | Warning + reason | Approval token (TTL ≤ 7d) | 2-of-N crypto signatures |
| **Safe sandbox** | seccomp | gVisor | gVisor / WASM | WASM / microVM |
| **Managed enforcement** | Выключен | Soft | Hard (блокировка) | Hard + attestation |
| **Runtime overrides** | Без ограничений | Без ограничений | Ограничены | Только через presets |
| **Lockfile** | Optional | Рекомендуется | Обязателен в prod | Обязателен всегда |
| **Conformance tests** | Optional | Рекомендуются | Обязательны (≥1) | Comprehensive suite |
| **Production deploy** | Запрещён | Разрешён | Разрешён | Разрешён |
| **Explain Plan** | stdout | stdout + JSON | JSON + hash | JSON + hash + подпись |
| **Execution Receipt** | stdout | stdout + JSON + CI | JSON + хранение | JSON + подпись + аудит |
| **Plan conformance** | Нет | Нет | Warning при drift | Блокировка при drift |
| **Traits / dispatch** | Нет | Нет | Optional | Полная поддержка |
| **Distributed execution** | Нет | Нет | Executors + islands | + placement + isolation |
| **OS support** | Linux | Linux | Linux + Cloud | Linux + Cloud + Windows |

**Ключевые фичи, ожидаемые в midmarket/enterprise:**
- Plan conformance (блокировка выполнения при расхождении с утверждённым планом)
- Cryptographic signing of plans and receipts
- Traits и operator dispatch
- Distributed execution (executors, islands, partitioning)
- Cryptographic approvals для Raw нод
- Template migrations
- OS-agnostic capability enforcement
- Policy presets library

Переход **Startup → Midmarket → Enterprise** — инкрементальный (в отличие от Proto → Startup). Код из startup работает в более строгих тирах без изменений; добавляются только новые требования. Plan и Receipt, заложенные в proto/startup, становятся фундаментом для аудита и conformance в старших тирах.

---

## 18. Pragmatic Security (Proto/Startup Focus)

### 18.1 Принцип "Необходимо и Достаточно"

**Proto:** минимальная безопасность, максимальная скорость. Песочница резиновая — внутри можно гадить, контейнер всё равно убьём.

**Startup:** базовая гигиена без оверхеда. TLS есть, secrets не в plain text, но без фанатизма.

**Не делайте security ради security** — каждый контроль должен решать реальную проблему, не гипотетическую.

### 18.2 Justification Validation

**Proto:** не требуется. Пишите что хотите, или вообще не пишите.

**Startup:** regex обязателен для Raw nodes.

```yaml
tier: startup
raw_node_justification:
  regex: "^(INC-\\d+|JIRA-\\d+): .{20,}"
  # Требует: ticket ID + минимум 20 символов описания
```

**Примеры:**
```
✓ "INC-2024-042: Emergency customer data recovery after DB corruption"
✓ "JIRA-1234: Legacy ETL script, migration to managed planned for Q2"
✗ "надо"
✗ "срочно"
✗ "потом исправлю"
```

UI просто не даст сохранить граф пока `reason` не матчится. Одна строка кода — огромная польза.

### 18.3 Data Encryption

**Проблема:** Client-Side Encryption (CSE) для всего убивает производительность:
- Блокирует Zero-Copy optimization
- Запрещает sendfile() syscall
- CPU потеет над каждым мегабайтом

**Решение для Startup:** Гибридная схема "Не шифруй кирпичи, шифруй алмазы"

| Тип данных | Размер | Метод | Обоснование |
|-----------|--------|-------|-------------|
| **Checkpoints** (parquet, blobs) | >10MB | SSE-S3 | Провайдер шифрует аппаратно, Zero-Copy работает |
| **Secrets в State** | <1KB | В памяти plain, Redis с TLS | Не шифруй каждое value, используй transport encryption |
| **Логи** | varies | Без PII → без шифрования | Не логируй секреты — проблема решена |

**Proto:** шифрование отсутствует полностью.

**Startup пример:**
```python
# Checkpoint: большой blob
s3_client.put_object(
    Bucket='checkpoints',
    Key='exec_123.parquet',
    Body=large_data,
    ServerSideEncryption='AES256'  # ← S3 сам шифрует
)

# State: секрет
redis.set('session:abc', session_token)  # plain text в Redis
# ↑ Но Redis подключен через TLS, диск encrypted at rest
```

**Модель угроз:** Не "AWS украдет диски", а "Админ сделает бакет public". SSE решает: без прав на бакет данные = мусор.

### 18.4 Identity & Authentication

**Proto:**
- Shared secret или вообще без auth
- Если кто-то внутри контейнера перехватит трафик — плевать, там синтетика

**Startup:**
- **Server-side TLS обязателен** — трафик в plain text не летает
- Bearer Token в заголовке для аутентификации воркеров
- Ротация ключей — раз в год (когда техлид уволится)

```python
# Startup worker auth
headers = {"Authorization": f"Bearer {WORKER_TOKEN}"}
response = requests.post("https://scheduler/api/task", headers=headers)
```

**mTLS / SPIRE?** Не для startup. Это целая команда ops-инженеров на fulltime. В midmarket/enterprise будет Cloud Native Identity (KSA + OIDC).

### 18.5 Dependency Management

**Proto:**
- `pip install` прямо с PyPI
- Если прилетит малварь — убьём контейнер, делов-то

**Startup:**
- Прокси-репозиторий (Nexus/Artifactory) желателен
- **Запрет на "latest" теги** — только pin версий
- Lockfile рекомендуется, но не блокирует

```toml
[tool.poetry.dependencies]
requests = "2.31.0"  # НЕ "^2.31.0"
pandas = "2.0.3"     # Точная версия
```

### 18.6 Break-glass (для будущего)

**Proto:** не нужен — в этом режиме стекла нет, одни подушки.

**Startup:** Simple logging в CloudWatch/ELK:
```json
{
  "event": "raw_node_override",
  "node_id": "legacy_etl",
  "reason": "INC-2024-042: Emergency recovery",
  "user": "oncall@company.com",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Midmarket/Enterprise:** тут уже 2FA, dual approval, multi-sig — но это потом.

### 18.7 Что НЕ делать в Proto/Startup

❌ **Envelope encryption для checkpoints** — оверкилл, используйте SSE-S3  
❌ **mTLS между нодами** — сложно, дорого, в startup не нужно  
❌ **WORM audit logs** — для compliance, в startup обычные логи хватит  
❌ **SCA сканеры в блокирующем режиме** — warnings достаточно  
❌ **Digital signatures на policies** — offline HSM это enterprise  

---

## 19. Security TODO: Midmarket & Enterprise

Фиксируем находки из v4.2 для будущей разработки.

### 19.1 Identity & Authentication

**Midmarket:**
- [ ] **mTLS между воркерами** (Istio/Linkerd service mesh)
- [ ] **VPN + IP Whitelisting** как fallback
- [ ] Автоматическая ротация ключей (90 дней)
- [ ] Интеграция с корпоративным SSO (SAML/OIDC)

**Enterprise:**
- [ ] **Cloud Native Identity** (primary рекомендация):
  - Kubernetes Service Accounts (KSA) + OIDC Federation
  - IRSA (AWS) / Workload Identity (GCP/Azure)
  - Zero maintenance, токены живут 1 час, авто-ротация
- [ ] **SPIFFE/SPIRE** (только если multi-cloud без OIDC):
  - Self-hosted PKI с автоматической ротацией
  - Dedicated ops-команда для админки
  - Attestation: TPM 2.0, Secure Boot
- [ ] Service Mesh поверх Cloud Identity для pod-to-pod mTLS

**Decision framework:** 95% безопасности за 5% усилий = KSA + OIDC. SPIRE только при жестких требованиях.

### 19.2 Policy Management

**Midmarket:**
- [ ] **Policies только через CI/CD:**
  - Git + Code Review обязательны
  - ReadOnly доступ к базе (кроме service account)
  - `UPDATE policies` руками — запрещено
- [ ] **Policy-diff в PR:**
  - Показывать только overrides, не полный preset
  - Блокировать если delta > N% от baseline
- [ ] **Versioned presets:**
  - `prod-strict-v2`, `dev-lax-v3`
  - Migration path между версиями

**Enterprise:**
- [ ] **Digital signatures на артефактах:**
  - Policy JSON подписывается offline HSM-ключом
  - Runtime проверяет подпись перед загрузкой
  ```bash
  gpg --detach-sign --armor policy_v2.json
  # Runtime: if !verify(policy.json.asc): reject()
  ```
- [ ] **Immutable audit trail:**
  - Кто/когда/зачем изменил preset
  - WORM storage для истории изменений

### 19.3 Encryption

**Midmarket:**
- [ ] **KMS-managed keys** (AWS KMS/GCP Cloud KMS):
  - SSE-KMS для S3/GCS checkpoints
  - Ключи ротируются облаком (90 дней)
  - Контроль через IAM policies
  ```python
  kms_client.encrypt(
      KeyId='arn:aws:kms:region:account:key/abc123',
      Plaintext=sensitive_data
  )
  ```
- [ ] **Secrets в State:** шифрование critical fields
  ```python
  # Не весь Redis, только PII/tokens
  encrypted_token = encrypt_field(api_token, kms_key)
  redis.set('user:123:token', encrypted_token)
  ```

**Enterprise:**
- [ ] **Гибридная схема (по типу данных):**
  
  **Data Plane (blobs >10MB):**
  - SSE-KMS (Server-Side Encryption)
  - S3/GCS сам шифрует на дисках твоим ключом
  - Zero-Copy и sendfile() работают
  
  **Control Plane (секреты, PII <100KB):**
  - Envelope Encryption (Client-Side)
  - Генерация data key через KMS
  - Шифрование в памяти перед отправкой
  ```python
  # Control Plane: секрет
  data_key = kms.generate_data_key()
  encrypted = aes_gcm_encrypt(api_token, data_key.plaintext)
  store(encrypted, data_key.ciphertext)  # Envelope
  
  # Data Plane: большой checkpoint
  s3.put_object(..., ServerSideEncryption='aws:kms')  # SSE
  ```
  
  **State (Redis):**
  - TLS in transit + Encrypted EBS/Persistent Disk
  - Шифрование только critical fields (session data, tokens)
  - Не шифруй каждое cache value на лету

- [ ] **Automatic key rotation:**
  - Daily для enterprise tier
  - Graceful key migration без downtime

**Принцип:** Не шифруй кирпичи (blobs) в броневик. Шифруй алмазы (secrets). Кирпичи вози в самосвале под брезентом (SSE-KMS).

### 19.4 Dependency Security

**Midmarket:**
- [ ] **Lockfile enforcement:**
  - Обязателен в production
  - CI блокируется без lockfile
  - `poetry.lock` / `package-lock.json`
- [ ] **Private mirror приоритет:**
  ```yaml
  dependencies:
    allowed_public:
      - numpy>=1.24.0,<2.0.0  # Явный allowlist
      - pandas==2.0.3
    mirror_priority: private_first
    lockfile_enforcement: ci_blocking
  ```
- [ ] **SCA сканеры в advisory mode:**
  - Snyk/BlackDuck/Dependabot
  - Warning в PR, не блокирует

**Enterprise:**
- [ ] **Vendoring или Air-gapped mirror:**
  - Полная копия PyPI внутри корпсети
  - Нет доступа к публичному интернету
- [ ] **Проверка подписей пакетов:**
  ```yaml
  dependencies:
    mode: vendored
    verification:
      - gpg_signatures
      - sha512_checksums
    sca:
      scanners: [snyk, blackduck, grype]
      policy: blocking  # CI fails при CVSS > 4.0
      max_cvss: 4.0
  ```
- [ ] **Reproducible builds:**
  - Байт-в-байт воспроизводимые артефакты
  - Hash-based verification

### 19.5 Break-glass & Emergency Procedures

**Midmarket:**
- [ ] **2FA + Dual Approval:**
  ```python
  @require_approval(approvers=["oncall-lead"], mfa=True)
  def emergency_override(graph_id, justification):
      log_audit(event="break_glass", justification=justification)
      notify_slack(channel="#security-alerts")  # Immediate
      # ... apply override
  ```
- [ ] **Justification validation:**
  ```yaml
  policies:
    break_glass:
      justification_regex: "^(INC-\\d+): .{30,}"
      require_ticket_validation: true  # Проверка что тикет существует
  ```
- [ ] **Time-limited waivers:**
  - Approval token с TTL ≤ 7 дней
  - Auto-expiry + rollback

**Enterprise:**
- [ ] **Multi-Sig (3-of-5):**
  ```python
  @require_multisig(threshold=3, signers=[
      "ciso@company.com",
      "cto@company.com", 
      "legal@company.com",
      "oncall-lead@company.com",
      "security-eng@company.com"
  ])
  def emergency_override(graph_id, incident_id):
      worm_log.append(event={
          "type": "break_glass",
          "graph": graph_id,
          "incident": incident_id,
          "signatures": get_current_signatures(),
          "immutable": True  # WORM storage
      })
  ```
- [ ] **WORM audit log:**
  - Write Once, Read Many
  - Даже админ не может удалить/изменить
  - Cryptographic chain (blockchain-like)
- [ ] **Post-mortem mandatory:**
  - Обязательный RCA после каждого break-glass
  - Tracking повторных событий

### 19.6 Migration Friction Mechanisms

**Midmarket:**
- [ ] **"Type to confirm" для security changes:**
  ```bash
  $ graph migrate fix --security
  
  ⚠️ Node 'DataProcessor': Adding net:allow:google.com
  ⚠️ Security Debt: +8% (12% → 20%)
  
  Type to confirm: I ACCEPT RISK FOR NETWORK ACCESS
  > _
  ```
- [ ] **Security Debt tracking:**
  ```bash
  $ graph migrate report
  
  Security Debt: +15% (was 8%, now 23%)
  Current Tier: Midmarket
  Blockers: 3 Raw nodes, 2 overly-broad capabilities
  
  ⚠️ These changes downgrade effective tier to Startup
  ```
- [ ] **Shame mechanism (геймификация):**
  - Dashboard с Security Debt метриками
  - PR bot: "⚠️ This PR increases security debt by 15%"
  - Не блокирует, но заставляет задуматься

**Enterprise:**
- [ ] **Automatic regression detection:**
  - Plan-diff с baseline
  - CI fails если security downgrade без waiver
- [ ] **Quarterly debt review:**
  - Forced review с security team
  - План по снижению debt до <10%

### 19.7 OS-Agnostic Enforcement

**Midmarket:**
- [ ] **Linux + Cloud support:**
  - AppArmor/SELinux для FS isolation
  - Bind-mounts / signed URLs
  - Egress proxy для NET

**Enterprise:**
- [ ] **Windows support:**
  - ACLs вместо AppArmor
  - Junctions вместо bind-mounts
  - Same capability model, different enforcement
- [ ] **Multi-cloud abstraction:**
  - Capabilities → IAM policies (AWS/GCP/Azure)
  - Platform-агностичные контракты

### 19.8 Plan Conformance

**Midmarket:**
- [ ] **Warning при drift:**
  ```bash
  $ graph run production-etl.json
  
  ⚠️ Plan drift detected:
    - Node "validate" added (not in approved plan)
    - parse: timeout changed 30s → 60s
  
  Continue? [y/N]
  ```

**Enterprise:**
- [ ] **Блокировка при drift:**
  - Execution refuse если plan hash не совпадает с approved
  - Исключение только через break-glass
- [ ] **Signed plan approval:**
  ```json
  {
    "plan_hash": "abc123...",
    "approved_by": ["tech-lead", "security"],
    "signatures": ["sig1", "sig2"],
    "valid_until": "2024-12-31"
  }
  ```

### 19.9 Distributed Execution Security

**Midmarket:**
- [ ] **Executor isolation:**
  - Raw nodes не могут быть scheduled на `prod:true` executors
  - Placement constraints по tags
- [ ] **Network segmentation:**
  - Prod/dev executors в разных VPC/zones

**Enterprise:**
- [ ] **Executor attestation:**
  - TPM-based proof при регистрации executor
  - Continuous runtime verification
- [ ] **Data residency controls:**
  - Placement rules по geo (EU data stays in EU)
  - Automatic enforcement через executor tags

---

## 20. Что НЕ входит в эту спецификацию

Отложено до midmarket/enterprise:

- Traits / operator dispatch
- Множественное наследование
- Cryptographic approvals и подписи
- Distributed execution
- OS-agnostic enforcement (сейчас Linux-first)
- Plan conformance enforcement
- Conformance testing enforcement
- Lockfile enforcement
- Template migrations
- Все security контролы из §19 (кроме базовых в §18)

---

## 21. Глоссарий

- **Port** — именованный вход/выход
- **Template** — переиспользуемая спецификация ноды
- **Node** — инстанс шаблона в графе
- **Subgraph** — нода, содержащая граф
- **Runtime** — настройки выполнения (retries, timeout, backpressure)
- **Config** — настройки логики (в params)
- **Preset** — именованная конфигурация runtime
- **Capability** — декларация доступа для managed-нод
- **Sandbox** — среда изоляции для safe-нод
- **DLQ** — Dead Letter Queue для проваленных сообщений
- **Compensation** — откатная операция (saga pattern)
- **Checkpoint** — кэш результата для replay
- **Tier** — уровень строгости (proto / startup / midmarket / enterprise)
- **Inline body** — subgraph, определённый прямо в params Iterate
- **Explain Plan** — pre-execution артефакт: что граф будет делать
- **Execution Receipt** — post-execution артефакт: что граф реально сделал
- **Delta** — расхождение между планом и фактическим выполнением
- **Plan-diff** — сравнение двух планов для отлова изменений
- **Security Debt** — метрика накопленных security компромиссов (в %)
- **SSE-KMS** — Server-Side Encryption with Customer Managed Keys
- **Envelope Encryption** — шифрование data key через master key (KMS)
- **Cloud Native Identity** — KSA + OIDC вместо собственного PKI
- **WORM Storage** — Write Once, Read Many для immutable audit logs
- **Break-glass** — экстренный override security правил с логированием
- **Justification Regex** — валидация причины для security-sensitive действий

---

*v5.3 — Proto + Startup. Pragmatic security: необходимо и достаточно. План до, Receipt после. 6 примитивов, zero surprises.*

**Changelog v5.3:**
- Добавлен §18: Pragmatic Security для Proto/Startup
  - Justification validation с regex
  - Гибридное шифрование (SSE для blobs, plain+TLS для state)
  - Принцип "не шифруй кирпичи, шифруй алмазы"
  - Identity без оверхеда (Bearer token + TLS)
- Добавлен §19: Security TODO для Midmarket/Enterprise
  - 9 категорий с actionable items
  - Конкретные технологии и примеры кода
  - Decision frameworks (Cloud Native vs SPIRE)
  - Migration friction mechanisms
