# examples/vapi_integration_mock.py
# Пример интеграции с голосовыми агентами (Vapi/Retell AI)
# Этот файл демонстрирует, как можно использовать логику из src/app.py
# для создания агента, который будет обрабатывать голосовые запросы.

import json
from ..src.app import AIAgent

# Инициализация агента
agent = AIAgent()

def handle_vapi_webhook(payload: dict):
    """
    Обработчик входящего вебхука от Vapi или Retell AI.
    """
    call_status = payload.get("status")
    
    if call_status == "conversation_update":
        # Извлекаем последний текст, произнесенный пользователем
        transcript = payload.get("transcript", "")
        
        if not transcript:
            return {"response": "No speech detected."}

        print(f"User said: {transcript}")
        
        # Передаем запрос нашему основному AI Agent
        agent_response = agent.process_request(transcript)
        
        # Формируем ответ для Vapi/Retell AI
        # В реальной интеграции это будет JSON-ответ, который Vapi/Retell AI
        # преобразует в голос.
        response_text = agent_response["response"]
        
        return {
            "response": response_text,
            "action": "reply" # Указываем, что агент должен ответить
        }
    
    elif call_status == "call_started":
        return {
            "response": "Hello! Thank you for calling NovaPay support. How can I help you today?",
            "action": "reply"
        }
    
    return {"response": "Call ended. Goodbye.", "action": "end_call"}

# Пример использования (симуляция вебхука)
mock_payload_start = {"status": "call_started"}
mock_payload_query = {"status": "conversation_update", "transcript": "I need help with my last payment."}

print("\n--- Simulating Call Start ---")
print(handle_vapi_webhook(mock_payload_start))

print("\n--- Simulating User Query ---")
print(handle_vapi_webhook(mock_payload_query))
