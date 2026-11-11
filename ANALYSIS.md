# Análise do Projeto MOEDA - Smart Cofrinho

## 📋 Resumo
Aplicação Flask que usa câmera do celular + Gemini API para reconhecer dinheiro (BRL) e somar ao saldo.

---

## 🔴 Problemas Críticos

### 1. **Segurança - API Key exposta no frontend**
```javascript
// static/js/script.js - Linha 88
body: JSON.stringify({ image: base64Image, api_key: getApiKey() })
```
- A chave da API viaja no body da requisição para cada scan
- Qualquer pessoa na rede Wi-Fi pode interceptar e usar sua quota
- **Solução**: Mover a chave para variável de ambiente no backend (`app.py`)

### 2. **SSL "adhoc" inseguro para produção**
```python
# app.py - Linha 121
app.run(host='0.0.0.0', port=PORT, debug=True, ssl_context='adhoc')
```
- Certificado auto-assinado novo a cada reinício
- Navegadores bloqueiam câmera em HTTP, mas `adhoc` não é confiável
- **Solução**: Usar certificado real (Let's Encrypt) ou tunnel (ngrok/cloudflare)

### 3. **Arquivo JSON sem lock/atomicidade**
```python
# app.py - Linhas 17-27
def save_data(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f)
```
- Race condition em acessos concorrentes
- Corrupção de dados se dois requests salvam ao mesmo tempo
- **Solução**: SQLite com WAL mode ou `fcntl`/`portalocker`

### 4. **Prompt do Gemini frágil**
```python
# app.py - Linhas 52-56
prompt = 'Conte o valor total... Retorne APENAS um JSON válido...'
```
- Sem exemplos (few-shot) → alucinações frequentes
- Não valida se o retorno é realmente JSON válido
- **Solução**: Adicionar exemplos, schema JSON, validação rigorosa

### 5. **`debug=True` em produção**
- Expõe stack traces, permite execução arbitrária via debugger pin
- **Solução**: `debug=False` + variável de ambiente `FLASK_ENV=production`

---

## 🟡 Problemas Médios

| Área | Problema | Impacto |
|------|----------|---------|
| **Frontend** | Scanner a cada 3s fixo (`setInterval`) | Gasta quota desnecessariamente |
| **Frontend** | Sem feedback visual durante análise | UX confusa |
| **Backend** | Sem rate limiting por IP/chave | Abuso de quota |
| **Backend** | Sem logs estruturados | Debug difícil |
| **Deploy** | `vercel.json` aponta para `api/index.py` que não existe | Deploy falha |
| **Dados** | `cofrinho.json` versionado no `.gitignore` mas existe no repo | Vaza dados locais |

---

## 🟢 Melhorias Sugeridas (Prioridade)

### 1. **Backend - Segurança & Robustez** ⭐⭐⭐
```python
# Novo app.py structure
- Variável de ambiente: GEMINI_API_KEY (não vir do frontend)
- SQLite com SQLAlchemy ou aiosqlite
- Rate limiting: Flask-Limiter
- Validação Pydantic do response do Gemini
- Logs com structlog
- Health check endpoint
```

### 2. **Frontend - UX & Performance** ⭐⭐
```javascript
// Melhorias no script.js
- Debounce no scan (só analisa se imagem mudou significativamente)
- Web Worker para canvas → base64 (não bloqueia UI)
- Preview do que está sendo detectado (bounding boxes)
- Offline-first: IndexedDB para histórico local
- PWA manifest + service worker
```

### 3. **Arquitetura** ⭐
```
MOEDA/
├── app/
│   ├── __init__.py
│   ├── routes/
│   │   ├── api.py
│   │   └── web.py
│   ├── services/
│   │   ├── gemini.py
│   │   └── storage.py
│   └── models.py
├── tests/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

### 4. **Deploy & CI/CD**
- GitHub Actions: lint (ruff), type-check (mypy), test (pytest)
- Docker multi-stage para produção
- Vercel/Render/Fly.io com variáveis de ambiente seguras
- Monitoramento: Sentry + uptime check

---

## 📦 Checklist de Ação Imediata

- [ ] Mover `GEMINI_API_KEY` para `.env` apenas no backend
- [ ] Remover `api_key` do payload frontend→backend
- [ ] Trocar `ssl_context='adhoc'` por certificado real ou tunnel
- [ ] Migrar `cofrinho.json` → SQLite
- [ ] Adicionar `FLASK_ENV=production` e `debug=False`
- [ ] Corrigir `vercel.json` (apontar para `app.py` ou criar `api/index.py`)
- [ ] Adicionar `.env` ao `.gitignore` (já está, ok)
- [ ] Remover `cofrinho.json` do repo (`git rm --cached cofrinho.json`)

---

## 💰 Estimativa de Esforço

| Melhoria | Tempo | Prioridade |
|----------|-------|------------|
| Segurança API Key | 30 min | 🔴 Crítica |
| SQLite + locks | 1-2h | 🔴 Crítica |
| Rate limiting | 30 min | 🟡 Alta |
| Prompt engineering Gemini | 1h | 🟡 Alta |
| PWA + offline | 3-4h | 🟢 Média |
| Testes + CI | 2h | 🟢 Média |
| Refatoração modular | 4-6h | 🟢 Baixa |

---

## 🚀 Próximos Passos Recomendados

1. **Hoje**: Corrigir os 3 problemas críticos (API key, SSL, SQLite)
2. **Esta semana**: Rate limiting + prompt melhorado + logs
3. **Próxima sprint**: PWA + testes + CI/CD
4. **Contínuo**: Monitorar quota Gemini, adicionar fallback (outro modelo)

---

*Gerado em 2026-11-11*
