# ADR-0006: Control de límites en el estado del grafo (nodo `guard`)

- **Estado:** Aceptado (implementado y probado)
- **Fecha:** 2026-10-01
- **Reemplaza:** decisión inicial "Presupuesto: limiter de LangGraph y controlar excepción".
- **Amplía:** decisión inicial "Límites: implementación nativa con rate limiter y configuraciones del grafo".

## Contexto
LangGraph no ofrece un limitador nativo de costo en USD ni de presupuesto de tokens por sesión. Si el
corte depende de una excepción (`GraphRecursionError`), la ejecución se interrumpe y se pierde el estado
salvo que haya checkpointer. Además, el patrón ReAct del borrador solo terminaba cuando el LLM decidía
hacerlo.

## Decisión
1. Se agrega un nodo `guard` que se ejecuta antes de cada llamada al LLM. Ruta: `START → guard`,
   `tool_caller → guard`.
2. `guard` delega en `ExecutionGuard` (dominio), que evalúa en orden: errores consecutivos de tools,
   presupuesto USD de la sesión, presupuesto de tokens de la sesión y número de pasos.
3. Un **paso** es una ejecución del nodo `agent` (una llamada al LLM) más las tools que dispare.
   `MAX_STEPS = 8` por request.
4. Se corta con el **primer** límite alcanzado.
5. Los mecanismos nativos quedan como red de seguridad:
   - `recursion_limit = 3 × MAX_STEPS + 3` (cada paso usa hasta tres supersteps: `guard`, `agent`, `tool_caller`).
   - Rate limiter (ADR-0005) y timeout global (ADR-0007).

## Alternativas consideradas
- **Solo `recursion_limit` y capturar la excepción.** Era la decisión inicial. No controla USD ni tokens,
  y obliga a reconstruir el estado tras la excepción.
- **Verificación dentro del nodo `agent`.** Funciona, pero mezcla la llamada al LLM con la decisión de
  corte y la hace menos visible en las trazas.

## Consecuencias
- (+) El límite es duro: se decide antes de gastar (con la estimación de ADR-0004).
- (+) Cada corte queda en la traza de LangSmith como una transición explícita de `guard`.
- (−) Un superstep adicional por paso; latencia despreciable frente a la del LLM.

## Relacionados
ADR-0001, ADR-0004, ADR-0007, ADR-0008, ADR-0009.
