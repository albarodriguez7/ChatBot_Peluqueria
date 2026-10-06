"""
Cliente verificado de cada conversación.

El modelo NUNCA decide con qué cliente se actúa: el id_cliente se guarda aquí
cuando buscar_cliente / registrar_cliente lo identifican, y las demás
herramientas lo leen de aquí. Así, aunque alguien intente manipular al modelo
("cancela la cita 3 del cliente 3"), solo se puede actuar sobre el cliente
identificado en esa conversación.

Se guarda en memoria, igual que el InMemorySaver: si se reinicia la app,
se pierde la conversación y también esta identificación.
"""

_CLIENTES_POR_CONVERSACION = {}


def _thread_id(config):
    return ((config or {}).get("configurable") or {}).get("thread_id")


def guardar_cliente(config, id_cliente):
    thread_id = _thread_id(config)

    if thread_id is None:
        raise RuntimeError("No hay thread_id en la configuración de la conversación.")

    _CLIENTES_POR_CONVERSACION[thread_id] = int(id_cliente)


def cliente_actual(config):
    return _CLIENTES_POR_CONVERSACION.get(_thread_id(config))


def olvidar(thread_id):
    _CLIENTES_POR_CONVERSACION.pop(thread_id, None)
