# Studio Alba — asistente de reservas

Agente de IA (LangChain + LangGraph) que atiende a los clientes de una peluquería en Madrid:
consulta servicios y horarios, y reserva, modifica o cancela citas. Frontend en Streamlit.

> Proyecto de demostración: el negocio y todos los datos (clientes, citas, ventas) son inventados.

## Qué incluye

- **Agente con herramientas** (LangChain + LangGraph): reserva, modifica y cancela citas llamando a funciones reales.
- **RAG** con Chroma y embeddings de OpenAI para responder dudas sobre el negocio a partir de `documentos_negocio/negocio.txt`.
- **Reservas en SQLite** con transacciones atómicas y huecos libres según la duración de cada servicio.
- **Tres aplicaciones en Streamlit**: chat para clientes, agenda para el personal y panel de negocio para la propietaria.
- **Google Calendar** como espejo de la agenda de cada profesional.
- **Tests** con pytest y trazas opcionales con LangSmith.

## Tecnologías

Python · LangChain · LangGraph · OpenAI · Chroma · SQLite · Streamlit · Google Calendar API · pandas · pytest · Poetry

## Cómo funciona

```text
Streamlit (app/frontend_cliente.py)
        │  thread_id por conversación
        ▼
Agente (app/agent.py) ── prompt dinámico con la fecha de hoy (Europe/Madrid)
   │            │
   │            └── RAG (app/rag.py, Chroma) → información del negocio
   ▼
Herramientas (app/tools/reservas_tools.py)
   │   el cliente identificado lo fija el código (reservas/sesion.py), no el modelo
   ▼
Lógica de reservas (app/reservas/)
   config.py          horario, zona horaria y rutas: única fuente de verdad
   disponibilidad.py  huecos libres por profesional
   db.py              SQLite: clientes y citas, con transacciones atómicas
   citas.py           crear / modificar / cancelar
   clientes.py        el teléfono identifica al cliente
        ▼
datos_negocio/studio_alba.db   clientes y citas (SQLite)
datos_negocio/*.csv            servicios, empleados y contabilidad
```

## Agenda para el personal

```powershell
poetry run streamlit run app/panel_empleadas.py --server.port 8502
```

Añade `PANEL_PIN=...` al `.env` (sin PIN el panel no se abre). Desde ahí las empleadas ven el día de cada
profesional, apuntan citas de teléfono o de tienda, cancelan citas y bloquean huecos. El asistente deja de
ofrecer esos huecos al instante, porque todo va a la misma base de datos.

## Panel de la propietaria

```powershell
poetry run streamlit run app/panel_propietaria.py --server.port 8503
```

Añade `OWNER_PIN=...` al `.env` (distinto de `PANEL_PIN`: aquí se ven ingresos, costes y nóminas).
Pestañas: Resumen, Ingresos, Costes, Clientes, Agenda y Marketing (recuperar clientes por WhatsApp,
coste por cliente nuevo, servicios más rentables por hora y franjas flojas).

Diseño: menú lateral verde oscuro, tarjetas blancas redondeadas, selector de periodo en píldoras, tipografías
Bodoni Moda y Manrope (se cargan de Google Fonts: sin internet se usan tipografías del sistema). El color principal de
todas las apps de Streamlit se define en `.streamlit/config.toml`.

Criterios: costes = gastos + compras a proveedores + nóminas (repartidas por días); ingresos y visitas salen de
`ventas.csv`; ocupación y mapa de horas, de las citas. Clientes «en riesgo» = más de 60 días sin venir;
«perdidos» = más de 120.

### Datos de demostración

`ventas.csv`, `gastos.csv` y `compras.csv` de ejemplo solo cubren un mes. Para enseñar el panel con historial:

```powershell
poetry run python app/generar_datos_demo.py
```

Genera 6 meses (clientes con teléfonos `000...` que no existen, ventas, gastos, compras y las citas pasadas
correspondientes). Antes hace una copia de seguridad en `datos_negocio/backup_<fecha>/`.

## Google Calendar

Cada profesional ve en su calendario de Google las citas y los bloqueos de la base de datos (próximos 90 días).
Es un espejo de solo lectura: lo que se escriba a mano en Google Calendar no llega a la base de datos ni bloquea
huecos; para apuntar o bloquear se usa el panel del personal.

1. Las librerías de Google ya vienen en `pyproject.toml` (se instalan con `poetry install`).
2. Crea una cuenta de servicio en Google Cloud, descarga su clave JSON en `credenciales/` (esa carpeta no se
   sube a GitHub) y comparte un calendario por profesional con el correo de la cuenta de servicio.
3. Rellena en el `.env`: `GOOGLE_SERVICE_ACCOUNT_FILE` y un `GCAL_EMPLEADO_<id>` por profesional
   (`id` es el `id_empleado` de `empleados.csv`).
4. Comprueba el acceso: `poetry run python app/sincronizar_calendario.py --comprobar`
5. Primera carga: `poetry run python app/sincronizar_calendario.py`

Después la aplicación sincroniza sola en segundo plano tras cada reserva, cambio o bloqueo. Si Google falla,
la reserva se guarda igual y el siguiente cambio (o el botón «Sincronizar ahora» del panel) lo pone al día.
Solo se tocan los eventos creados por la aplicación; los que las empleadas creen por su cuenta se respetan.

## Instalación

```powershell
poetry install
copy .env.example .env   # y rellena tu OPENAI_API_KEY y los PIN de los paneles
poetry run streamlit run app/frontend_cliente.py
```

## Tests

```powershell
poetry run pytest
```

Los tests trabajan sobre una copia temporal de `datos_negocio/`: nunca modifican los datos reales.

## Limitaciones conocidas

- `servicios.csv`, `empleados.csv` y la contabilidad siguen en CSV: los edita la propietaria y la app solo los lee.
- La primera ejecución crea `studio_alba.db` importando `clientes.csv` y `citas.csv`. Después esos dos CSV ya no se usan.
- Las citas de clientes inexistentes no se importan: quedan en `citas_huerfanas.csv` para revisarlas.
- La memoria de la conversación (`InMemorySaver`) y el cliente identificado se pierden al reiniciar.
- El teléfono identifica al cliente sin verificarlo: quien conozca un teléfono puede ver o cancelar sus citas.
  Antes de producción, verificar con un código por SMS o WhatsApp.
