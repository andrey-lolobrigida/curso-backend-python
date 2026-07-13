"""O mini-servidor do capítulo 0.

Você NÃO precisa entender este código ainda. Sério. Ele existe só para você
ter alguém do outro lado da linha para conversar em HTTP. No capítulo 1,
você começa a escrever o seu — e aí este arquivo vai parecer bem menos mágico.

Rode com:

    python server.py

e ele escuta em http://localhost:8000 até você apertar Ctrl+C.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

QUADRAS = [
    {"id": 1, "nome": "Quadra Central", "esporte": "tenis", "preco_hora": 80},
    {"id": 2, "nome": "Ginasio Azul", "esporte": "basquete", "preco_hora": 120},
    {"id": 3, "nome": "Saibro do Fundo", "esporte": "tenis", "preco_hora": 60},
]

# Reservas vivem só na memória: reiniciou o servidor, zerou tudo.
RESERVAS = []

SENHA = "clube-do-backend"

# Rotas que existem e os métodos que cada uma aceita (para responder 405
# com o header Allow quando o método não for suportado).
METODOS_POR_ROTA = {
    "/quadras": ["GET"],
    "/reservas": ["GET", "POST"],
    "/antigo": ["GET"],
    "/segredo": ["GET"],
    "/cha": ["GET"],
}


class Handler(BaseHTTPRequestHandler):
    server_version = "MiniServidorCap00/0.1"
    # Sem esta linha, a stdlib responde como HTTP/1.0, que fecha a conexão
    # a cada request. HTTP/1.1 mantém a conexão aberta — exige que toda
    # resposta declare seu Content-Length (nós declaramos).
    protocol_version = "HTTP/1.1"

    # ---------- utilitários ----------

    def _json(self, status, dados, headers_extras=None):
        corpo = json.dumps(dados, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        for nome, valor in (headers_extras or {}).items():
            self.send_header(nome, valor)
        self.end_headers()
        self.wfile.write(corpo)

    def _sem_corpo(self, status, headers_extras=None):
        self.send_response(status)
        for nome, valor in (headers_extras or {}).items():
            self.send_header(nome, valor)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _rota(self):
        partes = urlparse(self.path)
        return partes.path.rstrip("/") or "/", parse_qs(partes.query)

    def _405_ou_404(self, caminho):
        base = "/" + caminho.split("/")[1] if caminho != "/" else "/"
        if base in METODOS_POR_ROTA:
            permitidos = METODOS_POR_ROTA[base]
            self._json(
                405,
                {"erro": f"{self.command} nao e permitido em {caminho}"},
                {"Allow": ", ".join(permitidos)},
            )
        else:
            self._json(404, {"erro": f"nao existe nada em {caminho}"})

    # ---------- GET ----------

    def do_GET(self):
        caminho, query = self._rota()

        if caminho == "/quadras":
            quadras = QUADRAS
            if "esporte" in query:
                quadras = [q for q in quadras if q["esporte"] == query["esporte"][0]]
            self._json(200, quadras)

        elif caminho.startswith("/quadras/"):
            quadra = self._acha(QUADRAS, caminho.removeprefix("/quadras/"))
            if quadra is None:
                self._json(404, {"erro": "quadra nao encontrada"})
            else:
                self._json(200, quadra)

        elif caminho == "/reservas":
            self._json(200, RESERVAS)

        elif caminho == "/antigo":
            self._sem_corpo(301, {"Location": "/quadras"})

        elif caminho == "/segredo":
            if self.headers.get("X-Senha") == SENHA:
                self._json(200, {"segredo": "voce leu os headers. e exatamente assim que se faz."})
            else:
                self._json(
                    401,
                    {"erro": "faltou o header X-Senha (ou a senha esta errada)"},
                    {"X-Dica": f"a senha e {SENHA}"},
                )

        elif caminho == "/cha":
            self._json(418, {"erro": "sou um bule de cha, nao faco cafe"})

        else:
            self._405_ou_404(caminho)

    # ---------- POST ----------

    def do_POST(self):
        caminho, _ = self._rota()

        if caminho != "/reservas":
            self._405_ou_404(caminho)
            return

        tipo = self.headers.get("Content-Type", "")
        if not tipo.startswith("application/json"):
            self._json(415, {"erro": "mande Content-Type: application/json"})
            return

        tamanho = int(self.headers.get("Content-Length", 0))
        bruto = self.rfile.read(tamanho)
        try:
            dados = json.loads(bruto)
        except json.JSONDecodeError:
            self._json(400, {"erro": "o corpo nao e JSON valido"})
            return

        if not isinstance(dados, dict) or "quadra_id" not in dados or "quem" not in dados:
            self._json(400, {"erro": "o corpo precisa ter quadra_id e quem"})
            return

        if self._acha(QUADRAS, str(dados["quadra_id"])) is None:
            self._json(404, {"erro": f"quadra {dados['quadra_id']} nao existe"})
            return

        reserva = {"id": len(RESERVAS) + 1, "quadra_id": dados["quadra_id"], "quem": dados["quem"]}
        RESERVAS.append(reserva)
        self._json(201, reserva, {"Location": f"/reservas/{reserva['id']}"})

    # ---------- DELETE ----------

    def do_DELETE(self):
        caminho, _ = self._rota()

        if caminho.startswith("/reservas/"):
            reserva = self._acha(RESERVAS, caminho.removeprefix("/reservas/"))
            if reserva is None:
                self._json(404, {"erro": "reserva nao encontrada"})
            else:
                RESERVAS.remove(reserva)
                self._sem_corpo(204)
        else:
            self._405_ou_404(caminho)

    # ---------- os métodos que ainda não sabemos usar ----------

    def do_PUT(self):
        self._405_ou_404(self._rota()[0])

    def do_PATCH(self):
        self._405_ou_404(self._rota()[0])

    # ---------- mais utilitários ----------

    @staticmethod
    def _acha(itens, id_texto):
        if not id_texto.isdigit():
            return None
        alvo = int(id_texto)
        for item in itens:
            if item["id"] == alvo:
                return item
        return None

    def log_message(self, formato, *args):
        # Log enxuto: método, caminho, status.
        print(f"{self.command} {self.path} -> {args[1]}")


if __name__ == "__main__":
    servidor = HTTPServer(("127.0.0.1", 8000), Handler)
    print("Mini-servidor no ar em http://localhost:8000 — Ctrl+C para parar.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nAté a próxima.")
