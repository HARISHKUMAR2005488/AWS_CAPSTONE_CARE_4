// User Dashboard Functions

// Load health data on page load
document.addEventListener('DOMContentLoaded', function() {
    loadHealthData();
    loadMedicalRecordsDashboard();
    initializeCalendarDashboard();
});

// Toggle Floating Reminder Box
function toggleReminderBox() {
    const reminderBox = document.getElementById('floatingReminderBox');
    if (reminderBox.style.display === 'none' || reminderBox.style.display === '') {
        reminderBox.style.display = 'block';
    } else {
        reminderBox.style.display = 'none';
    }
}

// Toggle Floating Chat Box
function toggleChatBox() {
    const chatBox = document.getElementById('floatingChatBox');
    if (chatBox.style.display === 'none' || chatBox.style.display === '') {
        chatBox.style.display = 'flex';
    } else {
        chatBox.style.display = 'none';
    }
}

// Send Chat Message (Floating)
function sendChatMessageFloating(event) {
    event.preventDefault();
    
    const input = document.getElementById('chatInputFloating');
    const messagesContainer = document.getElementById('chatMessagesFloating');
    const userMessage = input.value.trim();
    
    if (!userMessage) return;
    
    // Add user message
    const userDiv = document.createElement('div');
    userDiv.className = 'message user-message';
    userDiv.innerHTML = `
        <div class="message-content">
            <strong>You:</strong>
            <p>${escapeHtml(userMessage)}</p>
        </div>
    `;
    messagesContainer.appendChild(userDiv);
    
    // Clear input
    input.value = '';
    
    // Show typing indicator
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing';
    typingDiv.innerHTML = `
        <div class="message-content">
            <strong>Assistant:</strong>
            <p><i class="fas fa-circle"></i> <i class="fas fa-circle"></i> <i class="fas fa-circle"></i> Analyzing...</p>
        </div>
    `;
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Send to backend
    fetch('/user/chat-assistant', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: userMessage })
    })
    .then(response => response.json())
    .then(data => {
        // Remove typing indicator
        typingDiv.remove();
        
        if (!data.success) {
            throw new Error(data.message || 'Unknown error');
        }
        
        // Add bot response
        const botDiv = document.createElement('div');
        botDiv.className = 'message bot-message';
        
        let responseHtml = `
            <div class="message-content">
                <strong>Health Assistant:</strong>
                <div class="response-text">${data.response}</div>
        `;
        
        // Add severity indicator for symptom analysis
        if (data.message_type === 'symptom_analysis' && data.severity_score) {
            const severityClass = data.severity_score >= 70 ? 'high' : data.severity_score >= 40 ? 'medium' : 'low';
            responseHtml += `
                <div class="severity-indicator severity-${severityClass}">
                    <i class="fas fa-heartbeat"></i> Severity: ${data.severity_score}/100
                </div>
            `;
        }
        
        // Add recommended specialists
        if (data.specializations && data.specializations.length > 0) {
            responseHtml += '<div class="specialists-list"><strong><i class="fas fa-user-md"></i> Recommended Specialists:</strong><ul>';
            data.specializations.forEach(spec => {
                responseHtml += `<li><strong>${spec.name}</strong>`;
                if (spec.reason) {
                    responseHtml += `<br><small>${spec.reason}</small>`;
                }
                responseHtml += '</li>';
            });
            responseHtml += '</ul></div>';
        }
        
        // Add health tips
        if (data.health_tips && data.health_tips.length > 0) {
            responseHtml += '<div class="health-tips"><strong><i class="fas fa-lightbulb"></i> Health Tips:</strong><ul>';
            data.health_tips.forEach(tip => {
                responseHtml += `<li>${tip}</li>`;
            });
            responseHtml += '</ul></div>';
        }
        
        // Add action buttons
        if (data.specializations && data.specializations.length > 0 && !data.is_emergency) {
            responseHtml += `
                <div class="chat-actions">
                    <a href="/doctors" class="btn-action">
                        <i class="fas fa-calendar-plus"></i> Book Appointment
                    </a>
                </div>
            `;
        }
        
        responseHtml += '</div>';
        botDiv.innerHTML = responseHtml;
        messagesContainer.appendChild(botDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    })
    .catch(error => {
        console.error('Error:', error);
        typingDiv.remove();
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message bot-message error-message';
        errorDiv.innerHTML = `
            <div class="message-content">
                <strong>Assistant:</strong>
                <p><i class="fas fa-exclamation-triangle"></i> ${error.message || 'Sorry, I encountered an error. Please try again or contact support if the issue persists.'}</p>
            </div>
        `;
        messagesContainer.appendChild(errorDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    });
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Fill chat input from suggestion chips
function fillChatInput(text) {
    const input = document.getElementById('chatInputFloating');
    input.value = text;
    input.focus();
}

// Clear chat history
function clearChat() {
    const messagesContainer = document.getElementById('chatMessagesFloating');
    messagesContainer.innerHTML = `
        <div class="message bot-message">
            <div class="message-content">
                <strong>Health Assistant:</strong>
                <p>Hello! I'm your AI health assistant. I can help you with:</p>
                <ul>
                    <li>Analyzing your symptoms</li>
                    <li>Recommending appropriate specialists</li>
                    <li>Answering health-related questions</li>
                    <li>Providing health tips and guidance</li>
                    <li>Helping you book appointments</li>
                </ul>
                <p><strong>How can I assist you today?</strong></p>
            </div>
        </div>
    `;
}

// Navigation Functions
function showDashboardSection(event) {
    if (event) event.preventDefault();
    hideAllSections();
    const mainContent = document.querySelector('.main-content');
    if (mainContent) mainContent.style.display = 'block';
    setActiveNav('nav-dashboard');
}

function showRecordsSection(event) {
    if (event) event.preventDefault();
    // Just stay on dashboard, records are already visible
    hideAllSections();
    const mainContent = document.querySelector('.main-content');
    if (mainContent) mainContent.style.display = 'block';
    setActiveNav('nav-records-calendar');
}

function showRecordsCalendarSection(event) {
    if (event) event.preventDefault();
    // Just stay on dashboard, records and calendar are already visible
    hideAllSections();
    const mainContent = document.querySelector('.main-content');
    if (mainContent) mainContent.style.display = 'block';
    setActiveNav('nav-records-calendar');
}

function showCalendarSection(event) {
    if (event) event.preventDefault();
    // Just stay on dashboard, calendar is already visible
    hideAllSections();
    const mainContent = document.querySelector('.main-content');
    if (mainContent) mainContent.style.display = 'block';
    setActiveNav('nav-records-calendar');
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
    document.querySelector('.main-content').style.display = 'none';
    const accountSection = document.getElementById('accountSection');
    const helpSection = document.getElementById('helpSection');
    if (accountSection) accountSection.style.display = 'none';
    if (helpSection) helpSection.style.display = 'none';
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
function loadMedicalRecordsDashboard() {
    const container = document.getElementById('recordsContainerDashboard');
    if (!container) return;
    
    container.innerHTML = '<div class="loading">Loading records...</div>';
    
    fetch('/api/medical-records')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.records && data.records.length > 0) {
                container.innerHTML = data.records.map(record => `
                    <div class="record-card-dashboard">
                        <div class="record-icon-dashboard">
                            <i class="fas fa-file-${record.file_type === 'pdf' ? 'pdf' : 'image'}"></i>
                        </div>
                        <div class="record-info-dashboard">
                            <h5>${record.description || 'Medical Document'}</h5>
                            <p><i class="fas fa-calendar"></i> ${new Date(record.upload_date).toLocaleDateString()}</p>
                        </div>
                    </div>
                `).join('');
            } else {
                container.innerHTML = `
                    <div class="no-records-compact">
                        <i class="fas fa-folder-open"></i>
                        <p>No Medical Records</p>
                        <button class="btn btn-sm btn-primary" onclick="showUploadModal()">Upload Document</button>
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
            loadMedicalRecordsDashboard();
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

// Dashboard Calendar Functions
let currentMonthDashboard = new Date().getMonth();
let currentYearDashboard = new Date().getFullYear();
let appointmentsDataDashboard = [];

function initializeCalendarDashboard() {
    fetchAppointmentsDashboard();
}

function fetchAppointmentsDashboard() {
    fetch('/api/appointments')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                appointmentsDataDashboard = data.appointments;
                renderCalendarDashboard();
            }
        })
        .catch(error => console.error('Error fetching appointments:', error));
}

function renderCalendarDashboard() {
    const calendar = document.getElementById('calendarDashboard');
    const monthYear = document.getElementById('currentMonthYearDashboard');
    
    if (!calendar || !monthYear) return;
    
    const months = ['January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'];
    
    monthYear.textContent = `${months[currentMonthDashboard]} ${currentYearDashboard}`;
    
    const firstDay = new Date(currentYearDashboard, currentMonthDashboard, 1).getDay();
    const daysInMonth = new Date(currentYearDashboard, currentMonthDashboard + 1, 0).getDate();
    
    let html = '<div class="calendar-header-days">';
    ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].forEach(day => {
        html += `<div class="calendar-day-name">${day}</div>`;
    });
    html += '</div><div class="calendar-days-grid">';
    
    // Empty cells for days before month starts
    for (let i = 0; i < firstDay; i++) {
        html += '<div class="calendar-day empty"></div>';
    }
    
    // Days of the month
    const today = new Date();
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${currentYearDashboard}-${String(currentMonthDashboard + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const appointmentsOnDay = appointmentsDataDashboard.filter(apt => apt.appointment_date === dateStr);
        const hasAppointment = appointmentsOnDay.length > 0;
        const isToday = today.getFullYear() === currentYearDashboard && 
                       today.getMonth() === currentMonthDashboard && 
                       today.getDate() === day;
        
        let classes = 'calendar-day';
        if (isToday) classes += ' today';
        if (hasAppointment) classes += ' has-appointment';
        
        html += `<div class="${classes}" onclick="showDayAppointments('${dateStr}')" title="${hasAppointment ? appointmentsOnDay.length + ' appointment(s)' : ''}">
                    <span class="day-number">${day}</span>
                    ${hasAppointment ? '<span class="appointment-dot"></span>' : ''}
                 </div>`;
    }
    
    html += '</div>';
    calendar.innerHTML = html;
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
    const answerText = element.querySelector('.faq-answer-text');
    const isActive = element.classList.contains('active');
    
    // Close all other FAQs in the same section
    const section = element.closest('.settings-section');
    if (section) {
        section.querySelectorAll('.faq-item-settings').forEach(item => {
            if (item !== element) {
                item.classList.remove('active');
                const otherAnswer = item.querySelector('.faq-answer-text');
                if (otherAnswer) otherAnswer.style.display = 'none';
            }
        });
    }
    
    // Toggle current FAQ
    element.classList.toggle('active');
    if (answerText) {
        answerText.style.display = isActive ? 'none' : 'block';
    }
}

function filterHelpTopics() {
    const searchValue = document.getElementById('helpSearch').value.toLowerCase();
    const faqItems = document.querySelectorAll('.faq-item-settings');
    const sections = document.querySelectorAll('.help-settings-container .settings-section');
    
    if (!searchValue) {
        // Show all items and sections
        faqItems.forEach(item => item.style.display = 'flex');
        sections.forEach(section => section.style.display = 'block');
        return;
    }
    
    faqItems.forEach(item => {
        const label = item.querySelector('.setting-info label');
        const answer = item.querySelector('.faq-answer-text');
        
        if (label && answer) {
            const question = label.textContent.toLowerCase();
            const answerText = answer.textContent.toLowerCase();
            
            if (question.includes(searchValue) || answerText.includes(searchValue)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        }
    });
    
    // Hide sections with no visible items
    sections.forEach(section => {
        const visibleItems = section.querySelectorAll('.faq-item-settings[style*="display: flex"], .faq-item-settings:not([style*="display: none"])');
        section.style.display = visibleItems.length > 0 ? 'block' : 'none';
    });
}
