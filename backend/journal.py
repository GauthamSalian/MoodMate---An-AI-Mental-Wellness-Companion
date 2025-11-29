from fastapi import APIRouter
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
router = APIRouter()

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
DYNAMO_CUE_TABLE = "JournalCueSchedule"
FIXED_USER_ID = "demo_user"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
dynamo_table = dynamodb.Table(DYNAMO_TABLE)
dynamo_cue_table = dynamodb.Table(DYNAMO_CUE_TABLE)
####################################################

######ANALYZE JOURNAL ENTRY FUNCTION####################
def analyze_journal_entry(entry):
    try:
        history_data = analyze_last_five_entries()
        prompt = f"""You are the 'Moodmate Unified Agent.' Your task is two-fold:
        1.  **Safety Check:** Analyze the user's current entry for psychological risk.
        2.  **Therapeutic Analysis:** Analyze the current entry and synthesize a **Pattern Analysis** using the provided historical context.

        **CRITICAL RULES:**
        1.  **Strict Output Format:** You MUST output ONLY a single, valid JSON object. Do not include any introductory text, commentary, or markdown fences.
        2.  **Action Determination:** Set 'action_required' to "BLOCK" if 'self_harm_flag' or 'violence_flag' is 'Yes'. Otherwise, set it to "PASS".
        3.  **Pattern Synthesis:** Use the 'HISTORICAL DATA' provided below to identify one specific recurring trigger or theme.

        ** INPUT (Current Journal Entry): **
        {entry}

        ** HISTORICAL DATA (Last 5 Entries): **
        {history_data}

        **UNIFIED JSON SCHEMA:**
        {{
        "overall_risk_level": "[HIGH, MEDIUM, or LOW, based on safety check]",
        "action_required": "[PASS or BLOCK, based on safety check]",
        "confidence_score": "[Numeric probability between 0.0 (low risk) and 1.0 (high risk)]",
        "self_harm_flag": "[Yes or No]",
        "violence_flag": "[Yes or No]",
        "safety_comment": "[Brief reason for the overall risk level.]",

        "historical_pattern": "[A sentence summarizing the recurring emotional or behavioral pattern identified from the HISTORICAL DATA, e.g., 'Anxiety consistently peaks on Sundays.' If no history is available, state 'No clear pattern detected.']",

        "essence_theme": "[A single sentence summarizing the core emotional theme of the CURRENT entry.]",
        "identified_strengths": [
            "[Identify one specific positive coping mechanism or inner strength.]",
            "[Identify a second strength.]"
        ],
        "reappraisal_message": "[A supportive paragraph (max 3 sentences) that reframes the main negative event.]",
        "coping_suggestions": [
            "[Actionable suggestion 1, formatted as a clear Cue-Action statement: 'When [specific situation], I will [specific coping action].']",
            "[Actionable suggestion 1, formatted as a clear Cue-Action statement: 'When [specific situation], I will [specific coping action].']",
            "[Actionable suggestion 1, formatted as a clear Cue-Action statement: 'When [specific situation], I will [specific coping action].']"
        ],
        "chatbot_context": [
            {{"Q": "[A specific question a future chatbot might ask.]", "A": "[A concise answer derived from the CURRENT entry.]"}},
            {{"Q": "[A second specific question.]", "A": "[A concise answer.]"}}
        ]
        }}
        """
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

def save_cue_schedule(cue_item: dict):
    cue_item["user_id"] = FIXED_USER_ID
    cue_item["journal_timestamp"] = datetime.datetime.utcnow().isoformat()
    try:
        dynamo_cue_table.put_item(Item = cue_item)
        print("Cues saved successfully")
    except Exception as e:
        print("Error saving cues:", e)

###############ANALYZE LAST 5 ENTRIES###################
def analyze_last_five_entries():
    try:
        response = dynamo_table.query(
            KeyConditionExpression = boto3.dynamodb.conditions.Key('user_id').eq(FIXED_USER_ID),
            ScanIndexForward = False,
            Limit = 5
        )
        items = response.get('Items', [])
        
        formatted_entries = []
        for item in items:
            formatted_entries.append(
                f"""
                    Theme: {item['essence_theme']},
                    Action Taken: {item['action_required']},
                    Coping Suggestions: {', '.join(item['coping_suggestions'])}
                """
            )

        if not formatted_entries:
            return("No journal entries found for analysis.")

        return "---  ENTRY SEPARATOR  ---".join(formatted_entries)
    except Exception as e:
        print("Error retrieving journal entries:", e)
