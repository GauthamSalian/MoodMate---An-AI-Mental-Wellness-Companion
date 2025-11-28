from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from typing import List
import os
from dotenv import load_dotenv
from uuid import uuid4
import boto3
import datetime
from decimal import Decimal
load_dotenv()
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai import APIClient
import json

###development stage(switch with router after creation)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
#####################################################


#IBM WatsonX######################################
credentials = Credentials(
    url = "https://eu-de.ml.cloud.ibm.com",
    api_key = os.getenv("WATSONX_API_KEY")
)
client = APIClient(credentials)

reframing_model = ModelInference(
    model_id="mistralai/mistral-medium-2505",
    credentials=credentials,
    project_id="1cb8c38f-d650-41fe-9836-86659006c090",
    params={"decoding_method": "greedy", "max_new_tokens": 500}
)
####################################################

#AWS DynamoDB#######################################
AWS_REGION = "ap-south-1"
DYNAMO_TABLE = "JournalEntries"
FIXED_USER_ID = "demo_user"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
dynamo_table = dynamodb.Table(DYNAMO_TABLE)
####################################################

#Prompt#############################################
prompt = f"""You are 'Moodmate-AI,' a compassionate and professional therapeutic assistant specializing in cognitive reappraisal. Your task is to analyze a user's journal entry, strictly adhere to therapeutic principles, and output a structured JSON object.

        **CRITICAL RULES:**
        1.  **Strict Output Format:** You MUST output only a single, valid JSON object. Do not include any introductory text, markdown (like "```json"), or external commentary.
        2.  **Therapeutic Tone:** Maintain a warm, supportive, non-judgmental, and empowering tone in all generated text fields.
        3.  **Reframing:** The 'reappraisal_message' must neutralize negative intensity by providing a constructive, distanced, or solution-oriented perspective.
        4.  **Coping:** The 'coping_suggestions' must be a list of 2-3 simple, actionable, and healthy steps relevant to the user's specific challenge (e.g., technical problem, stress management).
        5.  **RAG Context:** The 'chatbot_context' Q&A pairs must be specific, directly referencing the journal entry to create high-quality memory for the subsequent chatbot interaction.

        ** INPUT: **
        {{entry.text}}

        **JSON SCHEMA:**
        {{
        "overall_risk_level": "[HIGH, MEDIUM, or LOW, based on safety check]",
        "action_required": "[PASS or BLOCK, based on safety check]",
        "confidence_score": "[Numeric probability between 0.0 (low risk) and 1.0 (high risk)]",
        "self_harm_flag": "[Yes or No]",
        "violence_flag": "[Yes or No]",
        "safety_comment": "[Brief reason for the overall risk level.]",
        
        "essence_theme": "[A single sentence summarizing the core emotional theme or challenge.]",
        "identified_strengths": [
            "[Identify one specific positive coping mechanism or inner strength the user demonstrated, even unintentionally.]",
            "[Identify a second strength, focusing on positive traits like self-awareness or perseverance.]"
        ],
        "reappraisal_message": "[A supportive paragraph (3-4 sentences) that reframes the main negative event or feeling into a positive lesson, a manageable challenge, or a temporary state. This is the 'neutralizing' message.]",
        "coping_suggestions": [
            "[Actionable suggestion 1, specific to the entry.]",
            "[Actionable suggestion 2, specific to the entry.]",
            "[Actionable suggestion 3, specific to the entry.]"
        ],
        "chatbot_context": [
            {{"Q": "[A specific question a future chatbot might ask based on the entry.]", "A": "[A concise answer derived directly from the journal entry.]"}},
            {{"Q": "[A second specific question.]", "A": "[A concise answer.]"}}
        ]
        }}
        """
##################################################

######ANALYZE JOURNAL ENTRY FUNCTION####################
def analyze_journal_entry(entry):
    try:
        response = reframing_model.generate(prompt)
        result = response["results"][0]["generated_text"]

        start_index = result.find('{')
        end_index = result.rfind('}')

        if start_index == -1 or end_index == -1:
            raise ValueError("LLM did not return a parsable JSON structure.")
        
        clean_json_text = result[start_index : end_index + 1]
        analysis_data = json.loads(clean_json_text)

        print("Generated Response:", analysis_data)
        
        return (analysis_data)
    except Exception as e:
        return {
            "overall_risk_level": "Error",
            "action_required": "Error",
            "confidence_score": None,
            "self_harm_flag": "Error occurred while processing the safety check.",
            "violence_flag": "Error occurred while processing the safety check.",
            "safety_comment": "An error occurred while processing the safety check.",
            "essence_theme": "Error processing the journal entry.",
            "identified_strengths": [],
            "reappraisal_message": "An error occurred while analyzing your journal entry. Please try again later.",
            "coping_suggestions": [],
            "chatbot_context": []
        }
######################################################

