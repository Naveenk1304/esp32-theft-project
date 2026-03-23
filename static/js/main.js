// State variables
let apiKey = localStorage.getItem('electricity_api_key');
let isRealData = false;
let theftDetected = false;
let alertShown = false; // Control variable for single-trigger notifications
let lastAlertTime = 0;
let simulationInterval;
let charts = {};

// Chart.js Configuration
function createChart(id, label, color) {
    const ctx = document.getElementById(id).getContext('2d');
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

        // 🔥 ALWAYS mark as connected if data received
        updateStatusUI(true);

        processData(result);

    } catch (e) {
        console.error("Polling error:", e);
        updateStatusUI(false);
    }
}

function startSimulation() {
    simulationInterval = setInterval(() => {
        const demoData = {
            voltage: (220 + Math.random() * 10).toFixed(1),
            current: (1 + Math.random() * 2).toFixed(2),
            power: (200 + Math.random() * 400).toFixed(1),
            energy: (10 + Math.random() * 5).toFixed(3)
        };
        processData(demoData);
    }, 2000);
}

function processData(data) {
    document.getElementById('val-voltage').innerText = Number(data.voltage).toFixed(1);
    document.getElementById('val-current').innerText = Number(data.current).toFixed(2);
    document.getElementById('val-power').innerText = Number(data.power).toFixed(1);
    document.getElementById('val-energy').innerText = Number(data.energy).toFixed(2);

    updateCharts(data);

    // ✅ MOVE HERE (IMPORTANT)
    if (data.theft && Date.now() - lastAlertTime > 10000) {
        if (!alertShown) {
            triggerAlert();
            sendNotification();
            showToast("⚠️ Electricity Theft Detected!");
            alertShown = true;
            lastAlertTime = Date.now(); // 👈 UPDATE TIME
        }
    } else {
        if (alertShown && !data.theft) {
            resetAlert();
            alertShown = false;
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
    theftDetected = true;
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    
    indicator.classList.add('theft');
    indicator.innerText = "⚠️ THEFT DETECTED";
    subtext.innerText = "CRITICAL: ABNORMAL POWER CONSUMPTION";
    subtext.style.color = "#ff3131";
}

function resetAlert() {
    theftDetected = false;
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    
    indicator.classList.remove('theft');
    indicator.innerText = "NORMAL";
    subtext.innerText = "System Operating Correctly";
    subtext.style.color = "#8b949e";
}

function updateStatusUI(connected) {
    const sensorDot = document.getElementById('sensor-dot');
    const sensorStatus = document.getElementById('sensor-status');
    const aiDot = document.getElementById('ai-dot');
    const aiStatus = document.getElementById('ai-status');

    if (connected) {
        sensorDot.classList.add('connected');
        sensorStatus.innerText = "CONNECTED";
        aiDot.classList.add('connected');
        aiStatus.innerText = "AI LISTENING...";
    } else {
        sensorDot.classList.remove('connected');
        sensorStatus.innerText = "NOT CONNECTED";
        aiDot.classList.remove('connected');
        aiStatus.innerText = "AI: NOT RUNNING";
    }
}

function resetCharts() {
    ['current', 'power', 'energy'].forEach(key => {
        charts[key].data.labels = [];
        charts[key].data.datasets[0].data = [];
        charts[key].update();
    });
}

function openModal() { document.getElementById('setupModal').style.display = 'block'; }
function closeModal() { document.getElementById('setupModal').style.display = 'none'; }

function generateApiKey() {
    const existingKey = localStorage.getItem('electricity_api_key');
    
    if (existingKey) {
        alert("API key already generated");
        document.getElementById('api-key-box').innerText = existingKey;
        document.getElementById('api-key-display').innerText = "API KEY: " + existingKey;
        return;
    }

    const newKey = 'NK-' + Math.random().toString(36).substr(2, 9).toUpperCase();
    apiKey = newKey;
    localStorage.setItem('electricity_api_key', newKey);
    document.getElementById('api-key-box').innerText = newKey;
    document.getElementById('api-key-display').innerText = "API KEY: " + newKey;
}

// Initialize
window.onload = () => {
    // REQUEST PERMISSION
    if (Notification.permission !== "granted") {
        Notification.requestPermission();
    }

    initCharts();
    if (apiKey) {
        document.getElementById('api-key-display').innerText = "API KEY: " + apiKey;
        document.getElementById('api-key-box').innerText = apiKey;
    }
    
    setInterval(fetchLatestData, 2000);
    startSimulation();
};

window.onclick = (event) => {
    const modal = document.getElementById('setupModal');
    if (event.target == modal) closeModal();
};
