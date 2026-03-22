# AnonChatAI

**AnonChatAI** is an intelligent, anonymous social matching platform driven by a simple mission: to connect people wherever they are—whether in schools, local communities, or any shared space. We believe that mealtime and leisure breaks are better shared. Our platform ensures that everyone has something meaningful to do and someone to talk to, turning solitary moments into opportunities for connection.

Powered by **Google Gemini AI**, it goes beyond simple matching by providing smart conversation starters to break the ice and facilitate meaningful interactions.

## 🌟 Key Features

- **Smart Matching**: Matches users based on implicit criteria like dining purpose, gender preference, and personality traits.
- **Anonymous Chat**: Real-time anonymous messaging system using WebSockets.
- **AI-Powered Icebreakers**: Uses **Gemini 2.5 Flash** with **JSON Structured Output** to ensure reliable, error-free parsing of user interests. Generates personalized greeting messages and shared discussion topics in a strict format.
- **Real-Time Contact Exchange**: Seamless, real-time contact exchange (LINE/Instagram) at the end of a chat. Both parties must agree, and the contact info is revealed instantly without manual page refreshing.
- **Feedback & Historical System**: Allows users to rate their partners and leave feedback after the chat ends. User data and feedback are securely preserved as historical records.
- **Admin Panel**: Secure, modern interface for administrators to monitor historical users, active chats, and review feedback records.

## 🛠️ Tech Stack

- **Backend**: Python, Flask, Flask-SocketIO
- **Database**: SQLite
- **AI**: Google Gemini API (gemini-2.5-flash)
- **Frontend**: HTML, Vanilla CSS, Bootstrap 5, AOS Animation Library

## 🚀 Installation & Setup

1. **Clone the repository** (or download the source code).

2. **Install dependencies**:
   ```bash
   pip install flask flask-socketio google-generativeai python-dotenv
   ```

3. **Set up Environment Variables**:
   It is highly recommended to configure sensitive keys via a `.env` file in the root directory. Create a `.env` file and add the following:
   
   ```env
   GEMINI_API_KEY=your_api_key_here
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your_secure_password
   ```

4. **Run the Application**:
   Navigate to the project root and run:
   ```bash
   python ./src/app.py
   ```

5. **Access the App**:
   Open your browser and go to `http://127.0.0.1:5000`.

## 🛡️ Admin Access

- **URL**: `http://127.0.0.1:5000/admin`
- **Credentials**: Uses the `ADMIN_USERNAME` and `ADMIN_PASSWORD` values defined in your `.env` file. If not set, it defaults to `admin` / `admin123`.
- **Security Warning**: For the most secure setup, you should always set these environment variables to a strong, unique password when deploying in a real environment!

## 📂 Project Structure

- `src/`: Contains the source code.
  - `app.py`: Main application entry point, routing, and WebSockets.
  - `social_agent.py`: AI logic wrapper connecting to Gemini API.
  - `templates/`: HTML templates with modern UI/UX design.
  - `static/`: Static assets (CSS, JS, images).

## 🤝 Use & Modify

This project is provided as an open-source example for educational and development purposes. **We welcome anyone to fork, modify, and continue developing this project!**

> [!NOTE]
> **Placeholder Data**: Some files (like `src/info.json`) currently contain placeholder tags (e.g., "XXX1", "Class 1"). Please update these identifiers with your own real data when deploying or adapting the project.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 AnonChatAI Team