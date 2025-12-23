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
        prompt = f"""
        # 角色
        你是一位專門為初次見面的兩人尋找共同話題的社交專家。
        # 任務
        根據用戶 {user1_name} 和 {user2_name} 的興趣，生成問候語、共通話題、以及分別給兩人的專屬話題建議。
        # 上下文 (用戶資訊)
        * {user1_name} 的興趣是：{interests1}
        * {user2_name} 的興趣是：{interests2}
        # 輸出格式要求
        * **語言：請務必全程使用「繁體中文 (Traditional Chinese)」進行回覆。**
        * 請嚴格按照以下標籤輸出，不要改變標籤格式，也不要使用Markdown清單符號：
        [GREETING]
        (在這裡放置一句輕鬆的問候語，並介紹自己是「智能社交聊天助手」)
        [SHARED]
        (在這裡放置1-2個雙方都可能感興趣的共通話題)
        [FOR_{user1_name}]
        (在這裡放置2個建議 {user1_name} 可以問 {user2_name} 的話題)
        [FOR_{user2_name}]
        (在這裡放置2個建議 {user2_name} 可以問 {user1_name} 的話題)

        """
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return f"呼叫 API 時發生錯誤：{e}"
