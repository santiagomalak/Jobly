# Prompt para Claude in Chrome → Jobly

> **Límite ético/legal (lo digo derecho, como siempre):** este prompt trabaja **solo sobre páginas que abriste vos y estás viendo**. No pagina solo, no hace login, no postula ni manda mensajes. Upwork y Workana prohíben en sus términos la recolección automatizada masiva, y **Freelancer.com prohíbe cualquier acceso automatizado** (ya lo descartaste por su §33): ahí no lo uses. Un asistente que pasa a CSV lo que vos tenés abierto es una zona gris de bajo riesgo; un crawler no lo es, y podría costarte la cuenta justo en la plataforma donde querés cobrar.

```
Sos mi asistente de relevamiento de oportunidades laborales. Trabajá SOLO sobre las pestañas que yo tengo abiertas ahora mismo (búsquedas o avisos de Workana, Upwork, RemoteOK, We Work Remotely, LinkedIn Jobs, Get on Board, etc.). No hagas clic en "siguiente página", no inicies sesión, no postules, no envíes mensajes y no abras más de 30 avisos. Si una pestaña es de freelancer.com, salteala.

Para cada aviso visible, extraé los datos y devolveme UN SOLO bloque de código CSV con exactamente este encabezado y este orden de columnas:

titulo,empresa_o_cliente,url,fuente,tipo,modalidad,pais,seniority,presupuesto_min,presupuesto_max,moneda,periodo_pago,duracion_estimada,stack,requisitos,idioma,cliente_verificado,proyectos_previos_cliente,calificacion_cliente,gasto_total_cliente_usd,propuestas_recibidas,fecha_publicacion,fecha_relevamiento,contacto,notas

Reglas de formato (obligatorias):
- Separador coma. Encerrá TODOS los campos de texto entre comillas dobles; si un texto contiene comillas, duplicalas (""). Sin saltos de línea dentro de un campo: reemplazalos por " / ".
- Si un dato no aparece en la página, dejá el campo VACÍO. Nunca inventes, estimes ni completes con suposiciones.
- url: el link directo al aviso (no al listado), sin parámetros de tracking (sacá todo desde "?" si son utm_ o ref).
- fuente: el nombre del sitio en minúsculas (workana, upwork, remoteok, weworkremotely, linkedin, getonboard, otro).
- tipo: "freelance" si es un proyecto o contrato por tarea; "empleo" si es un puesto en relación de dependencia o contrato mensual de tiempo completo.
- modalidad: remoto | hibrido | presencial.
- pais: el país o región exigida para el candidato tal como figura (ej. "Worldwide", "LATAM", "USA only"). Vacío si no dice.
- seniority: junior | semi | senior | lead, solo si el aviso lo dice.
- presupuesto_min / presupuesto_max: números enteros sin símbolos ni separadores de miles (1500, no "1.500" ni "$1,500"). Si hay un solo monto, ponelo en ambos.
- moneda: código ISO (USD, EUR, BRL, ARS...).
- periodo_pago: hora | mes | proyecto. Sueldo anual: convertilo a mensual (÷12), poné "mes" y aclará "anual convertido" en notas.
- duracion_estimada: número de días (ej. "1 a 3 semanas" → 14 y el texto original en notas). Vacío si no dice.
- stack: tecnologías mencionadas, separadas por " | " (barra vertical), en minúsculas.
- requisitos: máximo 300 caracteres con los requisitos clave (años de experiencia, idiomas, horario).
- idioma: idioma en que está escrito el aviso: es | pt | en. Si exige llamadas o inglés fluido hablado, agregá "requiere inglés hablado" en notas.
- cliente_verificado: si | no | vacío. Solo si la plataforma lo muestra (ej. "Payment verified" en Upwork).
- proyectos_previos_cliente, calificacion_cliente (0 a 5), gasto_total_cliente_usd, propuestas_recibidas: números, solo si la plataforma los muestra (ej. "Proposals: 20 to 50" → 20).
- fecha_publicacion: AAAA-MM-DD. Si dice "hace 3 horas", calculala a partir de la fecha de hoy.
- fecha_relevamiento: la fecha de hoy, AAAA-MM-DD.
- contacto: solo si el aviso publica un email o un nombre de reclutador. Nada más.
- notas: cualquier aclaración útil, máximo 200 caracteres.
- Ningún campo puede empezar con =, +, - o @: si pasa, anteponé un apóstrofo (').

Al final, fuera del bloque CSV, decime en una línea cuántos avisos procesaste y cuáles salteaste y por qué.
```

Ejemplo de salida esperada (2 filas):

```csv
titulo,empresa_o_cliente,url,fuente,tipo,modalidad,pais,seniority,presupuesto_min,presupuesto_max,moneda,periodo_pago,duracion_estimada,stack,requisitos,idioma,cliente_verificado,proyectos_previos_cliente,calificacion_cliente,gasto_total_cliente_usd,propuestas_recibidas,fecha_publicacion,fecha_relevamiento,contacto,notas
"Automatizar reportes de ventas con n8n y Google Sheets","Cliente sin nombre","https://www.workana.com/job/automatizar-reportes-n8n","workana","freelance","remoto","","",150,300,"USD","proyecto",5,"n8n | google sheets | api rest","Experiencia previa con n8n","es","si",4,4.8,,12,2026-10-18,2026-10-19,"",""
"Data Analyst (Power BI)","Acme Analytics","https://remoteok.com/remote-jobs/123456","remoteok","empleo","remoto","LATAM","junior",1200,1500,"USD","mes",,"power bi | sql | excel","1+ años con Power BI; inglés escrito","en","",,,,,2026-10-17,2026-10-19,"","requiere inglés hablado"
```


## Cómo usarlo

1. Abrí en Chrome las búsquedas o avisos que te interesan (vos, a mano).
2. Pegale este prompt a Claude in Chrome y copiá el bloque CSV que devuelve en un archivo `.csv`
   (o pegalo directo).
3. En Jobly → **Importar**: arrastrá el archivo (o pegá el texto). Las columnas se mapean solas;
   el mapeo queda guardado por fuente.
4. Lo nuevo aparece en la home ordenado por score de oportunidad (★). Si te equivocaste de
   lote, **Deshacer** en el historial lo borra (salvo lo que ya postulaste).
