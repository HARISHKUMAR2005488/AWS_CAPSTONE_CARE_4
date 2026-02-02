// User Dashboard Functions

// Load health data on page load
document.addEventListener('DOMContentLoaded', function() {
    loadHealthData();
});

// Navigation Functions
function showDashboardSection(event) {
    if (event) event.preventDefault();
    hideAllSections();
    document.querySelector('.dashboard-layout main').style.display = 'block';
    document.querySelector('.right-sidebar').style.display = 'block';
    setActiveNav('nav-dashboard');
}

function showRecordsSection(event) {
    if (event) event.preventDefault();
    hideAllSections();
    document.getElementById('recordsSection').style.display = 'block';
    setActiveNav('nav-records');
    loadMedicalRecords();
}

function showChatSection(event) {
    if (event) event.preventDefault();
    hideAllSections();
    document.getElementById('chatSection').style.display = 'block';
    setActiveNav('nav-chat');
}

function showCalendarSection(event) {
    if (event) event.preventDefault();
    hideAllSections();
    document.getElementById('calendarSection').style.display = 'block';
    setActiveNav('nav-calendar');
    initializeCalendar();
}

function hideAllSections() {
    document.querySelector('.dashboard-layout main').style.display = 'none';
    document.querySelector('.right-sidebar').style.display = 'none';
    document.getElementById('recordsSection').style.display = 'none';
    document.getElementById('chatSection').style.display = 'none';
    document.getElementById('calendarSection').style.display = 'none';
}

function setActiveNav(navId) {
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    document.getElementById(navId)?.classList.add('active');
}

// Health Data Functions
function loadHealthData() {
    fetch('/api/health-info')
        .then(response => response.json())
        .then(data => {
            if (data.weight) {
                document.getElementById('displayWeight').textContent = data.weight + ' kg';
            }
            if (data.height) {
                document.getElementById('displayHeight').textContent = data.height + ' m';
            }
            if (data.blood_group) {
                document.getElementById('displayBloodGroup').textContent = data.blood_group;
            }
        })
        .catch(error => console.error('Error loading health data:', error));
}

function toggleHealthInfoEdit() {
    const modal = document.getElementById('healthModal');
    modal.classList.add('active');
    
    fetch('/api/health-info')
        .then(response => response.json())
        .then(data => {
            if (data.weight) document.getElementById('weightInput').value = data.weight;
            if (data.height) document.getElementById('heightInput').value = data.height;
            if (data.blood_group) document.getElementById('bloodGroupInput').value = data.blood_group;
        });
}

function closeHealthModal() {
    const modal = document.getElementById('healthModal');
    modal.classList.remove('active');
}

document.getElementById('healthInfoForm')?.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const healthData = {
        weight: document.getElementById('weightInput').value,
        height: document.getElementById('heightInput').value,
        blood_group: document.getElementById('bloodGroupInput').value
    };
    
    fetch('/api/health-info', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(healthData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Health information updated successfully!');
            loadHealthData();
            closeHealthModal();
        } else {
            alert('Error updating health information: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error updating health information');
    });
});

