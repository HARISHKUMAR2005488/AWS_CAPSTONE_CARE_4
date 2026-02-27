class AIService:
    @staticmethod
    def analyze_symptoms(symptoms_text):
        """
        Rule-based symptom analysis engine.
        Identifies emergency keywords and suggests specializations.
        """
        symptoms_lower = symptoms_text.lower()
        
        emergency_keywords = {
            "chest pain": 100, "heart attack": 100, "stroke": 100,
            "difficulty breathing": 90, "unconscious": 100, "severe bleeding": 90,
            "anaphylaxis": 100, "poisoning": 90, "suicide": 100
        }
        
        specialization_keywords = {
            "Cardiology": ["chest", "heart", "palpitation", "pressure"],
            "Neurology": ["headache", "dizzy", "faint", "seizure", "numbness"],
            "Orthopedics": ["bone", "joint", "back", "knee", "fracture"],
            "Dermatology": ["skin", "rash", "itch", "bump"],
            "Gastroenterology": ["stomach", "pain", "digest", "vomit"],
            "General": []
        }
        
        is_emergency = False
        severity_score = 0
        recommended_specialist = "General Practice"
        
        # Check emergencies
        for key, urgency in emergency_keywords.items():
            if key in symptoms_lower:
                is_emergency = True
                severity_score = max(severity_score, urgency)
        
        if not is_emergency:
            # Simple keyword matching for specialization
            max_matches = 0
            for spec, keywords in specialization_keywords.items():
                matches = sum(1 for k in keywords if k in symptoms_lower)
                if matches > max_matches:
                    max_matches = matches
                    recommended_specialist = spec
            
            severity_score = min(max_matches * 10 + 20, 80)

        response_text = ""
        if is_emergency:
            response_text = "🚨 CRITICAL: Your symptoms indicate a possible medical emergency. Please visit the nearest ER immediately."
        else:
            response_text = f"Based on your symptoms, we recommend consulting a {recommended_specialist}."

        return {
            "is_emergency": is_emergency,
            "severity_score": severity_score,
            "specializations": [{"name": recommended_specialist}],
            "response": response_text
        }
