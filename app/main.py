from fastapi import FastAPI, HTTPException

app = FastAPI(title="FairFare")

users: dict[int, dict] = {}
_next_id = 1


@app.post("/users", status_code=201)
def create_user(user: dict):
    global _next_id
    user = {"id": _next_id, **user}
    users[_next_id] = user
    _next_id += 1
    return user


@app.get("/users")
def list_users():
    return list(users.values())


@app.get("/users/{user_id}")
def get_user(user_id: int):
    if user_id not in users:
        raise HTTPException(status_code=404, detail="usuário não existe")
    return users[user_id]
