// User Dashboard Functions

// Load health data on page load
document.addEventListener('DOMContentLoaded', function() {
    loadHealthData();
});

// Right Sidebar Tab Switching
function switchRightTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.closest('.tab-btn').classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(tabName + '-tab').classList.add('active');
}

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

function showCalendarSection(event) {
    if (event) event.preventDefault();
    hideAllSections();
    document.getElementById('calendarSection').style.display = 'block';
    setActiveNav('nav-calendar');
    initializeCalendar();
}

function showAccountSection(event) {
    if (event) event.preventDefault();
    hideAllSections();
    document.getElementById('accountSection').style.display = 'block';
    setActiveNav(null); // No nav item active for footer items
}

function showHelpCenter(event) {
    if (event) event.preventDefault();
    hideAllSections();
    document.getElementById('helpSection').style.display = 'block';
    setActiveNav(null);
}

function hideAllSections() {
    document.querySelector('.dashboard-layout main').style.display = 'none';
    document.querySelector('.right-sidebar').style.display = 'none';
    document.getElementById('recordsSection').style.display = 'none';
    document.getElementById('calendarSection').style.display = 'none';
    document.getElementById('accountSection').style.display = 'none';
    document.getElementById('helpSection').style.display = 'none';
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
                response = `<strong style="color: #ff4444;">⚠️ EMERGENCY</strong><br>${response}`;
            }
            
            if (data.specializations && data.specializations.length > 0) {
                response += `<br><br><strong>Recommended:</strong><br>`;
                data.specializations.forEach(spec => {
                    response += `• ${spec}<br>`;
                });
                response += `<br><a href="/doctors" style="color: #5FEABE; text-decoration: underline;">Find a Doctor</a>`;
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
        contentDiv.innerHTML = `<strong>Assistant:</strong><p>${message}</p>`;
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
    typingDiv.innerHTML = '<div class="message-content"><strong>Assistant:</strong><p>Typing...</p></div>';
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
                    <strong>Assistant:</strong>
                    <p>Hello! Describe your symptoms and I'll help analyze them and suggest appropriate specialists.</p>
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
    // Switch to chat tab in right sidebar
    document.querySelectorAll('.tab-btn').forEach((btn, index) => {
        btn.classList.remove('active');
        if (index === 1) btn.classList.add('active'); // Chat tab
    });
    document.querySelectorAll('.tab-content').forEach((content, index) => {
        content.classList.remove('active');
        if (index === 1) content.classList.add('active'); // Chat content
    });
}

function callDoctor() {
    alert('Call feature coming soon!');
}

function openChat() {
    messageDoctor();
}

// Close modals when clicking outside
window.onclick = function(event) {
    const healthModal = document.getElementById('healthModal');
    const uploadModal = document.getElementById('uploadModal');
    const settingsModal = document.getElementById('settingsModal');
    const editProfileModal = document.getElementById('editProfileModal');
    const changePasswordModal = document.getElementById('changePasswordModal');
    
    if (event.target == healthModal) {
        closeHealthModal();
    }
    if (event.target == uploadModal) {
        closeUploadModal();
    }
    if (event.target == settingsModal) {
        closeSettingsModal();
    }
    if (event.target == editProfileModal) {
        closeEditProfileModal();
    }
    if (event.target == changePasswordModal) {
        closeChangePasswordModal();
    }
}

// Settings Modal Functions
function showSettingsModal(event) {
    if (event) event.preventDefault();
    document.getElementById('settingsModal').classList.add('active');
    loadSettings();
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
}

function loadSettings() {
    // Load settings from localStorage
    const emailNotif = localStorage.getItem('emailNotif') !== 'false';
    const smsNotif = localStorage.getItem('smsNotif') === 'true';
    const shareData = localStorage.getItem('shareData') !== 'false';
    const theme = localStorage.getItem('theme') || 'light';
    
    document.getElementById('emailNotif').checked = emailNotif;
    document.getElementById('smsNotif').checked = smsNotif;
    document.getElementById('shareData').checked = shareData;
    document.getElementById('themeSelect').value = theme;
}

function saveSettings() {
    const emailNotif = document.getElementById('emailNotif').checked;
    const smsNotif = document.getElementById('smsNotif').checked;
    const shareData = document.getElementById('shareData').checked;
    const theme = document.getElementById('themeSelect').value;
    
    localStorage.setItem('emailNotif', emailNotif);
    localStorage.setItem('smsNotif', smsNotif);
    localStorage.setItem('shareData', shareData);
    localStorage.setItem('theme', theme);
    
    alert('Settings saved successfully!');
    closeSettingsModal();
}

// Edit Profile Modal Functions
function showEditProfileModal() {
    document.getElementById('editProfileModal').classList.add('active');
}

function closeEditProfileModal() {
    document.getElementById('editProfileModal').classList.remove('active');
}

document.getElementById('editProfileForm')?.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData();
    formData.append('email', document.getElementById('editEmail').value);
    formData.append('phone', document.getElementById('editPhone').value);
    
    const profilePicture = document.getElementById('editProfilePicture').files[0];
    if (profilePicture) {
        formData.append('profile_picture', profilePicture);
    }
    
    fetch('/api/update-profile', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Profile updated successfully!');
            closeEditProfileModal();
            location.reload();
        } else {
            alert('Error updating profile: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error updating profile');
    });
});

// Change Password Modal Functions
function showChangePasswordModal() {
    document.getElementById('changePasswordModal').classList.add('active');
}

function closeChangePasswordModal() {
    document.getElementById('changePasswordModal').classList.remove('active');
    document.getElementById('changePasswordForm').reset();
}

document.getElementById('changePasswordForm')?.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (newPassword !== confirmPassword) {
        alert('New passwords do not match!');
        return;
    }
    
    if (newPassword.length < 6) {
        alert('Password must be at least 6 characters long!');
        return;
    }
    
    fetch('/api/change-password', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Password changed successfully!');
            closeChangePasswordModal();
        } else {
            alert('Error: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error changing password');
    });
});

// Help Center Functions
function toggleFAQ(element) {
    element.classList.toggle('active');
}

function filterHelpTopics() {
    const searchValue = document.getElementById('helpSearch').value.toLowerCase();
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question span').textContent.toLowerCase();
        const answer = item.querySelector('.faq-answer p').textContent.toLowerCase();
        
        if (question.includes(searchValue) || answer.includes(searchValue)) {
            item.style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
}
