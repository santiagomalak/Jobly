# PROMPT — Copiloto de arquitectura técnica
> Uso: cuando el cliente pregunta "¿cómo lo harías?" y necesitás sonar (y ser) senior en 10 minutos.

```
Actuá como arquitecto de software senior. Tengo que proponerle una solución a un cliente
y quiero una arquitectura defendible, no la más elegante.

PROBLEMA DEL CLIENTE:
<pegá la descripción>

RESTRICCIONES REALES:
- Presupuesto: USD <X>
- Plazo: <N> días
- Lo construyo yo solo
- El cliente tiene que poder mantenerlo (o al menos entenderlo) sin mí
- Stack que domino: Python, Node/React, n8n, SQL/BigQuery/dbt, Playwright, Postgres/Supabase

DEVOLVEME:

1. ARQUITECTURA EN 5 LÍNEAS
   Componentes y cómo fluye el dato. Sin diagramas ASCII gigantes.

2. DECISIONES CLAVE (3 máximo)
   Para cada una: qué elegí, contra qué alternativa, y la razón en términos de
   costo/tiempo/mantenimiento — no de elegancia.

3. LOS 3 PUNTOS DONDE ESTO SE ROMPE
   Fallas reales (rate limits, duplicados, datos sucios, timeouts, cambios de layout)
   y cómo las mitigo dentro del presupuesto.

4. LO QUE DEJO AFUERA A PROPÓSITO
   Y la frase exacta para decírselo al cliente sin que suene a que no sé hacerlo.

5. PLAN DE ENTREGA POR DÍA
   Día 1 / Día 2 / Día 3: qué ve el cliente funcionando al final de cada día.

6. ESTIMACIÓN HONESTA
   Horas reales × 1.4. Si no entra en el presupuesto, decímelo y proponé el recorte.
```
