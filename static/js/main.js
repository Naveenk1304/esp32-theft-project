// State variables
let apiKey = localStorage.getItem('electricity_api_key');
let last_update = 0;
let mode = "demo"; // demo | real | learning | monitoring
let learned_current = null;
let learning_readings = [];
let charts = {};
let mode = "demo"; // demo | real | learning | monitoring

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
    }
}

// Connectivity Check Logic
function checkConnectivity() {
    const now = Date.now();

    cote >& (now - last_update) < 5000;
    
    // Update Mode if not in learning or monitoring
    if (mode === "demo" || mode === "tual"e {;   
    mod  = i Connmctedo? "real" : "demo";e = "real";   // 🔥 ADD THIS
    } else {
        updateStatusUI(isConnected);
    updateModeUI();
    
    mode = "demo";   // 🔥 ADD THIS
    }

    updateModeUI(); // 🔥 ADD THIS
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
        if (aiStatus) aiStatus.innerText = (mode === "monitoring") ? "MONITORING ACTIVE" : (mode === "learning" ? "LEARNING..." : "AI READY");
    } else {
        if (sensorDot) sensorDot.classList.remove('connected');
        if (sensorStatus) sensorStatus.innerText = "NOT CONNECTED";
        if (aiDot) aiDot.classList.remove('connected');
        if (aiStatus) aiStatus.innerText = "AI: NOT RUNNING";
    }
}

function updateModeUI() {
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    const setupBtn = document.getElementById('setupBtn');
    const learnBtn = document.getElementById('learnBtn');
    const resetBtn = document.getElementById('resetBtn');
    const learningContainer = document.getElementById('learning-container');

    // Default: Hide all buttons and containers
    setupBtn.style.display = "none";
    learnBtn.style.display = "none";
    resetBtn.style.display = "none";
    learningContainer.style.display = "none";
    
    // Default text color and animation
    indicator.classList.remove('theft', 'learning-blink');

    if (mode === "demo") {
        indicator.innerText = "DEMO MODE";
        subtext.innerText = "Setup API Key to enable real monitoring";
        subtext.style.color = "#8b949e";
        setupBtn.style.display = "block";
    } 
    else if (mode === "real") {
        indicator.innerText = "READY";
        subtext.innerText = "Click Learn Pattern to start AI";
        subtext.style.color = "#8b949e";
        learnBtn.style.display = "block";
    } 
    else if (mode === "learning") {
        indicator.innerText = "LEARNING...";
        indicator.classList.add('learning-blink');
        subtext.innerText = "Collecting baseline data...";
        subtext.style.color = "var(--neon-green)";
        learningContainer.style.display = "block";
        // Buttons stay hidden in learning
    } 
    else if (mode === "monitoring") {
        // If theft is detected, processData will handle the UI
        // This is the default monitoring state
        if (!indicator.classList.contains('theft')) {
            indicator.innerText = "MONITORING";
            subtext.innerText = "System Operating Correctly";
            subtext.style.color = "#8b949e";
        }
        resetBtn.style.display = "block";
    }
}

function processData(data) {
    document.getElementById('val-voltage').innerText = Number(data.voltage).toFixed(1);
    document.getElementById('val-current').innerText = Number(data.current).toFixed(2);
    document.getElementById('val-power').innerText = Number(data.power).toFixed(1);
    document.getElementById('val-energy').innerText = Number(data.energy).toFixed(2);

    updateCharts(data);

    if (mode === "learning") {
        learning_readings.push(Number(data.current));
        const progress = (learning_readings.length / 50) * 100;
        document.getElementById('learning-progress').style.width = progress + "%";
        
        if (learning_readings.length >= 50) {
            const sum = learning_readings.reduce((a, b) => a + b, 0);
            learned_current = sum / learning_readings.length;
            mode = "monitoring";
            learning_readings = [];
            showToast("Learning Complete! Baseline established.");
            updateModeUI();
        }
    } 
    else if (mode === "monitoring") {
        const currentNow = Number(data.current);
        if (currentNow > learned_current + 0.02) {
            triggerAlert(learned_current, currentNow);
        } else {
            resetAlert();
        }
    }
}

function triggerAlert(learned, current) {
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    
    indicator.classList.add('theft');
    indicator.innerText = "THEFT DETECTED";
    subtext.innerText = "CRITICAL: ABNORMAL POWER CONSUMPTION";
    subtext.style.color = "#ff3131";
    
    // Add to theft logs if not already showing
    document.getElementById('theft-table-container').style.display = "block";
    const tbody = document.getElementById('theft-logs-body');
    
    // Only add if last log was more than 10 seconds ago to avoid spam
    const lastRow = tbody.firstElementChild;
    const now = new Date();
    if (!lastRow || (now - new Date(lastRow.dataset.time) > 10000)) {
        const row = document.createElement('tr');
        row.dataset.time = now.toISOString();
        row.style.borderBottom = "1px solid #30363d";
        row.innerHTML = `
            <td style="padding: 10px;">${now.toLocaleTimeString()}</td>
            <td style="padding: 10px;">${learned.toFixed(2)}</td>
            <td style="padding: 10px; color: #ff3131;">${current.toFixed(2)}</td>
            <td style="padding: 10px; color: #ff3131;">+${(current - learned).toFixed(2)}</td>
        `;
        tbody.prepend(row);
        showToast("⚠️ Electricity Theft Detected!");
        sendNotification();
    }
}

function resetAlert() {
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    
    if (indicator.classList.contains('theft')) {
        indicator.classList.remove('theft');
        indicator.innerText = "MONITORING";
        subtext.innerText = "System Operating Correctly";
        subtext.style.color = "#8b949e";
    }
}

function startLearning() {
    if (mode === "real") {
        mode = "learning";
        learning_readings = [];
        document.getElementById('learning-progress').style.width = "0%";
        updateModeUI();
    }
}

function resetPattern() {
    learned_current = null;
    learning_readings = [];
    mode = (last_update > 0 && (Date.now() - last_update) < 5000) ? "real" : "demo";
    document.getElementById('theft-table-container').style.display = "none";
    document.getElementById('theft-logs-body').innerHTML = "";
    resetAlert();
    updateModeUI();
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

document.getElementById("setupBtn").addEventListener("click", () => {
    if (mode === "demo") {
        openModal(); // existing setup
    } else if (mode === "real") {
        alert("Start Learning Mode (next step)");
    }
});

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

function updateModeUI() {
    const indicator = document.getElementById('indicator-circle');
    const subtext = document.getElementById('indicator-subtext');
    const setupBtn = document.getElementById('setupBtn');

    if (!indicator || !setupBtn) return;

    if (mode === "demo") {
        indicator.innerText = "DEMO MODE";
        subtext.innerText = "Setup API Key to enable real monitoring";
        setupBtn.innerText = "SETUP";
    }

    if (mode === "real") {
        indicator.innerText = "READY";
        subtext.innerText = "Click Learn Pattern to start AI";
        setupBtn.innerText = "LEARN PATTERN";
    }
}