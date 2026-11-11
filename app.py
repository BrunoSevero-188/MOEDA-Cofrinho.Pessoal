from flask import Flask, render_template, request, jsonify
from google import genai
import json
import os
import socket
import base64
import sqlite3
import threading
from contextlib import contextmanager
from PIL import Image
import io
import qrcode
from functools import wraps
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

MODEL_NAME = "gemini-2.0-flash"
DB_FILE = 'cofrinho.db'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()

# Rate limiting simples em memória
_rate_limit_store = {}
_rate_limit_lock = threading.Lock()
RATE_LIMIT_REQUESTS = 30  # requests
RATE_LIMIT_WINDOW = 60    # seconds


def get_client_ip():
    """Obtém IP do cliente considerando proxies."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


def check_rate_limit(ip: str) -> tuple[bool, int]:
    """Verifica rate limit. Retorna (allowed, remaining)."""
    now = datetime.now()
    with _rate_limit_lock:
        if ip not in _rate_limit_store:
            _rate_limit_store[ip] = []

        # Remove requests antigos
        cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW)
        _rate_limit_store[ip] = [ts for ts in _rate_limit_store[ip] if ts > cutoff]

        if len(_rate_limit_store[ip]) >= RATE_LIMIT_REQUESTS:
            oldest = min(_rate_limit_store[ip])
            retry_after = int((oldest + timedelta(seconds=RATE_LIMIT_WINDOW) - now).total_seconds())
            return False, max(1, retry_after)

        _rate_limit_store[ip].append(now)
        return True, RATE_LIMIT_REQUESTS - len(_rate_limit_store[ip])


def rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = get_client_ip()
        allowed, remaining = check_rate_limit(ip)
        if not allowed:
            return jsonify({
                "total": 0,
                "detalhes": f"Muitas requisições. Tente novamente em {remaining} segundos."
            }), 429
        response = f(*args, **kwargs)
        if isinstance(response, tuple):
            resp, code = response
        else:
            resp, code = response, 200
        if hasattr(resp, 'headers'):
            resp.headers['X-RateLimit-Remaining'] = str(remaining)
        return resp, code
    return decorated


# ==================== DATABASE ====================

DB_LOCK = threading.Lock()

@contextmanager
def get_db():
    """Context manager para conexão SQLite com WAL mode."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        # WAL mode para melhor concorrência
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Inicializa o banco de dados."""
    with DB_LOCK:
        with get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saldo (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    valor REAL NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS historico (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    valor REAL NOT NULL,
                    detalhes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Inicializa saldo se não existir
            conn.execute("INSERT OR IGNORE INTO saldo (id, valor) VALUES (1, 0)")


def get_data():
    """Retorna saldo atual e histórico."""
    with get_db() as conn:
        row = conn.execute("SELECT valor FROM saldo WHERE id = 1").fetchone()
        saldo = row['valor'] if row else 0.0
        historico = conn.execute(
            "SELECT valor, detalhes, created_at FROM historico ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        return {
            "saldo": float(saldo),
            "historico": [
                {"valor": float(h['valor']), "detalhes": h['detalhes'], "data": h['created_at']}
                for h in historico
            ]
        }


def db_add_balance(valor: float, detalhes: str = ""):
    """Adiciona valor ao saldo e registra no histórico."""
    with DB_LOCK:
        with get_db() as conn:
            conn.execute("UPDATE saldo SET valor = valor + ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (valor,))
            conn.execute(
                "INSERT INTO historico (valor, detalhes) VALUES (?, ?)",
                (valor, detalhes)
            )


# ==================== GEMINI ====================

# Few-shot examples para melhorar precisão
FEW_SHOT_EXAMPLES = """
Exemplos de resposta esperada:

Imagem: Uma nota de R$ 100 e duas moedas de R$ 1
{"total": 102.00, "detalhes": "1 nota de R$ 100,00 + 2 moedas de R$ 1,00"}

Imagem: Três notas de R$ 20 e uma moeda de R$ 0,50
{"total": 60.50, "detalhes": "3 notas de R$ 20,00 + 1 moeda de R$ 0,50"}

Imagem: Sem dinheiro visível
{"total": 0.00, "detalhes": "Nenhum dinheiro detectado na imagem"}

Imagem: Nota de R$ 50 parcialmente coberta
{"total": 50.00, "detalhes": "1 nota de R$ 50,00 (parcialmente visível)"}
"""

PROMPT = f"""Você é um contador de dinheiro brasileiro (Real BRL).
Analise a imagem e some TODAS as notas e moedas visíveis.

