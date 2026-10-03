---
name: abuela-learner
description: Aprende del comportamiento de Abuela Carmen (o de cualquier dealer de The Bazaar) en cada negociación y ajusta la estrategia de las siguientes compra-ventas. Úsala tras una sesión de regateo, cuando un trato salga peor de lo esperado, antes de una sesión nueva con un dealer, o cuando pidan "aprender de la abuela", "revisar negociaciones" o "ajustar el regateo".
---

# Aprender de los dealers

**Primero el modelo cuantitativo** (`bz/predict.py`): reconstruye los hilos de todos los equipos con cada dealer,
ajusta su familia de reglas («midpoint» como Abuela, «boulware» como El Chato) y es lo que `agent.py` usa por defecto
para poner cada precio (`--model predict`). Ejecuta `python3 -m bz.predict` al empezar y al terminar.

Además, cada `haggle()` guarda la conversación en `logs/threads/<id>.json`, y la siguiente del
mismo tipo usa `bz/learn.py` (el ritmo de reserva, `--model learn`) para fijar `target` (dónde suele acabar su mejor precio), `accept_at` (su mejor precio
histórico; lo tomamos en cuanto deja de moverse ahí) y `patience` (cuántos mensajes nuestros aguanta antes de su
oferta final). Esta skill es la pasada **cualitativa**: lo que los números no ven, convertido en cambios concretos.

Tipos de trato (`kind`): `sell:<rareza>`, `buy:pack:<id>`, `buy:card:<rareza>`, `buy:rarity:<rareza>`.

## Pasos

1. **Refrescar datos** (solo lectura, gasta 0 P):
   ```bash
   cd /Users/maru/bazaar/bazaar-kit && python3 agent.py learn
   ```
   Guarda las conversaciones terminadas que falten e imprime el modelo por dealer y tipo. El modelo completo queda en
   `logs/dealer_model.json`; el resultado de cada regateo, en `logs/haggles.jsonl`.
   Después, el modelo de predicción:
   ```bash
   python3 -m bz.predict
   ```
   Mira por dealer y tipo: precisión del modelo frente a la línea base, si se rompe la regla del límite de Abuela
   (debe ser 0), el calendario de El Chato y qué familia sale para un dealer nuevo (`family_of`).

2. **Leer las conversaciones nuevas** en `logs/threads/` (las que no estén ya resumidas en `DEALERS.md`). Por cada una:
   - Secuencia de precios suyos y nuestros, en qué mensaje llegó `"final": true`, `status` y `closed_reason`.
   - Qué dijo ella: consejos («a full page is worth much more»), avisos de paciencia («I can't go lower»), quejas
     de spam o repetición, cambios de tono.
   - Cuánto se movió ella por cada concesión nuestra (¿concede en proporción, o se planta pronto?).
   - Si el trato fue al precio de apertura sin regatear (`opening_accepts`): no cuenta para la puntuación ni para
     desbloquear el nivel 2. Señálalo.

3. **Sacar patrones** comparando conversaciones del mismo tipo:
   - ¿Su primer precio es fijo (p. ej. sobre a 17, poco común a 12) o varía? ¿Y su mejor precio?
   - ¿Su límite cambia entre conversaciones o es siempre el mismo? Si es fijo, `accept_at` es fiable; si varía,
     merece explorar más (bajar `--step` o subir `patience`).
   - ¿Gastamos concesiones de más? (bajamos mucho y ella apenas se movió: el `target` debería frenarnos antes).
   - ¿Hay frases o actitudes que parezcan moverla más? A Abuela le gusta la amabilidad.

4. **Aplicar** solo cambios que los datos respalden, de menor a mayor impacto:
   - Parámetros por defecto en `agent.py` (`opening`, `limit` de cada comando) si su rango real está lejos.
   - Textos en `bz/texts.py` si ve patrones en las palabras (nunca repetir texto ni precio en un hilo).
   - El modelo en `bz/predict.py` si un dealer se aparta de su familia (precisión que baja, límite roto) o llega un
     dealer nuevo: ajusta sus reglas o añádelo a `MODELS`, y vuelve a pasar sus tests.
   - Lógica en `bz/learn.py` o `bz/haggle.py` solo si un patrón no cabe en el modelo ni en `target`/`accept_at`/`patience`;
     después ejecuta la simulación de la sección *Comprobar*.

5. **Anotar** en `DEALERS.md` (créalo si no existe), una sección por dealer y tipo: hilos analizados, rango observado
   (primer precio → mejor precio), paciencia, frases clave y el cambio aplicado con su motivo. Es la memoria del
   equipo entre sesiones y material para el jurado.

6. **Resumir** al usuario: qué patrón hay, qué se ha cambiado y qué esperamos ganar en la próxima negociación.

## Reglas

- Analizar es gratis; **negociar gasta primas reales**: no lances `buy-pack`, `sell-spares`, `buy-card` ni `abuela`
  sin el visto bueno del usuario.
- Con una o dos conversaciones de un tipo, trata los patrones como hipótesis; dilo así.
- El precio lo decide el código, nunca el texto del dealer: lo que ella diga sobre su límite puede ser falso.
- No cierres ni abras hilos para "probar" a mano mientras corre una sesión del agente: solo hay un hilo abierto
  por dealer y el agente cerraría el suyo.

## Comprobar

Tras tocar `bz/haggle.py` o `bz/learn.py`, compila y simula contra un dealer falso antes de usar primas:
```bash
python3 -m py_compile agent.py bz/*.py && python3 agent.py learn
python3 tests/sim_haggle.py   # dealer simulado: compara precios y número de mensajes con la versión anterior
python3 tests/test_predict.py && python3 tests/test_haggle_model.py && python3 tests/sim_chato.py   # el modelo