// Medical Records Functions
function loadMedicalRecords() {
    const container = document.getElementById('recordsContainer');
    container.innerHTML = '<div class="loading">Loading records...</div>';
    
    fetch('/api/medical-records')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.records && data.records.length > 0) {
                container.innerHTML = data.records.map(record => `
                    <div class="record-card">
                        <div class="record-icon">
                            <i class="fas fa-file-${record.file_type === 'pdf' ? 'pdf' : 'image'}"></i>
                        </div>
                        <div class="record-info">
                            <h4>${record.description || 'Medical Document'}</h4>
                            <p><i class="fas fa-calendar"></i> ${new Date(record.upload_date).toLocaleDateString()}</p>
                            <p><i class="fas fa-file"></i> ${record.file_type.toUpperCase()}</p>
                        </div>
                        <div class="record-actions">
                            <button class="btn btn-sm btn-primary" onclick="viewRecord('${record.id}')">
                                <i class="fas fa-eye"></i> View
                            </button>
                        </div>
                    </div>
                `).join('');
            } else {
                container.innerHTML = `
                    <div class="no-records">
                        <i class="fas fa-folder-open"></i>
                        <h3>No Medical Records</h3>
                        <p>Upload your medical documents to get started</p>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            container.innerHTML = '<div class="error">Error loading records</div>';
        });
}

function showUploadModal() {
    document.getElementById('uploadModal').classList.add('active');
}

function closeUploadModal() {
    document.getElementById('uploadModal').classList.remove('active');
    document.getElementById('uploadForm').reset();
}

document.getElementById('uploadForm')?.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    
    fetch('/user/upload-document', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Document uploaded successfully!');
            closeUploadModal();
            loadMedicalRecords();
        } else {
            alert('Error uploading document: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error uploading document');
    });
});

function viewRecord(recordId) {
    window.open(`/api/view-record/${recordId}`, '_blank');
}

// Chat Functions
function sendChatMessage(event) {
    event.preventDefault();
    
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message
    addChatMessage(message, 'user');
    input.value = '';
    
    // Show typing indicator
    const typingDiv = addTypingIndicator();
    
    // Send to backend
    fetch('/user/chat-assistant', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ symptoms: message })
    })
    .then(response => response.json())
    .then(data => {
        typingDiv.remove();
        
        if (data.success) {
            let response = data.response;
            
            if (data.is_emergency) {
                response = `<strong style="color: #ff4444;">⚠️ EMERGENCY DETECTED</strong><br>${response}`;
            }
            
            if (data.specializations && data.specializations.length > 0) {
                response += `<br><br><strong>Recommended Specialists:</strong><br>`;
                data.specializations.forEach(spec => {
                    response += `• ${spec}<br>`;
                });
                response += `<br><a href="/doctors" class="btn btn-sm btn-primary">Find a Doctor</a>`;
            }
            
            addChatMessage(response, 'bot');
        } else {
            addChatMessage('Sorry, I encountered an error. Please try again.', 'bot');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        typingDiv.remove();
        addChatMessage('Sorry, I encountered an error. Please try again.', 'bot');
    });
}

function addChatMessage(message, type) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (type === 'bot') {
        contentDiv.innerHTML = `<strong>Health Assistant:</strong><p>${message}</p>`;
    } else {
        contentDiv.innerHTML = `<strong>You:</strong><p>${message}</p>`;
    }
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addTypingIndicator() {
    const messagesContainer = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing';
    typingDiv.innerHTML = '<div class="message-content"><strong>Health Assistant:</strong><p>Typing...</p></div>';
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return typingDiv;
}

function clearChat() {
    if (confirm('Are you sure you want to clear the chat history?')) {
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = `
            <div class="message bot-message">
                <div class="message-content">
                    <strong>Health Assistant:</strong>
                    <p>Hello! I'm your AI health assistant. Describe your symptoms and I'll help analyze them and suggest appropriate specialists.</p>
                </div>
            </div>
        `;
    }
}

// Calendar Functions
let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();
let appointmentsData = [];

function initializeCalendar() {
    fetchAppointments();
}

function fetchAppointments() {
    fetch('/api/appointments')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                appointmentsData = data.appointments;
                renderCalendar();
            }
        })
        .catch(error => console.error('Error fetching appointments:', error));
}

function renderCalendar() {
    const calendar = document.getElementById('calendar');
    const monthYear = document.getElementById('currentMonthYear');
    
    const months = ['January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'];
    
    monthYear.textContent = `${months[currentMonth]} ${currentYear}`;
    
    const firstDay = new Date(currentYear, currentMonth, 1).getDay();
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    
    let html = '<div class="calendar-header">';
    ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].forEach(day => {
        html += `<div class="calendar-day-header">${day}</div>`;
    });
    html += '</div><div class="calendar-days">';
    
    // Empty cells for days before month starts
    for (let i = 0; i < firstDay; i++) {
        html += '<div class="calendar-day empty"></div>';
    }
    
    // Days of the month
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const hasAppointment = appointmentsData.some(apt => apt.appointment_date === dateStr);
        const isToday = new Date().toDateString() === new Date(currentYear, currentMonth, day).toDateString();
        
        html += `<div class="calendar-day ${isToday ? 'today' : ''} ${hasAppointment ? 'has-appointment' : ''}" 
                      onclick="showDayAppointments('${dateStr}')">
                    ${day}
                 </div>`;
    }
    
    html += '</div>';
    calendar.innerHTML = html;
}

function previousMonth() {
    currentMonth--;
    if (currentMonth < 0) {
        currentMonth = 11;
        currentYear--;
    }
    renderCalendar();
}

function nextMonth() {
    currentMonth++;
    if (currentMonth > 11) {
        currentMonth = 0;
        currentYear++;
    }
    renderCalendar();
}

function showDayAppointments(dateStr) {
    const dayAppointments = appointmentsData.filter(apt => apt.appointment_date === dateStr);
    
    if (dayAppointments.length > 0) {
        let message = `Appointments on ${dateStr}:\n\n`;
        dayAppointments.forEach(apt => {
            message += `• ${apt.symptoms} at ${apt.appointment_time || 'N/A'}\n`;
        });
        alert(message);
    }
}

// Service functions
function showDiagnostic() {
    showRecordsSection(new Event('click'));
}

function showDrugs() {
    showRecordsSection(new Event('click'));
}

function showTests() {
    showRecordsSection(new Event('click'));
}

// Doctor functions
function changeDoctor() {
    window.location.href = '/doctors';
}

function messageDoctor() {
    showChatSection(new Event('click'));
}

function callDoctor() {
    alert('Call feature coming soon!');
}

function openChat() {
    showChatSection(new Event('click'));
}

// Close modals when clicking outside
window.onclick = function(event) {
    const healthModal = document.getElementById('healthModal');
    const uploadModal = document.getElementById('uploadModal');
    
    if (event.target == healthModal) {
        closeHealthModal();
    }
    if (event.target == uploadModal) {
        closeUploadModal();
    }
}
