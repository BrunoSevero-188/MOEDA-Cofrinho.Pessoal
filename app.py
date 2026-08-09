from flask import Flask, render_template, request, jsonify
from google import genai
import json
import os
import socket
import base64
from PIL import Image
import io
import qrcode

app = Flask(__name__)

MODEL_NAME = "gemini-2.0-flash"
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
    api_key = data.get('api_key', '').strip()

    if not api_key:
        return jsonify({"total": 0, "detalhes": "Nenhuma chave de API configurada."}), 400

    image_data = data['image'].split(",")[1]
    img_bytes = base64.b64decode(image_data)
    img = Image.open(io.BytesIO(img_bytes))

    prompt = (
        'Conte o valor total em dinheiro (Notas e Moedas de Real BRL) nesta imagem. '
        'Retorne APENAS um JSON válido, com aspas duplas, no formato: '
        '{"total": valor_float, "detalhes": "string"}'
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, img],
        )
        txt = response.text.replace('```json', '').replace('```', '').strip()
        result = json.loads(txt)
        return jsonify(result)
    except Exception as e:
        msg = str(e)
        if "API key not valid" in msg or "API_KEY_INVALID" in msg:
            return jsonify({"total": 0, "detalhes": "Chave de API inválida."}), 401
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            return jsonify({
                "total": 0,
                "detalhes": "Cota da API esgotada ou indisponível para essa chave. Tente gerar uma nova chave em aistudio.google.com/apikey ou aguarde alguns minutos."
            }), 429
        return jsonify({"total": 0, "detalhes": "Erro no processamento. Tente novamente."}), 500


@app.route('/add_balance', methods=['POST'])
def add_balance():
    val = request.json.get('valor', 0)
    data = get_data()
    data['saldo'] += float(val)
    data['historico'].append({"valor": float(val)})
    save_data(data)
    return jsonify({"novo_saldo": data['saldo']})


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
    local_url = f"https://127.0.0.1:{port}"
    network_url = f"https://{get_local_ip()}:{port}"

    print("=" * 55)
    print("💰  SMART COFRINHO rodando!")
    print(f"🖥   Local (este PC):  {local_url}")
    print(f"📱  Rede (celular):    {network_url}")
    print("=" * 55)
    print("Escaneie o QR Code abaixo com o celular (mesma Wi-Fi):\n")

    qr = qrcode.QRCode(border=1)
    qr.add_data(network_url)
    qr.make()
    qr.print_ascii(invert=True)
    print()


if __name__ == '__main__':
    PORT = 5000
    print_startup_banner(PORT)
    app.run(host='0.0.0.0', port=PORT, debug=True, ssl_context='adhoc')