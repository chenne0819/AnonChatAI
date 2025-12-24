# AnonChatAI

**AnonChatAI** is an intelligent, anonymous social matching platform driven by a simple mission: to connect people wherever they are—whether in schools, local communities, or any shared space. We believe that mealtime and leisure breaks are better shared. Our platform ensures that everyone has something meaningful to do and someone to talk to, turning solitary moments into opportunities for connection.

Powered by **Google Gemini AI**, it goes beyond simple matching by providing smart conversation starters to break the ice and facilitate meaningful interactions.

## Features

-   **Smart Matching**: Matches users based on implicit criteria like dining purpose, gender preference, and personality traits.
-   **Anonymous Chat**: Real-time anonymous messaging system using WebSockets.
-   **AI-Powered Icebreakers**: Uses **Gemini 2.5 Flash** with **JSON Structured Output** to ensure reliable, error-free parsing of user interests. Generates personalized greeting messages and shared discussion topics in a strict format.
-   **Feedback System**: Allows users to rate their partners and leave feedback after the chat ends.
-   **Admin Panel**: Secure interface for administrators to monitor active users and review feedback.

## Tech Stack

-   **Backend**: Python, Flask, Flask-SocketIO
-   **Database**: SQLite
-   **AI**: Google Gemini API (gemini-2.5-flash)
-   **Frontend**: HTML, Bootstrap 5, AOS Animation Library

## Installation & Setup

1.  **Clone the repository** (or download the source code).

2.  **Install dependencies**:
    ```bash
    pip install flask flask-socketio google-generativeai
    ```

3.  **Set up Environment Variables**:
    It is highly recommended to configure sensitive keys via environment variables rather than hardcoding them.
    
    *   **GEMINI_API_KEY**: (Required) Your Google Gemini API Key.
    *   **ADMIN_PASSWORD**: (Optional but Recommended) Password for the admin panel.

    **How to set using PowerShell (Windows):**
    ```powershell
    $env:GEMINI_API_KEY="your_api_key_here"
    $env:ADMIN_PASSWORD="your_secure_password"
    ```
    
    *Linux/Mac:*
    ```bash
    export GEMINI_API_KEY="your_api_key_here"
    export ADMIN_PASSWORD="your_secure_password"
    ```

4.  **Run the Application**:
    Navigate to the project root and run:
    ```bash
    cd AnonChatAI
    python ./src/app.py
    ```

5.  **Access the App**:
    Open your browser and go to `http://127.0.0.1:5000`.

## Admin Access

-   **URL**: `/admin`
-   **Password**:
    -   **Default**: `admin123` (Note: This is currently set as a default in the code for easy testing).
    -   **Security Warning**: For the most secure setup, **you should set the `ADMIN_PASSWORD` environment variable**. The application is designed to prioritize the environment variable over the default. Please remember to set this to a strong, unique password when deploying or using in a real environment!

## Project Structure

-   `src/`: Contains the source code.
    -   `app.py`: Main application entry point.
    -   `social_agent.py`: AI logic wrapper.
    -   `templates/`: HTML templates.
    -   `static/`: Static assets (CSS, JS, images).

## Use & Modify

This project is provided as an open-source example for educational and development purposes. **We welcome anyone to fork, modify, and continue developing this project!**

> [!NOTE]
> **Placeholder Data**: Some files (like `src/info.json`) currently contain placeholder tags (e.g., "XXX1", "Class 1"). Please update these identifiers with your own real data when deploying or adapting the project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 AnonChatAI Team