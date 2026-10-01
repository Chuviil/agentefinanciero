# ADR-0012: Estrategia de pruebas con chat model falso

- **Estado:** Propuesto
- **Fecha:** 2026-10-01

## Contexto
Probar con gpt-5-mini real cuesta dinero, no es determinista y no permite forzar escenarios como bucles
o presupuesto agotado.

## Decisión
1. `tests/unit`: dominio sin frameworks (`Budget`, `ExecutionGuard`, `CircuitBreaker`, `TokenPricing`,
   ratio) y `RunAnalysisService` con dobles de los puertos.
2. `tests/integration`: grafo completo con un chat model falso que devuelve `AIMessage` predefinidos,
   incluidos `tool_calls` y `usage_metadata` controlados.
3. `tests/api`: endpoint con `httpx`.
4. Escenarios mínimos: `completed`, `loop_detected`, `budget_exceeded` por sesión acumulada,
   `token_budget_exceeded`, `max_steps_reached`, `timeout` (con timeout reducido), denominador 0,
   HTTP 409 por request concurrente y `StepMetric` completo en cada respuesta.
5. Ninguna prueba automatizada llama al LLM real.

## Alternativas consideradas
- **Pruebas contra el LLM real con presupuesto pequeño.** Validan la integración, pero son lentas,
  costosas y no reproducibles. Pueden ejecutarse manualmente como smoke test.

## Consecuencias
- (+) Pruebas rápidas, gratuitas y deterministas.
- (−) No validan la calidad de las respuestas del modelo ni la tabla de precios real; eso se monitorea en
  LangSmith.

## Relacionados
ADR-0001, ADR-0006, ADR-0008, ADR-0009.
