# ADR-0011: Herramientas totalmente mockeadas

- **Estado:** Aceptado
- **Fecha:** 2026-10-01

## Contexto
El alcance pide herramientas simuladas que se apeguen a la especificación, sin integrar fuentes
financieras reales.

## Decisión
1. `search_financial_data(metric, period)`:
   - La tool LangChain delega en `FinancialDataPort`; el adaptador es `MockFinancialDataAdapter`.
   - Datos deterministas desde un diccionario en memoria.
   - Retraso de 2 s con `await asyncio.sleep(2)`; nunca `time.sleep`, que bloquearía el event loop.
   - Métrica o periodo desconocido → `{"error": "..."}`, sin lanzar excepción.
2. `calculate_ratio(numerator, denominator)`:
   - La tool delega en la función pura `domain/ratio.py`.
   - Retorna `{"result": numerator / denominator}`; denominador 0 → `{"error": "division by zero"}`.
3. No se agregan herramientas adicionales.
4. Las tools no consumen tokens; su costo es 0 y su latencia se refleja en `elapsed_time`.

## Alternativas consideradas
- **Ratio detrás de un puerto propio.** Coherente con la búsqueda, pero el cálculo es una regla pura sin
  dependencia externa que reemplazar.

## Consecuencias
- (+) Resultados reproducibles para pruebas y demostraciones.
- (+) Reemplazar el mock por una fuente real solo requiere un nuevo adaptador de `FinancialDataPort`.
- (−) Los errores devueltos como datos deben ser contados por el circuit breaker (ADR-0008).

## Relacionados
ADR-0001, ADR-0008.
