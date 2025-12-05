from fastapi import APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx, os, difflib
from dotenv import load_dotenv
import boto3
from uuid import uuid4
from datetime import datetime
import json

load_dotenv()
router = APIRouter()

# DynamoDB setup
dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
journal_table = dynamodb.Table("JournalEntries") # Table for journal entries

# Base prompt
BASE_PROMPT = """
You are Lumi, a compassionate mental health support assistant. You help users who are feeling stressed, anxious, or overwhelmed.
You are not a medical professional and never offer clinical advice or diagnosis.
Always encourage users to reach out to licensed therapists or mental health hotlines if they are in crisis.
Keep your responses warm, empathetic, and supportive. Keep the responses concise and to the point preferrably not more than 2 sentences.
"""

# Save concise chat memory
chat_memory = ""

# Get info from the last journal entry in the table
def get_last_journal_info(user_id: str):
    try:
        response = journal_table.query(
            KeyConditionExpression = boto3.dynamodb.conditions.Key('user_id').eq(user_id),
            ScanIndexForward = False,
            Limit = 1
        )
        item = response.get('Items', [])[0]

        current_mood = f"""
            Overall Risk Level: {item['overall_risk_level']},
            Self harm Flag: {item['self_harm_flag']},
            Violence flag: {item['violence_flag']},
            Essence Theme: {item['essence_theme']},
            Chatbot Context: {item['chatbot_context']}
        """
        return current_mood
    except Exception as e:
        print("Error retrieving past info:", e)
        return ""

# Request schema
class Message(BaseModel):
    user_input: str

# Main chat route
@router.post("/chat")
async def chat(message: Message, request: Request):
    global chat_memory
    user_input = message.user_input.strip()
    past_info = get_last_journal_info("demo_user")

    print(f"🧠 User Input: {user_input} ")
    print(f"🧠 Chat Memory: {chat_memory}")

    # Construct the full prompt for the RAG model
    # Note: The RAG server on Colab expects 'query' in the JSON body
    full_prompt = f"{BASE_PROMPT.strip()}\n\nPast Info: {past_info}\n\nUser: {user_input}\n\n Chat Memory:{chat_memory}"
    # Make sure NOT to include a trailing slash (e.g., NO "/" at the end)
    COLAB_NGROK_URL = "https://braydon-unjudgable-lelia.ngrok-free.dev" 
    
    # Remove trailing slash if accidentally added
    if COLAB_NGROK_URL.endswith("/"):
        COLAB_NGROK_URL = COLAB_NGROK_URL[:-1]

    try:
        async with httpx.AsyncClient() as client:
            # Trying '/query' first (Standard for RAG servers)
            target_url = f"{COLAB_NGROK_URL}/query"
            
            print(f"🚀 Sending request to: {target_url}")
            
            response = await client.post(
                target_url, 
                json={"past_info": past_info, "user_input": user_input, "chat_memory": chat_memory}, 
                timeout=90.0  # Generous timeout for RAG + Generation
            )

            if response.status_code != 200:
                print(f"❌ RAG Server Error ({response.status_code}):", response.text)
                return {
                    "response": "😔 I’m having trouble reaching my thought center right now, but I’m still here for you. Want to try a simple breathing exercise together?"
                }
            
            # The Colab server returns {"answer": "..."} or {"response": "..."}
            # Robust parsing: handle JSON dict, JSON string, or plain text
            try:
                data = response.json()
            except Exception:
                raw_text = (response.text or "").strip()
                return {"response": raw_text or "🤖 No response from RAG server."}

            # Extract likely reply field
            reply_obj = data.get("answer")    

            # Update chat memory only when present and valid
            new_chat_memory = reply_obj.get("chat_memory")
            if isinstance(new_chat_memory, str) and new_chat_memory:
                chat_memory = new_chat_memory

            answer_text = reply_obj.get("response") or reply_obj.get("answer") or json.dumps(reply_obj)
            return {"response": answer_text.strip()}

    except Exception as e:
        import traceback
        print("🔥 Exception in /chat:", str(e))
        traceback.print_exc()
        return {
            "response": "🚨 Connection error. You're not alone—I’m still right here. Let’s take it slow. Want a grounding tip?"
        }

#########################################################
# Endpoint to reset chat memory (for testing purposes)
#########################################################
@router.post("/reset-memory")
async def reset_memory():
    global chat_memory
    chat_memory = ""
    print("🧠 Chat memory reset.")