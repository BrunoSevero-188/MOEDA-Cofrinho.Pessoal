let balance = 0;
let lastDetectedValue = 0;
let lastImageHash = '';
const video = document.getElementById('video');

// Inicialização
updateBalanceDisplay();

// ==================== UTILITÁRIOS ====================

/** Gera hash simples da imagem para detectar mudanças significativas */
function getImageHash(canvas) {
    const ctx = canvas.getContext('2d');
    // Downscale para 32x32 e pega dados
    const small = document.createElement('canvas');
    small.width = 32;
    small.height = 32;
    small.getContext('2d').drawImage(canvas, 0, 0, 32, 32);
    const data = small.getContext('2d').getImageData(0, 0, 32, 32).data;
    let hash = 0;
    for (let i = 0; i < data.length; i += 4) {
        hash = ((hash << 5) - hash) + data[i] + data[i+1] + data[i+2];
        hash |= 0;
    }
    return hash.toString(36);
}

/** Mostra toast temporário */
function showToast(msg, isError = false) {
    const toast = document.createElement('div');
    toast.className = `toast ${isError ? 'error' : ''}`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/** Debounce helper */
function debounce(fn, ms) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}

// ==================== BALANCE & HISTORY ====================

async function updateBalanceDisplay() {
    try {
        const res = await fetch('/get_balance');
        const data = await res.json();
        document.getElementById('total-balance').innerText =
            `R$ ${Number(data.saldo).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
        renderHistory(data.historico || []);
    } catch (e) {
        console.error('Erro ao buscar saldo:', e);
    }
}

function renderHistory(historico) {
    const list = document.getElementById('history-list');
    const empty = document.getElementById('history-empty');

    if (!historico.length) {
        list.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    list.innerHTML = historico.map(h => `
        <li class="history-item">
            <div class="history-info">
                <span class="history-value">+ R$ ${Number(h.valor).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>
                <span class="history-detalhes">${h.detalhes || 'Adição manual'}</span>
            </div>
            <span class="history-date">${formatDate(h.data)}</span>
        </li>
    `).join('');
}

function formatDate(isoString) {
    if (!isoString) return '';
    const d = new Date(isoString);
    return d.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'});
}

// ==================== SCANNER ====================

async function openScanner() {
    document.getElementById('camera-overlay').classList.remove('hidden');
    document.getElementById('scan-status').innerText = "Iniciando câmera...";
    document.getElementById('current-scan-value').innerText = "R$ 0,00";
    lastDetectedValue = 0;
    lastImageHash = '';

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        document.getElementById('scan-status').innerText =
            "Câmera indisponível (precisa de HTTPS ou localhost).";
        showToast('Câmera não disponível neste navegador', true);
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } }
        });
        video.srcObject = stream;
        await video.play();
    } catch (err) {
        document.getElementById('scan-status').innerText = "Erro ao acessar câmera: " + err.message;
        showToast('Não foi possível acessar a câmera', true);
        return;
    }

    // Scan com debounce por mudança visual (não tempo fixo)
    const scanLoop = async () => {
        if (document.getElementById('camera-overlay').classList.contains('hidden')) return;

        // Só processa se a imagem mudou significativamente
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);

        const currentHash = getImageHash(canvas);
        const changed = currentHash !== lastImageHash;
        lastImageHash = currentHash;

        if (changed || lastDetectedValue === 0) {
            await scanFrame(canvas);
        }

        // Próximo frame em 500ms (mais responsivo, mas só processa se mudou)
        requestAnimationFrame(() => setTimeout(scanLoop, 500));
    };

    scanLoop();
}

async function scanFrame(canvas) {
    // Reusa canvas passado ou cria novo
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
    }

    const base64Image = canvas.toDataURL('image/jpeg', 0.8); // Qualidade 80%
    document.getElementById('scan-status').innerText = "🔍 Analisando...";

    try {
        const res = await fetch('/process_image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: base64Image }) // SEM api_key!
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detalhes || `HTTP ${res.status}`);
        }

        lastDetectedValue = Number(data.total) || 0;
        document.getElementById('current-scan-value').innerText =
            `R$ ${lastDetectedValue.toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
        document.getElementById('scan-status').innerText = data.detalhes || "Detectado";

    } catch (e) {
        document.getElementById('scan-status').innerText = "Erro: " + e.message;
        console.error('Scan error:', e);
    }
}

function closeScanner() {
    document.getElementById('camera-overlay').classList.add('hidden');
    if (video.srcObject) {
        video.srcObject.getTracks().forEach(t => t.stop());
        video.srcObject = null;
    }
}

async function confirmScan() {
    if (lastDetectedValue <= 0) {
        showToast('Nenhum valor detectado para adicionar', true);
        return;
    }

    try {
        const res = await fetch('/add_balance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                valor: lastDetectedValue,
                detalhes: `Scan: ${document.getElementById('scan-status').innerText}`
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Erro ao salvar');

        showToast(`✅ Adicionado R$ ${lastDetectedValue.toFixed(2)}`);
        updateBalanceDisplay();
        lastDetectedValue = 0;
        document.getElementById('current-scan-value').innerText = "R$ 0,00";
        document.getElementById('scan-status').innerText = "Buscando dinheiro...";

    } catch (e) {
        showToast('❌ ' + e.message, true);
    }
}

// ==================== UPLOAD DE FOTO ====================

async function calculateFromPhoto(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validação básica
    if (!file.type.startsWith('image/')) {
        showToast('Arquivo deve ser uma imagem', true);
        return;
    }
    if (file.size > 10 * 1024 * 1024) {
        showToast('Imagem muito grande (máx 10MB)', true);
        return;
    }

    const reader = new FileReader();
    reader.onload = async () => {
        const base64Image = reader.result;
        showToast('🔍 Analisando foto...');

        try {
            const res = await fetch('/process_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: base64Image })
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.detalhes || `HTTP ${res.status}`);

            const total = Number(data.total) || 0;
            const msg = `Valor detectado: R$ ${total.toFixed(2)}\n${data.detalhes}\n\nAdicionar ao saldo?`;

            if (confirm(msg)) {
                const addRes = await fetch('/add_balance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ valor: total, detalhes: `Foto: ${data.detalhes}` })
                });
                const addData = await addRes.json();
                if (!addRes.ok) throw new Error(addData.error || 'Erro ao salvar');

                showToast(`✅ Adicionado R$ ${total.toFixed(2)}`);
                updateBalanceDisplay();
            }
        } catch (e) {
            showToast('❌ ' + e.message, true);
        }
    };

    reader.readAsDataURL(file);
    event.target.value = ''; // Permite escolher mesma foto novamente
}

// ==================== EXPORT ====================
// Torna funções globais para onclick no HTML
window.openScanner = openScanner;
window.closeScanner = closeScanner;
window.confirmScan = confirmScan;
window.calculateFromPhoto = calculateFromPhoto;