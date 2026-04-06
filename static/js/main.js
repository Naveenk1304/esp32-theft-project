// State variables
let apiKey = localStorage.getItem('electricity_api_key');
let last_update = 0;
let currentStatus = "NORMAL"; // NORMAL or THEFT
let lastStatusChangeTime = 0;
let theftConfirmationStartTime = 0;
let isConfirmingTheft = false;
let charts = {};

// Chart.js Configuration
function createChart(id, label, color) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: color,
                backgroundColor: color + '22',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                y: { 
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8b949e' }
                }
            },
            plugins: {
                legend: { display: true, labels: { color: '#8b949e' } }
            }
        }
    });
}

// Initializing Charts
function initCharts() {
    charts.current = createChart('currentChart', 'Current (A)', '#00ff41');
    charts.power = createChart('powerChart', 'Power (W)', '#00ff41');
    charts.energy = createChart('energyChart', 'Energy (kWh)', '#00ff41');
}

function updateCharts(data) {
    const timeLabel = new Date().toLocaleTimeString();
    
    ['current', 'power', 'energy'].forEach(key => {
        const chart = charts[key];
        if (!chart) return;
        chart.data.labels.push(timeLabel);
        chart.data.datasets[0].data.push(data[key]);
        
        // Keep only last 20 points
        if (chart.data.labels.length > 20) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
        }
        
        chart.update('none');
    });
}

// Data Handling
async function fetchLatestData() {
    try {
        const response = await fetch('/api/latest');
        const result = await response.json();

        // Update last_update from backend
        if (result.last_update) {
            last_update = result.last_update;
        }

        processData(result);

    } catch (e) {
        console.error("Polling error:", e);
        updateStatusUI(false);
    }
}

// Connectivity Check Logic
function checkConnectivity() {
    const now = Date.now();
    // If last_update is within 5 seconds (5000ms)
    if (last_update > 0 && (now - last_update) < 5000) {
        updateStatusUI(true);
    } else {
        updateStatusUI(false);
    }
}

function processData(data) {
    document.getElementById('val-voltage').innerText = Number(data.voltage).toFixed(1);
    document.getElementById('val-current').innerText = Number(data.current).toFixed(2);
    document.getElementById('val-power').innerText = Number(data.power).toFixed(1);
    document.getElementById('val-energy').innerText = Number(data.energy).toFixed(2);

    updateCharts(data);

    // THEFT DEBOUNCE LOGIC
    const now = Date.now();
    
    if (data.theft) {
        if (currentStatus === "NORMAL") {
            if (!isConfirmingTheft) {
                isConfirmingTheft = true;
                theftConfirmationStartTime = now;
            } else if (now - theftConfirmationStartTime >= 6000) { // 6 seconds confirmation
                currentStatus = "THEFT";
                lastStatusChangeTime = now;
                isConfirmingTheft = false;
                triggerAlert();
                sendNotification();
                showToast("⚠️ Electricity Theft Detected!");
            }
        } else {
            isConfirmingTheft = false;
        }
    } else {
        isConfirmingTheft = false;
        if (currentStatus === "THEFT") {
            // Hold THEFT for at least 7 seconds before switching back
            if (now - lastStatusChangeTime >= 7000) {
                currentStatus = "NORMAL";
                lastStatusChangeTime = now;
                resetAlert();
            }
        }
    }
}

function sendNotification() {
    if (Notification.permission === "granted") {
        new Notification("⚠️ Electricity Theft Detected!", {
            body: "Abnormal power usage detected in your system",
            icon: "https://cdn-icons-png.flaticon.com/512/565/565547.png"
        });
    }
}

function showToast(message) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<span>🚨</span> <span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 500);
    }, 5000);
}

function triggerAlert() {
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    
    if (indicator) {
        indicator.classList.add('theft');
        indicator.innerText = "⚠️ THEFT DETECTED";
    }
    if (subtext) {
        subtext.innerText = "CRITICAL: ABNORMAL POWER CONSUMPTION";
        subtext.style.color = "#ff3131";
    }
}

function resetAlert() {
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    
    if (indicator) {
        indicator.classList.remove('theft');
        indicator.innerText = "NORMAL";
    }
    if (subtext) {
        subtext.innerText = "System Operating Correctly";
        subtext.style.color = "#8b949e";
    }
}

function updateStatusUI(connected) {
    const sensorDot = document.getElementById('sensor-dot');
    const sensorStatus = document.getElementById('sensor-status');
    const aiDot = document.getElementById('ai-dot');
    const aiStatus = document.getElementById('ai-status');

    if (connected) {
        if (sensorDot) sensorDot.classList.add('connected');
        if (sensorStatus) sensorStatus.innerText = "CONNECTED";
        if (aiDot) aiDot.classList.add('connected');
        if (aiStatus) aiStatus.innerText = "AI LISTENING...";
    } else {
        if (sensorDot) sensorDot.classList.remove('connected');
        if (sensorStatus) sensorStatus.innerText = "NOT CONNECTED";
        if (aiDot) aiDot.classList.remove('connected');
        if (aiStatus) aiStatus.innerText = "AI: NOT RUNNING";
    }
}

function generateApiKey() {
    fetch('/generate-key')
        .then(res => res.json())
        .then(data => {
            apiKey = data.api_key;
            localStorage.setItem('electricity_api_key', apiKey);
            document.getElementById('api-key-box').innerText = apiKey;
            document.getElementById('api-key-display').innerText = "API KEY: " + apiKey;
        })
        .catch(err => console.error("Key generation failed:", err));
}

function openModal() { document.getElementById('setupModal').style.display = 'block'; }
function closeModal() { document.getElementById('setupModal').style.display = 'none'; }

// Initialize
window.onload = () => {
    if (Notification.permission !== "granted" && Notification.permission !== "denied") {
        Notification.requestPermission();
    }

    initCharts();
    if (apiKey) {
        document.getElementById('api-key-display').innerText = "API KEY: " + apiKey;
        document.getElementById('api-key-box').innerText = apiKey;
    }
    
    // Polling data every 2 seconds
    setInterval(fetchLatestData, 2000);
    
    // Connectivity check every 1 second
    setInterval(checkConnectivity, 1000);
};

window.onclick = (event) => {
    const modal = document.getElementById('setupModal');
    if (event.target == modal) closeModal();
};
