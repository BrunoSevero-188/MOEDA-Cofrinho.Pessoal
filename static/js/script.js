let balance = 0;
let lastDetectedValue = 0;
const video = document.getElementById('video');

updateBalanceDisplay();

function getApiKey() { 
    return localStorage.getItem('gemini_api_key') || ''; 
}

function openSettings() { 
    document.getElementById('api-key-input').value = getApiKey(); 
    document.getElementById('settings-modal').classList.remove('hidden'); 
}

function closeSettings() { 
    document.getElementById('settings-modal').classList.add('hidden'); 
}

function saveApiKey() { 
    const key = document.getElementById('api-key-input').value.trim(); 
    if (!key) { 
        alert('Cole uma chave válida antes de salvar.'); 
        return; 
    } 
    localStorage.setItem('gemini_api_key', key); 
    closeSettings(); 
}

async function updateBalanceDisplay() { 
    const res = await fetch('/get_balance'); 
    const data = await res.json(); 
    document.getElementById('total-balance').innerText = `R$ ${data.saldo.toFixed(2)}`; 
}

async function confirmScan() { 
    await fetch('/add_balance', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ valor: lastDetectedValue }) 
    }); 
    updateBalanceDisplay(); 
}

async function openScanner() { 
    if (!getApiKey()) { 
        alert('Configure sua chave de API primeiro (ícone de engrenagem).'); 
        openSettings(); 
        return; 
    } 
    
    document.getElementById('camera-overlay').classList.remove('hidden'); 
    
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { 
        document.getElementById('scan-status').innerText = "Câmera indisponível (verifique se está usando HTTPS)."; 
        return; 
    } 
    
    try { 
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } }); 
        video.srcObject = stream; 
    } catch (err) { 
        document.getElementById('scan-status').innerText = "Não foi possível acessar a câmera: " + err.message; 
        return; 
    } 
    
    const scannerInterval = setInterval(async () => { 
        if (document.getElementById('camera-overlay').classList.contains('hidden')) { 
            clearInterval(scannerInterval); 
            return; 
        } 
        scanFrame(); 
    }, 3000); 
}

async function scanFrame() { 
    const canvas = document.createElement('canvas'); 
    canvas.width = video.videoWidth; 
    canvas.height = video.videoHeight; 
    canvas.getContext('2d').drawImage(video, 0, 0); 
    
    const base64Image = canvas.toDataURL('image/jpeg'); 
    document.getElementById('scan-status').innerText = "Analisando..."; 
    
    const res = await fetch('/process_image', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ image: base64Image, api_key: getApiKey() }) 
    }); 
    
    const data = await res.json(); 
    lastDetectedValue = data.total || 0; 
    document.getElementById('current-scan-value').innerText = `R$ ${lastDetectedValue.toFixed(2)}`; 
    document.getElementById('scan-status').innerText = data.detalhes; 
}

function closeScanner() { 
    document.getElementById('camera-overlay').classList.add('hidden'); 
    video.srcObject.getTracks().forEach(t => t.stop()); 
}

async function calculateFromPhoto(event) { 
    if (!getApiKey()) { 
        alert('Configure sua chave de API primeiro (ícone de engrenagem).'); 
        openSettings(); 
        return; 
    } 
    
    const file = event.target.files[0]; 
    if (!file) return; 
    
    const reader = new FileReader(); 
    reader.onload = async () => { 
        const base64Image = reader.result; 
        const res = await fetch('/process_image', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ image: base64Image, api_key: getApiKey() }) 
        }); 
        
        const data = await res.json(); 
        const total = data.total || 0; 
        
        if (confirm(`Valor detectado: R$ ${total.toFixed(2)}\n${data.detalhes}\n\nAdicionar ao saldo?`)) { 
            await fetch('/add_balance', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ valor: total }) 
            }); 
            updateBalanceDisplay(); 
        } 
    }; 
    
    reader.readAsDataURL(file); 
    event.target.value = ''; // Permite escolher a mesma foto de novo depois 
}