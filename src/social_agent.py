import google.generativeai as genai
import os

class SocialAgent:
    def __init__(self, api_key=None):
        self.api_key = api_key
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
            except Exception as e:
                print(f"Error configuring Gemini API: {e}")
        else:
            print("Warning: Gemini API Key not provided.")

    def generate_topics(self, user1_name, interests1, user2_name, interests2):
        if not self.api_key:
            return "錯誤：Gemini API 金鑰未設定。"
        
        model = genai.GenerativeModel('gemini-2.5-flash')
        # JSON Schema for the output
        prompt = f"""
        # Role
        You are a social expert connecting two strangers.
        
        # Task
        Generate a JSON object containing a greeting, shared topics, and individual topic suggestions based on user interests.

        # User Info
        * {user1_name}: {interests1}
        * {user2_name}: {interests2}

        # JSON Output Format (Strict)
        Return ONLY valid JSON with this structure:
        {{
            "greeting": "Traditional Chinese greeting...",
            "shared_topics": ["Topic 1", "Topic 2"],
            "user1_topics": ["Topic for User 1 to ask", "Topic for User 1 to ask"],
            "user2_topics": ["Topic for User 2 to ask", "Topic for User 2 to ask"]
        }}
        
        **Language Rule**: All values inside the JSON MUST be in Traditional Chinese.
        """
        try:
            # Generate content using the new model behavior
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return response.text
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return f"呼叫 API 時發生錯誤：{e}"
