// State variables
let charts = {};
let isLearning = false;
let learningReadings = [];
const LEARNING_TARGET = 30;

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
        const data = await response.json();

        updateUI(data);
        
        if (isLearning && data.is_real) {
            processLearning(data.current);
        }

    } catch (e) {
        console.error("Polling error:", e);
    }
}

function updateUI(data) {
    // Stats Update
    document.getElementById('val-voltage').innerText = Number(data.voltage).toFixed(1);
    document.getElementById('val-current').innerText = Number(data.current).toFixed(2);
    document.getElementById('val-power').innerText = Number(data.power).toFixed(1);
    document.getElementById('val-energy').innerText = Number(data.energy).toFixed(3);

    updateCharts(data);

    // Status Display
    const sensorStatus = document.getElementById('sensor-status');
    const aiStatus = document.getElementById('ai-status');
    const sensorDot = document.getElementById('sensor-dot');
    const aiDot = document.getElementById('ai-dot');
    const apiKeyDisplay = document.getElementById('api-key-display');
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    const genBtn = document.getElementById('generateKeyHeaderBtn');
    const learnBtn = document.getElementById('learnBtn');

    sensorStatus.innerText = data.status.toUpperCase();
    aiStatus.innerText = data.ai_status.toUpperCase();
    apiKeyDisplay.innerText = "API KEY: " + (data.api_key || "NOT GENERATED");

    if (data.sensor_connected) {
        sensorDot.classList.add('connected');
        genBtn.style.display = "none";
        learnBtn.style.display = (data.ai_status === "AI RUNNING" || isLearning) ? "none" : "block";
        indicator.innerText = data.theft ? "THEFT DETECTED" : (isLearning ? "LEARNING..." : (data.ai_status === "AI RUNNING" ? "MONITORING" : "AI READY"));
        
        if (data.theft) {
            indicator.classList.add('theft');
            subtext.innerText = "CRITICAL: ABNORMAL POWER CONSUMPTION";
            subtext.style.color = "#ff3131";
        } else {
            indicator.classList.remove('theft');
            subtext.innerText = isLearning ? "Collecting baseline data..." : "System Operating Correctly";
            subtext.style.color = "#8b949e";
        }

        if (data.ai_status === "AI RUNNING") {
            aiDot.classList.add('connected');
        } else {
            aiDot.classList.remove('connected');
        }
    } else {
        sensorDot.classList.remove('connected');
        aiDot.classList.remove('connected');
        genBtn.style.display = "block";
        learnBtn.style.display = "none";
        indicator.innerText = "DEMO MODE";
        indicator.classList.remove('theft');
        subtext.innerText = "Put your API key into ESP code";
        subtext.style.color = "#8b949e";
    }

    // Update Logs Table
    if (data.theft_logs && data.theft_logs.length > 0) {
        document.getElementById('theft-table-container').style.display = "block";
        const tbody = document.getElementById('theft-logs-body');
        tbody.innerHTML = "";
        data.theft_logs.slice().reverse().forEach(log => {
            const row = `<tr>
                <td style="padding: 10px;">${log.timestamp}</td>
                <td style="padding: 10px;">${log.learned_current}</td>
                <td style="padding: 10px; color: #ff3131;">${log.current_now}</td>
                <td style="padding: 10px; color: #ff3131;">+${log.difference}</td>
            </tr>`;
            tbody.innerHTML += row;
        });
    }
}

function processLearning(current) {
    learningReadings.push(Number(current));
    const progress = (learningReadings.length / LEARNING_TARGET) * 100;
    document.getElementById('learning-progress').style.width = progress + "%";
    
    if (learningReadings.length >= LEARNING_TARGET) {
        const sum = learningReadings.reduce((a, b) => a + b, 0);
        const avg = sum / learningReadings.length;
        
        fetch('/api/learn', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({average_current: avg})
        }).then(() => {
            isLearning = false;
            learningReadings = [];
            document.getElementById('learning-container').style.display = "none";
            showToast("Learning Complete! AI is now monitoring.");
        });
    }
}

function startLearning() {
    isLearning = true;
    learningReadings = [];
    document.getElementById('learning-container').style.display = "block";
    document.getElementById('learning-progress').style.width = "0%";
    document.getElementById('learnBtn').style.display = "none";
}

function generateApiKey() {
    fetch('/generate-key')
        .then(res => res.json())
        .then(data => {
            if (data.api_key) {
                document.getElementById('api-key-box').innerText = data.api_key;
                document.getElementById('api-key-display').innerText = "API KEY: " + data.api_key;
                
                // Sync with server active key
                fetch('/api/set-active-key', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({api_key: data.api_key})
                });

                showToast("API Key Generated Successfully!");
            }
        });
}

function manualSendLogs() {
    fetch('/api/send-logs', {method: 'POST'})
        .then(res => res.json())
        .then(data => {
            if (data.success) showToast("Logs sent to Telegram!");
            else showToast(data.message || "No logs to send");
        });
}

function openModal() { document.getElementById('setupModal').style.display = 'block'; }
function closeModal() { document.getElementById('setupModal').style.display = 'none'; }

function showToast(msg) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Initial setup
window.onload = () => {
    initCharts();
    setInterval(fetchLatestData, 1000);
};