########################################################

#Base Models#######################################
class JournalEntry(BaseModel):
    text: str

class ChatbotContextItem(BaseModel):
    Q: str
    A: str

class JournalEntryResponse(BaseModel):
    entry_text: str
    overall_risk_level: str
    action_required: str
    confidence_score: Decimal
    self_harm_flag: str
    violence_flag: str
    essence_theme: str
    historical_pattern: str
    identified_strengths: List[str]
    reappraisal_message: str
    coping_suggestions: List[str]
    chatbot_context: List[ChatbotContextItem]
###################################################

#######################ENDPOINTS###########################
#.........................................................#
####CREATE JOURNAL ENTRY ENDPOINT###################
@router.post("/journal-entry", response_model=JournalEntryResponse)
def create_journal_entry(entry: JournalEntry):
    analysis = analyze_journal_entry(entry.text)

    item = {
        "text": entry.text,
        "overall_risk_level": analysis["overall_risk_level"],
        "action_required": analysis["action_required"],
        "confidence_score": Decimal(str(analysis["confidence_score"])) if analysis["confidence_score"] is not None else None,
        "self_harm_flag": analysis["self_harm_flag"],
        "violence_flag": analysis["violence_flag"],
        "essence_theme": analysis["essence_theme"],
        "historical_pattern": analysis["historical_pattern"],
        "identified_strengths": analysis["identified_strengths"],
        "reappraisal_message": analysis["reappraisal_message"],
        "coping_suggestions": analysis["coping_suggestions"],
        "chatbot_context": analysis["chatbot_context"]
    }

    save_journal_entry(item)
    save_cue_schedule({
        "cue_1": analysis["coping_suggestions"][0],
        "cue_2": analysis["coping_suggestions"][1],
        "cue_3": analysis["coping_suggestions"][2]
    })

    return JournalEntryResponse(
        entry_text=entry.text,
        overall_risk_level=str(analysis["overall_risk_level"]),
        action_required=analysis["action_required"],
        confidence_score=Decimal(str(analysis["confidence_score"])) if analysis["confidence_score"] is not None else None,
        self_harm_flag=analysis["self_harm_flag"],
        violence_flag=analysis["violence_flag"],
        essence_theme=analysis["essence_theme"],
        historical_pattern=analysis["historical_pattern"],
        identified_strengths=analysis["identified_strengths"],
        reappraisal_message=analysis["reappraisal_message"],
        coping_suggestions=analysis["coping_suggestions"],
        chatbot_context=[ChatbotContextItem(**ctx) for ctx in analysis["chatbot_context"]]
    )
##########################################################################

##GET JOURNAL BY DATE########################################
@router.get("/journal-entry/by-date", response_model=JournalEntryResponse)
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
            entry_text=latest_entry["text"],
            overall_risk_level=latest_entry["overall_risk_level"],
            action_required=latest_entry["action_required"],
            confidence_score=latest_entry["confidence_score"],
            self_harm_flag=latest_entry["self_harm_flag"],
            violence_flag=latest_entry["violence_flag"],
            essence_theme=latest_entry["essence_theme"],
            historical_pattern=latest_entry["historical_pattern"],
            identified_strengths=latest_entry["identified_strengths"],
            reappraisal_message=latest_entry["reappraisal_message"],
            coping_suggestions=latest_entry["coping_suggestions"],
            chatbot_context=[ChatbotContextItem(**ctx) for ctx in latest_entry["chatbot_context"]]
        )
    except Exception as e:
        return {"message": "Error retrieving journal entry: " + str(e)}
#####################################################

#GET ALL JOURNALS####################################
@router.get("/journal-entries", response_model=List[JournalEntryResponse])
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
                    historical_pattern=item["historical_pattern"],
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