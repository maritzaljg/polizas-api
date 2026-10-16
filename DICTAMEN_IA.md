# Dictamen sobre `ia_tests_propuesta.py` — Parte D

**Grupo:** individual · **Integrante:** Maritza Liliana Jiménez Gómez

La batería propuesta por el asistente **está en verde**: `6 passed` sobre el servicio
original y `6 passed` sobre el corregido. Pasa igual contra un servicio roto que contra
uno sano, que es precisamente el problema. Los tres defectos están abajo, cada uno con
la mutación que lo demuestra y las dos salidas de `pytest`.

La batería corregida está en `tests/test_ia_corregido.py` y da `17 passed` sobre el
servicio sano, dos veces seguidas y sin tocar la base de datos de la aplicación.

## Defecto 1

- **Qué está mal:** el aislamiento que la batería declara en su propio comentario —«las pruebas nunca escriben en la base de datos de la aplicación»— no se aplica nunca. Define una función local llamada `get_db` y la registra como `app.dependency_overrides[get_db]`, pero la aplicación depende de `database.get_db`, que es **otro objeto distinto con el mismo nombre**. FastAPI busca esa clave por identidad, no por nombre, así que el reemplazo no sustituye nada y las pruebas trabajan contra la base real del servicio. Como agravante, el doble es un `MagicMock`, que habría aceptado en silencio cualquier llamada si el reemplazo hubiera funcionado.
- **Por qué es un defecto** (módulo · sección): M8 · 4. Inyección de dependencias con Depends — el reemplazo de una dependencia se registra contra el objeto que la aplicación declara en `Depends`; una función homónima definida en el archivo de pruebas no ocupa su lugar.
- **Cómo lo comprobamos:** este defecto no necesita mutar el servicio, porque el daño se mide en la base de datos. Se tomó la huella de `app.db` y el número de pólizas antes y después de correr la batería. La batería original la dejó con siete pólizas más; la corregida la dejó byte por byte idéntica.

```diff
# El reemplazo, antes y después
- def get_db():
-     yield MagicMock()
- app.dependency_overrides[get_db] = get_db          # clave: función local
+ import database
+ app.dependency_overrides[database.get_db] = _sesion_de_prueba   # la dependencia real
```

```
# ia_tests_propuesta.py: en verde, y la base REAL cambia
app.db antes:    eaf835f0dc0df373   ·  38 pólizas
6 passed, 1 warning in 4.80s
app.db después:  ab088b39518bdc30   ·  45 pólizas
```

```
# tests/test_ia_corregido.py: en verde, y la base REAL intacta
app.db antes:    eaf835f0dc0df373
17 passed, 1 warning in 4.68s
app.db después:  eaf835f0dc0df373
```

- **Corrección:** se sustituye `database.get_db`, que es la dependencia que la aplicación declara, por una sesión sobre una base temporal propia, instalada con una *fixture* `autouse` que la pone antes de cada prueba y la retira al terminar.

## Defecto 2

- **Qué está mal:** varias afirmaciones aceptan a la vez el resultado correcto y el incorrecto, de modo que no pueden fallar. `assert r.status_code in (200, 201, 422)` da por buena tanto una creación exitosa como su rechazo por datos inválidos. `assert r.status_code in (200, 404)` al pedir una póliza inexistente acepta el 404 correcto y también el 200 con el error en el cuerpo, que es justamente el defecto H8 del servicio original. `assert r.status_code < 500` solo falla si el servidor revienta. Y `assert "puntaje" in r.json() or "error" in r.json()` acepta que la puntuación no se haya podido calcular.
- **Por qué es un defecto** (módulo · sección): M10 · 4. Framework pytest — una afirmación describe el resultado esperado; si admite varios resultados contradictorios, la prueba deja de distinguir entre un servicio que funciona y uno que no.
- **Cómo lo comprobamos:** primero se midió que el mismo test pasa contra comportamientos opuestos: el servicio original responde **200** al pedir una póliza inexistente y el corregido responde **404**, y `test_consultar_poliza_inexistente` da `1 passed` en los dos casos. Después se mutó el servicio corregido para que dejara de devolver el 404.

