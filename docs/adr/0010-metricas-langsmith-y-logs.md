# ADR-0010: Métricas FinOps en LangSmith y logs JSON

- **Estado:** Aceptado (amplía la decisión inicial "Métricas: LangSmith logeado desde LangGraph")
- **Fecha:** 2026-10-01

## Contexto
La versión en producción no registraba tokens, costo ni llamadas a herramientas. El requisito pide, por
paso: `step_number`, `tool_called`, `tokens_used`, `cumulative_cost` y `elapsed_time`.

## Decisión
1. LangSmith se activa con tracing nativo de LangGraph (`LANGSMITH_TRACING=true`). El engine agrega
   `analyst_id`, `session_id` y `request_id` como `metadata` y `tags` del invoke.
2. Por cada paso, el dominio construye un `StepMetric` con: `step_number`, `tool_called`, `tokens_used`,
   `cumulative_tokens`, `step_cost_usd`, `cumulative_cost`, `remaining_budget_usd`, `elapsed_time`,
   `overshoot_usd` y `overshoot_tokens` (ADR-0004).
3. La métrica se emite por `MetricsPort`. `CompositeMetricsAdapter` la envía a:
   - LangSmith, como metadata del run.
   - Logs JSON a stdout: evento `analysis_step` por paso y `analysis_completed` al final.
4. Los costos en métricas son acumulados **de la sesión** (ADR-0003).
5. Si LangSmith falla, el error se registra y el log JSON se mantiene; el agente no se interrumpe.

## Alternativas consideradas
- **Solo LangSmith.** Era la decisión inicial. Deja el sistema sin métricas si LangSmith no está disponible.
- **Callbacks de LangChain para calcular costo.** Posible, pero saca el cálculo del dominio.

## Consecuencias
- (+) Gasto filtrable por analista, sesión y request.
- (+) Métricas disponibles aunque falle la plataforma de observabilidad.
- (−) Doble emisión; los logs JSON deben tener retención y rotación definidas por la plataforma.

## Relacionados
ADR-0002, ADR-0003, ADR-0004.
