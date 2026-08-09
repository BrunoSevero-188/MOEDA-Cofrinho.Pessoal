from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import json
import os
import socket
import base64
from PIL import Image
import io
import qrcode

app = Flask(__name__)

from dotenv import load_dotenv
load_dotenv()

# Configurar a API KEY do Google Gemini via variável de ambiente
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError(
        "Defina a variável de ambiente GEMINI_API_KEY antes de rodar "
        "(ex: export GEMINI_API_KEY='sua_chave_aqui')"
    )

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

DB_FILE = 'cofrinho.json'


def get_data():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w') as f:
            json.dump({"saldo": 0.0, "historico": []}, f)
    with open(DB_FILE, 'r') as f:
        return json.load(f)


def save_data(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_balance', methods=['GET'])
def get_balance():
    return jsonify(get_data())


@app.route('/process_image', methods=['POST'])
def process_image():
    data = request.json
    image_data = data['image'].split(",")[1]  # Remove o cabeçalho base64
    img_bytes = base64.b64decode(image_data)
    img = Image.open(io.BytesIO(img_bytes))

    # Pedindo explicitamente JSON válido (aspas duplas) para evitar erro no json.loads
    prompt = (
        'Conte o valor total em dinheiro (Notas e Moedas de Real BRL) nesta imagem. '
        'Retorne APENAS um JSON válido, com aspas duplas, no formato: '
        '{"total": valor_float, "detalhes": "string"}'
    )

    try:
        response = model.generate_content([prompt, img])
        txt = response.text.replace('```json', '').replace('```', '').strip()
        result = json.loads(txt)
        return jsonify(result)
    except Exception as e:
        return jsonify({"total": 0, "detalhes": f"Erro no processamento: {e}"}), 500


@app.route('/add_balance', methods=['POST'])
def add_balance():
    val = request.json.get('valor', 0)
    data = get_data()
    data['saldo'] += float(val)
    data['historico'].append({"valor": float(val)})
    save_data(data)
    return jsonify({"novo_saldo": data['saldo']})


def get_local_ip():
    """Descobre o IP da máquina na rede local (sem precisar de internet real)."""
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
    local_url = f"https://127.0.0.1:{port}"
    network_url = f"https://{get_local_ip()}:{port}"

    print("=" * 55)
    print("💰  SMART COFRINHO rodando!")
    print(f"🖥   Local (este PC):  {local_url}")
    print(f"📱  Rede (celular):    {network_url}")
    print("=" * 55)
    print("Escaneie o QR Code abaixo com o celular (mesma Wi-Fi):\n")
    print("⚠️  O navegador vai avisar que o site 'não é seguro' (certificado")
    print("    autoassinado). Toque em 'Avançado' > 'Acessar mesmo assim'.\n")

    qr = qrcode.QRCode(border=1)
    qr.add_data(network_url)
    qr.make()
    qr.print_ascii(invert=True)
    print()


if __name__ == '__main__':
    PORT = 5000
    print_startup_banner(PORT)
    app.run(host='0.0.0.0', port=PORT, debug=True, ssl_context='adhoc')