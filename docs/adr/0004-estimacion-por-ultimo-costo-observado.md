# ADR-0004: Estimación previa de costo por último costo observado

- **Estado:** Aceptado — **implementación diferida**. El MVP estima cada llamada con un valor fijo,
  `INITIAL_CALL_ESTIMATE_TOKENS`, valorizado al precio de salida, y no registra `overshoot_*`.
- **Fecha:** 2026-10-01

## Contexto
El nodo `guard` (ADR-0006) debe decidir, antes de cada llamada al LLM, si el presupuesto restante alcanza.
Si solo se verifica después, el presupuesto siempre se excede por una llamada.

## Decisión
1. El costo estimado de la siguiente llamada es el **costo real de la última llamada observada** en la
   sesión (USD y tokens), tomado de `usage_metadata` y guardado en el registro de sesión (ADR-0003).
2. Si la sesión no tiene llamadas previas, se usa `INITIAL_CALL_ESTIMATE_TOKENS` (por defecto 2000),
   valorizados al precio de salida por ser el más alto. Este valor se calibra con los datos de LangSmith.
3. `guard` permite la llamada solo si `restante_usd ≥ estimado_usd` y `restante_tokens ≥ estimado_tokens`.
4. Toda llamada envía `max_completion_tokens` acotado a los tokens restantes de la sesión, lo que limita
   el desvío en la parte de salida.
5. Si una llamada termina superando el presupuesto, el exceso se registra como `overshoot_usd` y
   `overshoot_tokens` en el `StepMetric`.

## Alternativas consideradas
- **Conteo exacto del contexto con tokenizador.** Más preciso en la entrada, pero no predice la salida
  ni los tokens de razonamiento, y agrega dependencia y latencia.
- **Promedio de las llamadas de la sesión.** Más estable, pero subestima más cuando el contexto crece.
- **Margen fijo por llamada.** Fácil de configurar, pero no se adapta al tamaño real de las consultas.

## Consecuencias
- (+) Simple, sin dependencias adicionales y basado en datos reales del mismo modelo.
- (−) **Tiende a subestimar**: cada paso agrega resultados de tools al contexto, así que la siguiente
  llamada suele tener más tokens de entrada que la anterior. El desvío queda acotado a una llamada y se
  hace visible con `overshoot_*`.
- (−) La primera llamada depende de un valor configurado, no observado.

## Relacionados
ADR-0002, ADR-0003, ADR-0006.