Regras:
- Identifique notas: R$ 2, 5, 10, 20, 50, 100, 200
- Identifique moedas: R$ 0,05, 0,10, 0,25, 0,50, 1,00
- Some tudo e retorne o total
- Se não houver dinheiro, total = 0
- Seja conservador: só conte o que tem certeza

{FEW_SHOT_EXAMPLES}

Retorne APENAS um JSON válido com aspas duplas:
{{"total": valor_float, "detalhes": "string descritiva"}}"""


def process_image_with_gemini(image_bytes: bytes) -> dict:
    """Processa imagem com Gemini e retorna dict validado."""
    if not GEMINI_API_KEY:
        return {"total": 0.0, "detalhes": "Chave da API Gemini não configurada no servidor."}

    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Redimensiona se muito grande (economia de tokens)
        max_dim = 1024
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[PROMPT, img],
        )

        txt = response.text.strip()
        # Remove markdown code fences se houver
        txt = txt.replace('```json', '').replace('```', '').strip()

        result = json.loads(txt)

        # Validação rigorosa
        total = float(result.get('total', 0))
        detalhes = str(result.get('detalhes', 'Processado com sucesso'))

        if total < 0:
            total = 0.0
            detalhes = "Valor inválido retornado pela IA"

        return {"total": total, "detalhes": detalhes}

    except json.JSONDecodeError:
        return {"total": 0.0, "detalhes": "Resposta da IA em formato inválido. Tente novamente."}
    except Exception as e:
        msg = str(e)
        if "API key not valid" in msg or "API_KEY_INVALID" in msg:
            return {"total": 0.0, "detalhes": "Chave da API inválida. Configure no painel do servidor."}
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            return {
                "total": 0.0,
                "detalhes": "Cota da API esgotada. Gere nova chave em aistudio.google.com/apikey ou aguarde."
            }
        if "PERMISSION_DENIED" in msg:
            return {"total": 0.0, "detalhes": "API Gemini não habilitada. Ative no Google Cloud Console."}
        app.logger.error(f"Erro no Gemini: {e}")
        return {"total": 0.0, "detalhes": "Erro no processamento. Tente novamente."}


# ==================== ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_balance', methods=['GET'])
def get_balance():
    return jsonify(get_data())


@app.route('/process_image', methods=['POST'])
@rate_limit
def process_image():
    if not request.is_json:
        return jsonify({"total": 0, "detalhes": "Content-Type deve ser application/json"}), 400

    data = request.json
    if not data or 'image' not in data:
        return jsonify({"total": 0, "detalhes": "Imagem não fornecida"}), 400

    try:
        # Remove prefixo data:image/...;base64,
        image_data = data['image']
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        img_bytes = base64.b64decode(image_data)
    except Exception:
        return jsonify({"total": 0, "detalhes": "Imagem inválida (base64 malformado)"}), 400

    result = process_image_with_gemini(img_bytes)
    return jsonify(result)


@app.route('/add_balance', methods=['POST'])
@rate_limit
def add_balance():
    if not request.is_json:
        return jsonify({"error": "Content-Type deve ser application/json"}), 400

    data = request.json
    try:
        valor = float(data.get('valor', 0))
        detalhes = str(data.get('detalhes', 'Adição manual'))
    except (ValueError, TypeError):
        return jsonify({"error": "Valor inválido"}), 400

    if valor <= 0:
        return jsonify({"error": "Valor deve ser positivo"}), 400

    db_add_balance(valor, detalhes)
    return jsonify({"novo_saldo": get_data()['saldo']})


@app.route('/health', methods=['GET'])
def health():
    """Health check para load balancers."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


# ==================== STARTUP ====================

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def print_startup_banner(port):
    local_url = f"http://127.0.0.1:{port}"
    network_url = f"http://{get_local_ip()}:{port}"

    print("=" * 60)
    print("💰  SMART COFRINHO rodando!")
    print(f"🖥   Local (este PC):  {local_url}")
    print(f"📱  Rede (celular):    {network_url}")
    print("=" * 60)

    if not GEMINI_API_KEY:
        print("⚠️  AVISO: GEMINI_API_KEY não configurada no .env")
        print("   Configure no arquivo .env para usar a detecção por IA")
        print("=" * 60)

    print("Escaneie o QR Code abaixo com o celular (mesma Wi-Fi):\n")

    qr = qrcode.QRCode(border=1)
    qr.add_data(network_url)
    qr.make()
    qr.print_ascii(invert=True)
    print()


if __name__ == '__main__':
    init_db()
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('FLASK_ENV') == 'development'

    print_startup_banner(PORT)

    # Em produção, use gunicorn: gunicorn -w 4 -b 0.0.0.0:5000 app:app
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)