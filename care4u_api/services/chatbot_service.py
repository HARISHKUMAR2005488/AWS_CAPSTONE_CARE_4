"""Lightweight NLP chatbot for symptom triage and specialist recommendation."""

import re


SYMPTOM_SPECIALIZATION_MAP = {
    'fever': 'General Physician',
    'cough': 'Pulmonologist',
    'cold': 'General Physician',
    'chest pain': 'Cardiologist',
    'headache': 'Neurologist',
    'skin rash': 'Dermatologist',
    'stomach pain': 'Gastroenterologist',
    'anxiety': 'Psychiatrist',
    'vision blur': 'Ophthalmologist',
    'joint pain': 'Orthopedist',
}


def _tokenize(text: str) -> set:
    return set(re.findall(r'[a-zA-Z]+', text.lower()))


def detect_intent(message: str) -> str:
    """Perform basic intent detection with keyword patterns."""
    text = message.lower().strip()

    if any(k in text for k in ['book', 'appointment', 'schedule']):
        return 'book_appointment'
    if any(k in text for k in ['emergency', 'urgent', 'severe', 'critical']):
        return 'emergency'
    if any(k in text for k in ['symptom', 'pain', 'fever', 'cough', 'headache', 'rash']):
        return 'symptom_analysis'
    if any(k in text for k in ['hello', 'hi', 'hey']):
        return 'greeting'
    return 'general'


def map_symptoms_to_specializations(message: str) -> list:
    """Return deduplicated specializations inferred from symptom phrases."""
    text = message.lower()
    specializations = []

    for symptom, specialist in SYMPTOM_SPECIALIZATION_MAP.items():
        if symptom in text:
            specializations.append({'symptom': symptom, 'specialization': specialist})

    seen = set()
    unique = []
    for entry in specializations:
        spec = entry['specialization']
        if spec in seen:
            continue
        seen.add(spec)
        unique.append(entry)

    return unique


def build_chatbot_response(message: str) -> dict:
    """Generate JSON-ready chatbot output."""
    intent = detect_intent(message)
    recommendations = map_symptoms_to_specializations(message)

    if intent == 'greeting':
        text = 'Hello. I can help analyze symptoms and suggest the right specialist.'
    elif intent == 'book_appointment':
        text = 'Please share symptoms and preferred date/time. I can suggest specialist type first.'
    elif intent == 'emergency':
        text = 'Potential emergency detected. Please seek immediate medical care or call emergency services.'
    elif intent == 'symptom_analysis':
        if recommendations:
            specs = ', '.join(item['specialization'] for item in recommendations)
            text = f'Based on your symptoms, consider consulting: {specs}.'
        else:
            text = 'Please provide a few more symptom details for better specialist recommendation.'
    else:
        text = 'I can help with symptom analysis, specialist guidance, and appointment preparation.'

    return {
        'intent': intent,
        'response': text,
        'recommendations': recommendations,
        'confidence': 0.82 if recommendations else 0.65,
    }
