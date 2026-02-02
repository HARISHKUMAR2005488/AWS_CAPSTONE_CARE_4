// User Dashboard Functions

// Load health data on page load
document.addEventListener('DOMContentLoaded', function() {
    loadHealthData();
});

// Load health information
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

// Toggle health info edit modal
function toggleHealthInfoEdit() {
    const modal = document.getElementById('healthModal');
    modal.classList.add('active');
    
    // Load current values
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

// Save health information
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

// Doctor functions
function changeDoctor() {
    window.location.href = '/doctors';
}

function messageDoctor() {
    alert('Chat feature coming soon!');
}

function callDoctor() {
    alert('Call feature coming soon!');
}

function openChat() {
    alert('Chat feature coming soon!');
}

// Service functions
function showDiagnostic() {
    alert('Diagnostic records feature coming soon!');
}

function showDrugs() {
    alert('Drugs archive feature coming soon!');
}

function showTests() {
    alert('Tests feature coming soon!');
}

function showRecordsSection() {
    alert('Medical records feature coming soon!');
}

function editAppointment(appointmentId) {
    alert('Edit appointment feature coming soon! Appointment ID: ' + appointmentId);
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('healthModal');
    if (event.target == modal) {
        closeHealthModal();
    }
}
