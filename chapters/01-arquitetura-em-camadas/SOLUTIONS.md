# Soluções — Capítulo 1

Tentou antes de abrir? Então vamos. Cada solução segue o mesmo caminho: **o sintoma → o diagnóstico → o conserto → a moral**. O raciocínio vale mais que o código final.

---

## Bloco 1a — o schema que vaza

**O sintoma.** `test_saida_de_usuario_nao_vaza_campos_internos` falha: o JSON do `POST /users` traz `"internal_note": ""`.

**O diagnóstico.** Que camada acusa? A resposta da API está errada, então o suspeito é quem monta a resposta: o schema de saída. Abra `app/schemas/user.py`:

```python
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    internal_note: str
```

Alguém "espelhou o model por conveniência" — se o model tem o campo, o schema também tem. E o `response_model=UserOut`, que é um **filtro** (lição 04), deixou passar porque o campo está declarado no contrato. O filtro funcionou perfeitamente; o contrato é que estava errado.

**O conserto.** Remova `internal_note: str` do `UserOut`. Só isso.

```python
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
```

E o model? **Pode manter a coluna.** O teste continua verde com `internal_note` no banco — rode e confira. A nota interna pode ser útil para o time; o problema nunca foi ela existir, foi ela *sair na API*.

**A moral.** Model é o formato interno; schema de saída é o **contrato público**. São documentos diferentes com donos diferentes — quando um espelha o outro "por conveniência", todo campo novo do banco nasce público por padrão. A lição 04 avisou: *um dia um campo interno vai tentar escapar*. Foi hoje.

---

## Bloco 1b — a fronteira errada

**O sintoma.** `test_reservas_encostadas_nao_conflitam` falha: reservar 12:00–14:00 depois de 10:00–12:00 devolve 409, mas deveria dar 201.

**O diagnóstico.** Quem decide conflito é o service (lição 09). No `create` do arquivo quebrado:

```python
overlapping = [
    b
    for b in self.bookings.list_all()
    if b.resource_id == data.resource_id
    and b.starts_at <= data.ends_at
    and b.ends_at >= data.starts_at
]
```

O teste acusa os operadores: `<=` e `>=`. Com eles, a reserva que termina *exatamente* quando a outra começa conta como sobreposição. A regra do FairFare (lição 09) usa comparação **estrita**: encostar não é sobrepor.

**O conserto.** Jogue a lista fora e volte a chamar quem sempre soube fazer isso:

```python
overlapping = self.bookings.find_overlapping(data.resource_id, data.starts_at, data.ends_at)
```

O `find_overlapping` do repositório já tem os operadores certos (`<` e `>`).

**A moral — e o segundo bug.** Repare que o código quebrado tinha **dois** problemas, e o teste só acusa um. O outro está no `list_all()`: ele traz **todas as reservas do banco** para a memória e filtra em Python. Com 50 reservas, ninguém nota; com 500 mil (todas as quadras, todos os tempos), cada `POST /bookings` arrasta a tabela inteira pela rede para descartar 99,9% dela. O banco filtra com índice, no lugar onde o dado mora; é o trabalho dele. Esse é um **bug adormecido**: nenhum teste funcional o pega, porque o *resultado* é igual — só o custo explode, e mais tarde. Fronteira certa (a query no repositório) e operador certo são dois cuidados diferentes; o estagiário errou os dois de uma vez.

---

## Bloco 1c — status codes mentirosos

**O sintoma.** Dois testes: `test_recurso_inexistente_e_404` recebe 200, e `test_recurso_sem_tipo_e_422` explode com `KeyError: 'tipo'` — a versão de teste do 500 que o cliente veria.

**O diagnóstico.** O router "simplificado" perdeu as duas proteções da borda:

```python
@router.post("", status_code=201)
def create_resource(resource: dict, db: Session = Depends(get_db)):
    created = ResourceRepository(db).create(nome=resource["nome"], tipo=resource["tipo"])
    return created


@router.get("/{resource_id}")
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    return ResourceRepository(db).get(resource_id)
```

`resource: dict` é a promessa vazia da lição 03 de volta: sem schema, um payload sem `tipo` passa pela porta e explode lá dentro (`KeyError` → 500, família "o erro é meu", quando o erro era do cliente — status mentiroso). E o GET devolve o que o repositório mandar: `None` vira `200` com corpo `null` — "funcionou!" para uma coisa que não existe.

**O conserto.** Schema na entrada, 404 explícito na saída:

```python
@router.post("", status_code=201, response_model=ResourceOut)
def create_resource(resource: ResourceCreate, db: Session = Depends(get_db)):
    return ResourceRepository(db).create(nome=resource.nome, tipo=resource.tipo)


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = ResourceRepository(db).get(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="recurso não existe")
    return resource
```

(É o router oficial — compare com `app/routers/users.py`, que era a dica.)

**A moral.** O router tem exatamente dois empregos: validar a forma na entrada e dizer a verdade na saída. O capítulo 0 insistiu que status codes apontam o culpado; um 200 para o que não existe e um 500 para payload torto mentem duas vezes.

---

## Bloco 2 — o recurso ganha capacidade

**O caminho, de baixo para cima.**

**1. O model** (`app/models/resource.py`):

```python
class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    tipo: Mapped[str] = mapped_column(server_default="quadra")
    capacity: Mapped[int | None]
```

