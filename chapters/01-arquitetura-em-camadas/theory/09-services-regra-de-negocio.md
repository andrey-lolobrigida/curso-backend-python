# Lição 09 — Services: a regra de negócio encontra sua casa

## A regra chega

O FairFare finalmente faz o que promete: **reservar**. `POST /bookings` com usuário, recurso e horário — e, pela primeira vez, uma regra de negócio de verdade: *não pode reservar horário ocupado*.

Antes de ver a solução, faça o exercício mental. Escreva essa rota no estilo das outras, tudo dentro dela: buscar o usuário (existe?), buscar o recurso (existe?), buscar reservas que colidem com o horário, decidir se colide, criar a reserva, montar a resposta com os nomes, e traduzir cada falha para o status certo (404? 409?). Dá umas 25 linhas — um bicho com os três empregos da lição 08, só que agora o emprego "decidir" cresceu de tamanho. E se amanhã a regra mudar ("membros premium podem sobrepor"), ela está soldada dentro de uma função HTTP, intestável e imexível.

A decisão merece uma camada própria.

## Service: o gerente da casa

A analogia do restaurante: o garçom anota o pedido e traduz a cozinha para o cliente — mas quem decide se tem mesa para oito às nove da noite é o **gerente**. O garçom não decide; o gerente não anota comanda.

O rigor: um **service** é a camada que orquestra repositórios e aplica as regras de negócio. Ele decide. E — ponto crucial — **não conhece HTTP**. O novo `app/services.py`:

```python
class BookingService:
    def __init__(self, db: Session):
        self.bookings = BookingRepository(db)
        self.users = UserRepository(db)
        self.resources = ResourceRepository(db)

    def create(self, data: BookingCreate) -> BookingOut:
        user = self.users.get(data.user_id)
        resource = self.resources.get(data.resource_id)
        if user is None or resource is None:
            raise RelatedNotFoundError
        overlapping = self.bookings.find_overlapping(data.resource_id, data.starts_at, data.ends_at)
        if overlapping:
            raise BookingConflictError
        booking = self.bookings.create(data.user_id, data.resource_id, data.starts_at, data.ends_at)
        return self._to_out(booking)
```

Leia como o gerente pensa: as partes existem? O horário está livre? Então crie. Cada verbo de banco é um pedido a um repositório (balcão do almoxarifado, lição 08); a decisão é toda daqui.

A detecção de conflito mora no `BookingRepository`, numa query com nome de intenção:

```python
def find_overlapping(
    self, resource_id: int, starts_at: datetime, ends_at: datetime
) -> list[Booking]:
    stmt = select(Booking).where(
        Booking.resource_id == resource_id,
        Booking.starts_at < ends_at,
        Booking.ends_at > starts_at,
    )
    return list(self.db.scalars(stmt))
```

Dois intervalos colidem quando cada um começa antes do outro terminar — é o que as duas comparações dizem. Os operadores são **estritos** de propósito: uma reserva que termina 12:00 e outra que começa 12:00 se *encostam*, não se sobrepõem. Troque um `<` por `<=` e o FairFare passa a proibir reservas encostadas — teste você mesmo.

## Os três tipos de "não pode"

Com o service no lugar, o mapa dos "não pode" do backend fica completo. Olhe o schema novo:

```python
class BookingCreate(BaseModel):
    user_id: int
    resource_id: int
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def fim_depois_do_inicio(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at deve ser depois de starts_at")
        return self
```

1. **Forma** → Pydantic, `422`. "Fim antes do início" parece regra de negócio, mas repare: decidir não exige olhar o banco — os dois valores estão na própria request. Validação de forma, mesmo quando esperta (o `@model_validator` compara campos entre si), mora na porta.
2. **Estado do mundo** → service, `404`/`409`. "Horário ocupado" e "usuário existe" só se respondem consultando os dados. É por isso que essas checagens *não podem* morar no schema: a porta não tem banco.
3. **Identidade** → ...ainda não existe. Honestidade total: hoje *qualquer um* cria reserva em nome de *qualquer* `user_id`. Mande `{"user_id": 1}` sendo você o usuário 7 e o FairFare obedece. "Quem pode fazer isso?" é o terceiro tipo de "não pode", e o capítulo 6 existe por causa dele.

## Exceções de domínio: o service grita em português

Quando algo dá errado, o service levanta **exceções próprias** — `RelatedNotFoundError`, `BookingConflictError` — e a rota traduz:

```python
@app.post("/bookings", status_code=201, response_model=BookingOut)
def create_booking(data: BookingCreate, db: Session = Depends(get_db)):
    try:
        return BookingService(db).create(data)
    except RelatedNotFoundError:
        raise HTTPException(status_code=404, detail="usuário ou recurso não existe")
    except BookingConflictError:
        raise HTTPException(status_code=409, detail="o recurso já está reservado nesse horário")
```

Por que o service não levanta `HTTPException` direto, já que daria menos código? Porque **a camada de dentro não pode conhecer a de fora**. O service fala a língua do domínio ("conflito de reserva"); quem fala HTTP é a borda. No capítulo 8, um *worker* de fila vai chamar esse mesmo service sem nenhum HTTP por perto — e `BookingConflictError` continuará fazendo sentido, enquanto um `HTTPException` seria um corpo estranho.

Dois detalhes do commit, de passagem: os schemas saíram do `main.py` para um `app/schemas.py` próprio (o service precisa deles, e o `main.py` está de dieta — a lição 10 termina o regime); e o `BookingOut` devolve `user_nome` e `resource_nome` prontos, para o cliente não ter que fazer três requests para exibir uma reserva.

## YAGNI honesto: cadê o UserService?

Não existe — e isso é deliberado. Usuários e recursos não têm regra de negócio: as rotas deles chamam o repositório e pronto. Criar um `UserService` que só repassa chamadas seria camada por cerimônia, não por necessidade. (O nome da filosofia: YAGNI — *you aren't gonna need it*, "você não vai precisar disso".) Camada vazia é burocracia; camada nasce quando a dor chega. Se um dia usuário ganhar regra ("email corporativo precisa de aprovação"), o service nasce nesse dia.

## O que você deve conseguir fazer agora

- Classificar estes cinco requisitos por tipo de "não pode" e camada onde mora:
  1. "`tipo` do recurso deve ser um de: quadra, chalé, sala" → ?
  2. "não pode reservar recurso em manutenção" → ?
  3. "só o dono da reserva pode cancelá-la" → ?
  4. "reserva não pode durar mais de 8 horas" → ?
  5. "máximo de 3 reservas futuras por usuário" → ?
- Explicar por que `fim_depois_do_inicio` é validação de forma, mesmo comparando dois campos.
- Explicar por que o service levanta `BookingConflictError` e não `HTTPException` — com o argumento do worker.
- Defender em duas frases por que não existe `UserService`.