#####SAVE TO DYNAMODB###############################
def save_journal_entry(item: dict):
    item["user_id"] = FIXED_USER_ID
    item["entry_id"] = str(uuid4())
    item["timestamp_utc"] = datetime.datetime.utcnow().isoformat()
    try:
        dynamo_table.put_item(Item=item)
        print("Journal entry saved successfully.")
    except Exception as e:
        print("Error saving journal entry:", e)
###################################################

#Base Models#######################################
class JournalEntry(BaseModel):
    text: str

class ChatbotContextItem(BaseModel):
    Q: str
    A: str

class JournalEntryResponse(BaseModel):
    overall_risk_level: str
    action_required: str
    confidence_score: Decimal
    self_harm_flag: str
    violence_flag: str
    essence_theme: str
    identified_strengths: List[str]
    reappraisal_message: str
    coping_suggestions: List[str]
    chatbot_context: List[ChatbotContextItem]
###################################################

####################################################
####CREATE JOURNAL ENTRY ENDPOINT###################
@app.post("/journal-entry", response_model=JournalEntryResponse)
def create_journal_entry(entry: JournalEntry):
    analysis = analyze_journal_entry(entry)

    item = {
        "text": entry.text,
        "overall_risk_level": analysis["overall_risk_level"],
        "action_required": analysis["action_required"],
        "confidence_score": Decimal(str(analysis["confidence_score"])) if analysis["confidence_score"] is not None else None,
        "self_harm_flag": analysis["self_harm_flag"],
        "violence_flag": analysis["violence_flag"],
        "essence_theme": analysis["essence_theme"],
        "identified_strengths": analysis["identified_strengths"],
        "reappraisal_message": analysis["reappraisal_message"],
        "coping_suggestions": analysis["coping_suggestions"],
        "chatbot_context": analysis["chatbot_context"]
    }

    save_journal_entry(item)

    return JournalEntryResponse(
        overall_risk_level=str(analysis["overall_risk_level"]),
        action_required=analysis["action_required"],
        confidence_score=Decimal(str(analysis["confidence_score"])) if analysis["confidence_score"] is not None else None,
        self_harm_flag=analysis["self_harm_flag"],
        violence_flag=analysis["violence_flag"],
        essence_theme=analysis["essence_theme"],
        identified_strengths=analysis["identified_strengths"],
        reappraisal_message=analysis["reappraisal_message"],
        coping_suggestions=analysis["coping_suggestions"],
        chatbot_context=[ChatbotContextItem(**ctx) for ctx in analysis["chatbot_context"]]
    )
##########################################################################

##GET JOURNAL BY DATE########################################
@app.get("/journal-entry/by-date", response_model=JournalEntryResponse)
def get_journal_entry_by_date(date: str):
    try:
        response = dynamo_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(FIXED_USER_ID) & 
                                   boto3.dynamodb.conditions.Key('timestamp_utc').begins_with(date)
        )
        items = response.get('Items', [])
        if not items:
            return {"message": "No journal entries found for the specified date."}
        
        latest_entry = max(items, key=lambda x: x['timestamp_utc'])

        return JournalEntryResponse(
            overall_risk_level=latest_entry["overall_risk_level"],
            action_required=latest_entry["action_required"],
            confidence_score=latest_entry["confidence_score"],
            self_harm_flag=latest_entry["self_harm_flag"],
            violence_flag=latest_entry["violence_flag"],
            essence_theme=latest_entry["essence_theme"],
            identified_strengths=latest_entry["identified_strengths"],
            reappraisal_message=latest_entry["reappraisal_message"],
            coping_suggestions=latest_entry["coping_suggestions"],
            chatbot_context=[ChatbotContextItem(**ctx) for ctx in latest_entry["chatbot_context"]]
        )
    except Exception as e:
        return {"message": "Error retrieving journal entry: " + str(e)}
#####################################################

#GET ALL JOURNALS####################################
@app.get("/journal-entries", response_model=List[JournalEntryResponse])
def get_all_journal_entries():
    try:
        response = dynamo_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(FIXED_USER_ID)
        )
        items = response.get('Items', [])
        
        journal_entries = []
        for item in items:
            journal_entries.append(
                JournalEntryResponse(
                    overall_risk_level=item["overall_risk_level"],
                    action_required=item["action_required"],
                    confidence_score=item["confidence_score"],
                    self_harm_flag=item["self_harm_flag"],
                    violence_flag=item["violence_flag"],
                    essence_theme=item["essence_theme"],
                    identified_strengths=item["identified_strengths"],
                    reappraisal_message=item["reappraisal_message"],
                    coping_suggestions=item["coping_suggestions"],
                    chatbot_context=[ChatbotContextItem(**ctx) for ctx in item["chatbot_context"]]
                )
            )
        return journal_entries
    except Exception as e:
        return {"message": "Error retrieving journal entries: " + str(e)}
############################################################