`Mapped[int | None]` — o `| None` faz a coluna nascer `nullable`. Sem `mapped_column` extra: não há default a declarar, nulo já é o padrão.

**2. A migração.** `uv run alembic revision --autogenerate -m "recurso ganha capacidade"`, e o rascunho sai:

```python
op.add_column('resources', sa.Column('capacity', sa.Integer(), nullable=True))
```

E a pergunta do enunciado: **por que sem `server_default`, se o `tipo` da lição 07 precisou?** Porque o `tipo` era `NOT NULL`: as linhas antigas *precisavam* de um valor, senão o banco recusava. `capacity` é nullable — as linhas antigas ficam com `NULL`, que é exatamente a semântica que queremos ("não declarou"). Coluna opcional dispensa resposta para o passado.

**3. Os schemas** (`app/schemas/resource.py`):

```python
class ResourceCreate(BaseModel):
    nome: str
    tipo: str
    capacity: int | None = None


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    tipo: str
    capacity: int | None
```

No `Create`, o `= None` torna o campo **opcional na request**. No `Out`, sem default: o campo sempre sai (com `null` quando não há valor) — contrato explícito.

**4. O caminho do dado.** A pegadinha do exercício: schema e model prontos, testes ainda vermelhos. O `capacity` chegava na porta e morria lá, porque ninguém o passava adiante:

```python
# app/repositories/resource.py
def create(self, nome: str, tipo: str, capacity: int | None = None) -> Resource:
    resource = Resource(nome=nome, tipo=tipo, capacity=capacity)
    ...

# app/routers/resources.py
return ResourceRepository(db).create(
    nome=resource.nome, tipo=resource.tipo, capacity=resource.capacity
)
```

**A moral.** Uma feature "de um campo só" atravessou quatro arquivos — model, migração, schema, router/repositório — e cada um tinha uma decisão própria (nullable? default? opcional na entrada?). É o preço das camadas: mais lugares para tocar, cada lugar com uma responsabilidade só. O mapa da lição 10 diz a ordem; você nunca fica perdido, só dá alguns passos a mais.

*(Nota: este exercício fica na sua branch. O `capacity` não entra no app oficial — entra quando algum capítulo precisar dele.)*

---

## Bloco 3 — o pastelão vira camadas

**O ponto de partida.** Tudo verde, inclusive o pastelão — e é isso que torna o exercício realista: refatorar não é consertar o quebrado, é melhorar o que funciona *sem quebrá-lo*.

**Onde cada pedaço foi morar.** O DELETE do freelancer fazia quatro coisas; o mapa da lição 10 diz o endereço de cada uma:

| No pastelão | O quê | Vai para |
|---|---|---|
| `SELECT ... WHERE id = :id` com `text()` | buscar a reserva | `BookingRepository.get` (já existia!) |
| `DELETE FROM bookings ...` | apagar | `BookingRepository.delete` (novo) |
| `if starts_at <= datetime.now()` | regra "só futuras" | `BookingService.cancel` (novo) |
| os dois `HTTPException` | tradução para HTTP | fica no router |

**O repositório** ganha o verbo que faltava:

```python
def delete(self, booking: Booking) -> None:
    self.db.delete(booking)
    self.db.commit()
```

**O service** ganha o `cancel` — e duas exceções de domínio novas, porque o service grita em português (lição 09):

```python
class BookingNotFoundError(Exception):
    pass


class BookingInPastError(Exception):
    pass
```

```python
def cancel(self, booking_id: int) -> None:
    booking = self.bookings.get(booking_id)
    if booking is None:
        raise BookingNotFoundError
    if booking.starts_at <= datetime.now():
        raise BookingInPastError
    self.bookings.delete(booking)
```

Repare no que sumiu junto: o `datetime.fromisoformat(str(row[0]))` do pastelão. Ele existia porque o SQL cru devolve o dado *cru* (string) — indo pelo model, `booking.starts_at` já é `datetime`. Uma conversão manual a menos é um bug futuro a menos.

**O router** vira só tradução, o mesmo padrão do POST:

```python
@router.delete("/{booking_id}", status_code=204)
def cancel_booking(booking_id: int, db: Session = Depends(get_db)):
    try:
        BookingService(db).cancel(booking_id)
    except BookingNotFoundError:
        raise HTTPException(status_code=404, detail="reserva não existe")
    except BookingInPastError:
        raise HTTPException(status_code=409, detail="só reservas futuras podem ser canceladas")
```

(Não esqueça de reexportar as exceções novas em `app/services/__init__.py`.)

**A moral.** O pastelão e a versão em camadas têm o **mesmo comportamento** — os testes provam. A diferença é o futuro: no pastelão, a regra "só futuras" era invisível para qualquer código que não fosse a rota (um job de limpeza do capítulo 8 teria que copiá-la); em camadas, `BookingService.cancel` é a regra, chamável de qualquer lugar. Você fez em 20 minutos, com rede, o que o capítulo inteiro fez em 11 lições: essa experiência — mover sem medo porque o verde vigia — é a habilidade que o curso quer instalar.

*(Este exercício, ao contrário do bloco 2, **entra no app oficial** — o cancelamento é útil demais para ficar só na sua branch. Veja o commit seguinte do capítulo: é a solução acima, com os 3 testes incorporados ao smoke test.)*
