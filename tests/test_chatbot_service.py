"""Basic unit tests for chatbot intent logic."""

from care4u_api.services.chatbot_service import build_chatbot_response, detect_intent


def test_detect_intent_for_booking():
    assert detect_intent('I want to book an appointment') == 'book_appointment'


def test_symptom_mapping_returns_specialization():
    output = build_chatbot_response('I have fever and cough for 2 days')
    assert output['intent'] == 'symptom_analysis'
    assert len(output['recommendations']) > 0
