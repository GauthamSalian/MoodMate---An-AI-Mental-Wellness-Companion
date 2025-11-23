# 🧠 MoodMate
### Your Agentic AI Companion for Mental Resilience


[![Hackathon Winner](https://img.shields.io/badge/🏆_Winner-2nd_Place_@_MindScape_2025-FFD700?style=for-the-badge)](https://github.com/GauthamSalian/MoodMate---An-AI-Mental-Wellness-Companion)
[![Tech Stack](https://img.shields.io/badge/Stack-React_|_FastAPI_|_AWS-blue?style=for-the-badge)](https://github.com/GauthamSalian/MoodMate---An-AI-Mental-Wellness-Companion)
[![AI Models](https://img.shields.io/badge/AI-IBM_Watsonx_|_HuggingFace-orange?style=for-the-badge)](https://github.com/GauthamSalian/MoodMate---An-AI-Mental-Wellness-Companion)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

> **MoodMate** is an intelligent, agentic mental wellness ecosystem designed to detect early signs of stress, analyze emotional patterns, and provide proactive support using advanced LLMs.

---

## 🏆 Achievement
**🥈 2nd Place Winner** at **MindScape Hackathon 2025**
* **Theme:** Mental Health Technology Support
* **Organized By:** BNMIT in association with **IBM SkillsBuild, 1M1B, and AWS**.

---

## 📸 System Overview

![Dashboard Preview](https://via.placeholder.com/800x400?text=MoodMate+Dashboard+Preview)

---

## ✨ Core Features

### 🧠 1. The "Agentic" Core
Unlike passive chatbots, MoodMate is **proactive**.
* **Goal-Oriented Conversations:** The bot remembers previous sessions and nudges users toward their defined wellness goals.
* **Contextual Awareness:** Powered by `Mistral-Small-24B`, it understands nuance, sarcasm, and deep emotional context.

### 📊 2. Deep Emotional Analytics
* **Smart Journaling:** Write naturally. Our NLP engine highlights emotional keywords and assigns a "Sentiment Score" to every entry.
* **The Emotion Calendar:** A visual heatmap of your mental state over weeks and months, helping you identify triggers.
* **Risk Detection:** Analyzes external data (e.g., Tweets) to flag high-risk content using **IBM Granite Guardian**.

### 🛡️ 3. Actionable Wellness
* **Habit Builder:** AI-suggested micro-habits to break negative loops (e.g., "Replace doom-scrolling with 2 minutes of breathing").
* **Psychologist Network:** A commission-based booking system connecting high-risk users with certified professionals.
* **Security First:** Enterprise-grade `bcrypt` hashing and `JWT` session management.

---

## 🏗️ Technical Architecture

MoodMate is built on a decoupled **Microservices** architecture hosted on **AWS**.

### **The AI Pipeline**
| Component | Model / Technology | Purpose |
| :--- | :--- | :--- |
| **Emotion Recognition** | `j-hartmann/emotion-english-distilroberta-base` | Quantifying user sentiment from journal entries. |
| **Risk Analysis** | `ibm-granite/granite-guardian-3.2-3b` | Detecting self-harm or severe distress markers in text. |
| **Conversational Core** | `mistralai/mistral-small-3.2-24b-instruct` | Powering the empathetic, reasoning chatbot via OpenRouter. |

### **The Cloud Infrastructure (AWS)**
* **Compute:** `AWS EC2` (T3 instances) hosting the FastAPI backend and AI inference workers.
* **Database:** `AWS DynamoDB` (NoSQL) for high-speed storage of journals, chat history, and user profiles.
* **Storage:** `AWS S3` for storing static assets and generated reports.
* **Orchestration:** `APScheduler` for running background tweet analysis jobs.

---

## 🛠️ Tech Stack

**Frontend**
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB) ![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat&logo=tailwind-css&logoColor=white) ![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white)

**Backend & AI**
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi) ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) ![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=flat&logo=huggingface&logoColor=black) ![IBM Watsonx](https://img.shields.io/badge/IBM_Watsonx-052FAD?style=flat&logo=ibm&logoColor=white)

**Infrastructure**
![AWS](https://img.shields.io/badge/AWS-232F3E?style=flat&logo=amazon-aws&logoColor=white) ![DynamoDB](https://img.shields.io/badge/DynamoDB-4053D6?style=flat&logo=amazon-dynamodb&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

---

## 🚀 Getting Started

### Prerequisites
* Node.js v18+
* Python 3.10+
* AWS Credentials (configured in `.env`)

### Installation

**1. Clone the Repository**
```bash
git clone [https://github.com/GauthamSalian/MoodMate---An-AI-Mental-Wellness-Companion.git](https://github.com/GauthamSalian/MoodMate---An-AI-Mental-Wellness-Companion.git)
cd MoodMate---An-AI-Mental-Wellness-Companion
````

**2. Backend Setup (FastAPI)**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

**3. Frontend Setup (React)**

```bash
cd frontend
npm install
npm run dev
```

-----

## 🔮 Future Roadmap

  - [ ] **Live Tele-Therapy (WebRTC):** Implementing secure, peer-to-peer video consultations between patients and psychologists using **WebRTC** and Socket.io for signaling.
  - [ ] **Voice Journaling:** Integration of Whisper AI for speech-to-text sentiment analysis.
  - [ ] **RAG Integration:** Giving the bot long-term memory using Vector Databases (Pinecone/ChromaDB).
  - [ ] **Mobile App:** React Native port for iOS/Android.

-----

## 👨‍💻 Contributors

  * **Gautham Salian** - *Lead Engineer & AI Architect*

-----

### 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.

```
```
