# Smart Cofrinho

App Flask que usa a câmera do celular + Gemini API para reconhecer dinheiro (notas/moedas de Real) e somar num saldo.

## 🚀 Como rodar localmente

### 1. Pré-requisitos
- Python 3.10+
- Conta no [Google AI Studio](https://aistudio.google.com/apikey) para obter a API Key

### 2. Instalação

```bash
# Clone o repositório
git clone <url-do-repo>
cd MOEDA

# Crie ambiente virtual
python -m venv venv

# Ative o ambiente virtual
# Windows PowerShell:
venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat
# Linux/Mac:
source venv/bin/activate

# Instale dependências
pip install -r requirements.txt
```

### 3. Configuração

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite o .env e adicione sua chave
# GEMINI_API_KEY=sua_chave_aqui
```

**Obter API Key:** https://aistudio.google.com/apikey

### 4. Executar

```bash
python app.py
```

### 5. Acessar

**No computador (servidor):**
- Abra: http://localhost:5000
- Ou: http://127.0.0.1:5000

**No celular (mesma rede Wi-Fi):**
1. O terminal exibirá um **QR Code** e URLs como:
   ```
   PC  Local (este PC):  http://127.0.0.1:5000
   Tel Rede (celular):   http://192.168.1.XXX:5000
   ```
2. Escaneie o QR Code com a câmera do celular
3. Ou digite manualmente o IP mostrado (ex: `http://192.168.1.15:5000`)

> ⚠️ **Importante:** Celular e computador devem estar na **mesma rede Wi-Fi**

---

## 📱 Como usar

1. **Abrir câmera** → Botão "Escanear" (precisa de HTTPS ou localhost)
2. **Apontar para notas/moedas** → O app detecta automaticamente
3. **Confirmar valor** → Adiciona ao saldo
4. **Ou upload de foto** → Botão "Foto" para enviar imagem da galeria

---

## ⚙️ Configurações (.env)

| Variável | Obrigatório | Padrão | Descrição |
|----------|-------------|--------|-----------|
| `GEMINI_API_KEY` | Sim | - | Chave do Google Gemini |
| `FLASK_ENV` | Não | `development` | `development` ou `production` |
| `PORT` | Não | `5000` | Porta do servidor |

---

## 🔑 API Key por usuário (opcional)

Cada usuário pode configurar sua própria chave:
1. Clique no **ícone de engrenagem** (canto superior)
2. Cole sua API Key pessoal
3. Salva no `localStorage` do navegador
4. Tem prioridade sobre a chave do servidor

---

## 🐛 Solução de problemas

### "Chave da API inválida"
- Verifique se `GEMINI_API_KEY` no `.env` está preenchida corretamente
- Regenere em: https://aistudio.google.com/apikey
- Remova espaços/quebras de linha extras

### "Câmera indisponível"
- **HTTPS obrigatório** para câmera em produção
- Localmente funciona em `localhost` ou `127.0.0.1`
- No celular via IP local, use `http://IP:5000` (não https)

### "Cota esgotada / 429"
- Limite gratuito do Gemini atingido
- Aguarde ou crie nova chave

### Celular não acessa o IP
- Verifique se estão na **mesma Wi-Fi**
- Desative VPN no celular
- Firewall do Windows: permita Python na rede privada
- Teste: `ping <IP-do-PC>` no celular (via app Termux ou similar)

---

## 📦 Deploy no Vercel

1. Conecte o repositório no Vercel
2. Configure **Environment Variable**:
   - `GEMINI_API_KEY` = sua chave
3. Deploy automático

> O `vercel.json` e `api/index.py` já estão configurados para serverless.

---

## 🛠️ Desenvolvimento

```bash
# Modo debug com auto-reload
FLASK_ENV=development python app.py

# Produção (gunicorn)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

## 📁 Estrutura

```
MOEDA/
├── app.py              # App principal Flask
├── api/index.py        # Entry point Vercel
├── templates/index.html
├── static/
│   ├── css/style.css
│   └── js/script.js
├── requirements.txt
├── .env                # Não commitado (configure localmente)
├── .env.example        # Template
├── vercel.json
└── cofrinho.db         # SQLite (criado automaticamente)
```

---

## 📄 Licença

MIT