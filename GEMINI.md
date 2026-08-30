# 🏛️ Reglas Fundamentales de Ingeniería y Desarrollo (Leyes Universales de José Luis Villaronga)

Estas tres leyes son principios arquitectónicos y de ingeniería de software de máxima prioridad para todo agente de IA (**Antigravity**) que trabaje con este usuario, aplicables de forma universal a cualquier proyecto, módulo o servicio:

---

### Ley 1: Modularización Estricta y Separación de Responsabilidades desde el Día Cero
> *Si un servicio, microservicio o componente previsiblemente va a crecer o evolucionar, debe implementarse con modularización estricta, alta cohesión y bajo acoplamiento desde el inicio.*

* **Prohibición:** Nunca construir o expandir archivos monolíticos que mezclen múltiples dominios (seguridad, proxying, herramientas, telemetría, bases de datos).
* **Mandato:** Separar la lógica en submódulos especializados con responsabilidades únicas y contratos de interfaz claros. Cada componente debe poder ser probado, refactorizado o reemplazado de manera aislada sin poner en riesgo el resto del sistema ni provocar fallos catastróficos en cadena.

---

### Ley 2: Atacar Causas Raíz cuando el Riesgo de Fallo en Cadena es Bajo
> *Al implementar soluciones, correcciones o fixes, evaluar la complejidad y el radio de impacto del código: si el riesgo de generar errores en cadena es bajo, siempre se debe atacar la causa raíz estructural en lugar de aplicar parches superficiales o redundantes.*

* **Prohibición:** Evitar "parches rápidos" o funciones utilitarias duplicadas que oculten problemas de diseño o configuración fundamental.
* **Mandato:** Identificar el origen primario del problema (ej. inicialización de entorno, carga determinista de configuraciones, tipos de datos, contratos de API) y resolverlo a nivel de arquitectura, manteniendo el código limpio, canónico y libre de deuda técnica.

---

### Ley 3: El Principio del Mínimo Cambio Posible (Navaja de Ockham en Software)
> *Si una tarea o corrección puede realizarse de dos o más maneras, la manera correcta es siempre aquella que se logre con el mínimo cambio posible (mínimo blast radius).*

* **Prohibición:** No reescribir código innecesariamente, no introducir sobre-ingeniería ni alterar partes que ya funcionan de forma estable por meras preferencias estilísticas.
* **Mandato:** Realizar intervenciones quirúrgicas, directas, elegantes y verificables. Preservar intacta la funcionalidad existente, minimizando el diff de cambios para facilitar auditorías de código, pruebas de regresión y rollbacks limpios.
