# ADR-0009: Respuesta parcial y contrato de la API

- **Estado:** Aceptado (implementado y probado). Diferidos junto con ADR-0003: `budget.scope = "session"`
  y el HTTP 409; el contrato actual omite `budget.scope` y el presupuesto es por request.
- **Fecha:** 2026-10-01

## Contexto
El requisito pide devolver una respuesta parcial con advertencia cuando se agota el presupuesto. Hay que
definir qué contiene, quién la redacta y con qué código HTTP se devuelve.

## Decisión
1. El nodo `finalize_partial` arma la respuesta parcial **sin llamar al LLM**, a partir de los resultados
   de tools ya obtenidos y el motivo de corte. Si el presupuesto se agotó, no se gasta más para redactar.
2. Contrato de respuesta:
   ```json
   {
     "status": "completed | partial",
     "answer": "texto",
     "warning": "null | mensaje",
     "stop_reason": "completed | budget_exceeded | token_budget_exceeded | max_steps_reached | timeout | loop_detected | tool_errors",
     "budget": {"scope": "session", "max_budget_usd": 0.5, "spent_usd": 0.0, "remaining_usd": 0.0,
                "max_tokens": 10000, "tokens_used": 0, "remaining_tokens": 0},
     "steps": ["StepMetric"],
     "elapsed_time_s": 0.0
   }
   ```
3. Códigos HTTP:
   - **200**: el agente se ejecutó, sea `completed` o `partial`.
   - **409**: la sesión ya tiene un request en ejecución (ADR-0003).
   - **422**: request inválido.
   - Ningún límite alcanzado produce 5xx.
4. Los mensajes de `answer` y `warning` van en español.

## Alternativas consideradas
- **Usar el LLM para resumir lo obtenido al cortar.** Mejor redacción, pero gasta justo cuando el
  presupuesto se agotó.
- **HTTP 402 o 429 en respuestas parciales.** Señala el corte en el código, pero los clientes HTTP suelen
  tratarlo como error y descartar el cuerpo con los datos útiles.

## Consecuencias
- (+) El analista siempre recibe lo obtenido y el motivo del corte.
- (−) La respuesta parcial es menos elaborada que una redactada por el LLM.

## Relacionados
ADR-0003, ADR-0006, ADR-0007, ADR-0008.