```diff
# main.py, en obtener_poliza: el 404 deja de devolverse
-        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
+        raise HTTPException(status_code=status.HTTP_200_OK,
                             detail=f"no existe la póliza {id_poliza}")
```

```
# ia_tests_propuesta.py sobre el servicio mutado: ni se entera
6 passed, 1 warning in 5.24s
```

```
# tests/test_ia_corregido.py sobre el servicio mutado
FAILED tests/test_ia_corregido.py::test_consultar_poliza_inexistente_da_404
1 failed, 16 passed, 1 warning in 5.57s
```

- **Corrección:** cada afirmación exige un único resultado: `== 201` al crear, `== 404` al consultar lo que no existe, `== 409` ante un número repetido y `== 422` ante cada entrada inválida. Y donde la prueba decía «no falla», ahora comprueba el contenido: que la póliza creada aparezca en el listado, que el resumen traiga el conteo y la suma exactos, y que la predicción quede registrada con el número de su póliza.

## Defecto 3

- **Qué está mal:** los datos de cada prueba se sortean con `random.choice` para el tipo y `random.uniform` para la prima, sin fijar una semilla. Cada corrida prueba un caso distinto, así que el resultado no es reproducible: un fallo no se puede volver a ver, y por tanto no se puede diagnosticar ni confirmar que quedó arreglado. El comentario del archivo lo presenta como una virtud —«datos variados, para no probar siempre el mismo caso»— cuando lo que produce es que no se sepa qué caso se probó.
- **Por qué es un defecto** (módulo · sección): M10 · 7. Reproducibilidad sin Docker — una prueba cuyo resultado depende del azar no es reproducible, y sin reproducibilidad el informe de un fallo no sirve para nada.
- **Cómo lo comprobamos:** se introdujo en el servicio un fallo que afecta **solo a uno de los tres tipos de póliza** que la batería sortea, y se corrió seis veces. Con el mismo defecto presente, informó cuatro resultados distintos. La batería corregida, ante exactamente la misma mutación, informa siempre lo mismo y además nombra el caso que falló.

```diff
# main.py, en crear_poliza: solo las pólizas de tipo "vida" fallan
+    if datos.tipo == "vida":          # MUTACION temporal
+        raise RuntimeError("fallo al crear polizas de vida")
     poliza = Poliza(
         numero=datos.numero,
```

```
# ia_tests_propuesta.py, seis corridas con la MISMA mutación
corrida 1: 1 failed, 5 passed
corrida 2: 1 failed, 5 passed
corrida 3: 3 failed, 3 passed
corrida 4: 1 failed, 5 passed
corrida 5: 2 failed, 4 passed
corrida 6: 1 failed, 5 passed
```

```
# tests/test_ia_corregido.py, cuatro corridas con la MISMA mutación
corrida 1: 1 failed, 16 passed
corrida 2: 1 failed, 16 passed
corrida 3: 1 failed, 16 passed
corrida 4: 1 failed, 16 passed
FAILED tests/test_ia_corregido.py::test_cada_tipo_de_poliza_se_crea_igual[vida-4750000]
```

- **Corrección:** los datos pasan a ser fijos y explícitos, y la variedad se consigue **enumerando** los casos con `pytest.mark.parametrize` en vez de sorteándolos. Los tres tipos de póliza se prueban los tres, siempre, y el nombre del caso que falla aparece en la salida.

---

## Comprobación adicional: las tres roturas que anuncia el enunciado

El enunciado advierte que el calificador prueba la batería corregida contra tres
mutaciones que el grupo no ve: «un 404 que deja de devolverse, un `commit` que se
quita, un validador que acepta lo que no debe». Se hicieron las tres.

| Rotura introducida | `ia_tests_propuesta.py` | `tests/test_ia_corregido.py` |
|---|---|---|
| El 404 de consultar una póliza deja de devolverse | `6 passed` — no la detecta | `1 failed` — falla el test que corresponde |
| Se reemplaza el `commit` de la creación por un `flush` | `1 failed` — la detecta de rebote | `5 failed` |
| El validador de fechas acepta una vigencia invertida | `6 passed` — no la detecta | `1 failed` — falla el caso «fechas invertidas» |

En las tres, el servicio se devolvió a su estado original y la batería completa del
repositorio volvió a `37 passed, 1 xfailed`.
