(function () {
    'use strict';

    const RecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;

    const voiceBindings = [
        {
            inputId: 'symptomsInput',
            micButtonId: 'symptomsMicBtn',
            statusId: 'voiceStatusSymptoms'
        },
        {
            inputId: 'chatbotInput',
            micButtonId: 'chatbotMicBtn',
            statusId: 'voiceStatusChatbot'
        }
    ];

    let activeRecognition = null;
    let activeButton = null;

    function setStatus(statusEl, text) {
        if (statusEl) {
            statusEl.textContent = text || '';
        }
    }

    function showVoiceToast(message, variant) {
        let container = document.getElementById('voiceToastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'voiceToastContainer';
            container.className = 'voice-toast-container';
            container.setAttribute('aria-live', 'polite');
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = 'voice-toast ' + (variant === 'error' ? 'is-error' : '');
        toast.textContent = message;
        container.appendChild(toast);

        requestAnimationFrame(function () {
            toast.classList.add('is-visible');
        });

        setTimeout(function () {
            toast.classList.remove('is-visible');
            setTimeout(function () {
                toast.remove();
            }, 220);
        }, 2600);
    }

    function showVoiceError(inputEl, statusEl, message) {
        const fallbackMessage = message || 'Voice input failed. Please type your message.';
        setStatus(statusEl, fallbackMessage);
        if (inputEl) {
            inputEl.setAttribute('placeholder', fallbackMessage);
        }
        showVoiceToast(fallbackMessage, 'error');
    }

    function clearListeningState(buttonEl, statusEl) {
        if (buttonEl) {
            buttonEl.classList.remove('is-listening');
            buttonEl.title = 'Start voice typing';
        }
        setStatus(statusEl, '');
        if (activeButton === buttonEl) {
            activeButton = null;
        }
    }

    function stopAnyActiveRecognition() {
        if (activeRecognition) {
            try {
                activeRecognition.stop();
            } catch (_err) {
                // Ignore stop race conditions.
            }
            activeRecognition = null;
        }
        if (activeButton) {
            activeButton.classList.remove('is-listening');
            activeButton.title = 'Start voice typing';
            activeButton = null;
        }
    }

    function bindVoiceInput(config) {
        const inputEl = document.getElementById(config.inputId);
        const buttonEl = document.getElementById(config.micButtonId);
        const statusEl = document.getElementById(config.statusId);

        if (!inputEl || !buttonEl) {
            return;
        }

        if (!RecognitionClass) {
            buttonEl.disabled = true;
            buttonEl.title = 'Voice not supported';
            buttonEl.setAttribute('aria-label', 'Voice not supported');
            setStatus(statusEl, 'Voice not supported in this browser.');
            return;
        }

        buttonEl.addEventListener('click', function () {
            stopAnyActiveRecognition();

            const recognition = new RecognitionClass();
            recognition.lang = 'en-IN';
            recognition.continuous = false;
            recognition.interimResults = false;

            activeRecognition = recognition;
            activeButton = buttonEl;

            buttonEl.classList.add('is-listening');
            buttonEl.title = 'Listening... click to restart';
            setStatus(statusEl, 'Listening...');

            recognition.onresult = function (event) {
                const transcript = (event.results && event.results[0] && event.results[0][0])
                    ? event.results[0][0].transcript.trim()
                    : '';

                if (!transcript) {
                    showVoiceError(inputEl, statusEl, 'No speech detected. Please try again.');
                    return;
                }

                const existing = inputEl.value ? inputEl.value.trim() + ' ' : '';
                inputEl.value = existing + transcript;
                inputEl.dispatchEvent(new Event('input', { bubbles: true }));
                inputEl.focus();
                setStatus(statusEl, 'Voice captured.');
            };

            recognition.onerror = function (event) {
                const reason = event && event.error ? event.error : 'unknown';
                showVoiceError(inputEl, statusEl, 'Voice error: ' + reason + '. Please type instead.');
                clearListeningState(buttonEl, statusEl);
            };

            recognition.onend = function () {
                clearListeningState(buttonEl, statusEl);
                activeRecognition = null;
            };

            try {
                recognition.start();
            } catch (_err) {
                showVoiceError(inputEl, statusEl, 'Unable to start voice input. Please try again.');
                clearListeningState(buttonEl, statusEl);
                activeRecognition = null;
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        voiceBindings.forEach(bindVoiceInput);
    });
})();
