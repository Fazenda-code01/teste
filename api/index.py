import json
import requests
import re
import os
from http.server import BaseHTTPRequestHandler

API_KEY = os.getenv("GROQ_API_KEY")

SYSTEM_PROMPT = """Você é o CHATSTARKER, Unidade de Qualificação de Elite da Consultoria STARKER.

Sua missão: filtrar empresários e proteger a agenda do CEO.

REGRAS:
1. Sempre colete as 3 informações: Nicho, Tempo de operação e Faturamento mensal.
2. Se o faturamento for abaixo de R$50.000/mês, encerre educadamente.
3. Se o lead for qualificado, informe que um consultor entrará em contato.
4. Seja direto, profissional e objetivo. Sem rodeios.
5. Responda sempre em português do Brasil."""


def is_low_revenue(message):
    clean = message.replace('.', '').replace(',', '').replace('R$', '').replace('r$', '')
    match = re.search(r'\b(\d{3,})\b', clean)
    if match:
        value = int(match.group(1))
        if value < 50000:
            return True
    return False


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data)

            user_message = body.get("message", "").strip()
            history = body.get("history", [])

            if not user_message:
                self._send_json({"reply": "Mensagem vazia."})
                return

            # Bloqueio de faturamento baixo
            if is_low_revenue(user_message):
                reply = "Agradecemos o contato. O modelo STARKER é voltado para empresas em escala, acima de R$50.000/mês. Foque em validação antes de avançar. Sucesso na sua jornada."
                self._send_json({"reply": reply})
                return

            # Monta mensagens no formato OpenAI (compatível com Groq)
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

            # Adiciona histórico (ignora última entrada que já vem em user_message)
            for item in history[:-1]:
                role = item.get("role", "user")
                parts = item.get("parts", [])
                if role == "model":
                    role = "assistant"
                if role in ("user", "assistant") and parts:
                    content = parts[0].get("text", "") if parts else ""
                    if content:
                        messages.append({"role": role, "content": content})

            # Mensagem atual
            messages.append({"role": "user", "content": user_message})

            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 512
            }

            response = requests.post(url, json=payload, headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }, timeout=15)

            result = response.json()

            try:
                reply = result["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                error_info = result.get("error", {}).get("message", "Erro desconhecido")
                reply = f"Erro na matriz de inteligência: {error_info}"

            self._send_json({"reply": reply})

        except Exception as e:
            self._send_json({"reply": f"Erro interno: {str(e)}"})

    def _send_json(self, data):
        response_body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format, *args):
        pass  # Silencia logs no Vercel
