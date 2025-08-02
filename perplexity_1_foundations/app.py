# Professional AI Assistant using Google Gemini API
# Updated to use Google Gemini instead of OpenAI for cost-effectiveness
# Requires GOOGLE_API_KEY, PUSHOVER_USER, and PUSHOVER_TOKEN environment variables

from typing import Any
from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr
import logging
import sys
from datetime import datetime

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

logger.info("="*50)
logger.info(f"Application starting at {datetime.now()}")
logger.info("="*50)

load_dotenv(override=True)

# Log environment variables (without revealing full keys)
logger.info("Checking environment variables...")
google_key = os.getenv('GOOGLE_API_KEY')
pushover_user = os.getenv('PUSHOVER_USER')
pushover_token = os.getenv('PUSHOVER_TOKEN')

logger.info(f"GOOGLE_API_KEY: {'✅ Found' if google_key else '❌ Missing'}")
logger.info(f"PUSHOVER_USER: {'✅ Found' if pushover_user else '❌ Missing'}")
logger.info(f"PUSHOVER_TOKEN: {'✅ Found' if pushover_token else '❌ Missing'}")

if google_key:
    logger.info(f"Google API Key starts with: {google_key[:4]}...")

def push(text: str):
    try:
        logger.info(f"Sending push notification: {text[:50]}...")
        response = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": os.getenv("PUSHOVER_TOKEN"),
                "user": os.getenv("PUSHOVER_USER"),
                "message": text,
            },
            timeout=10
        )
        logger.info(f"Push notification response status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"Push notification failed: {response.text}")
    except Exception as e:
        logger.error(f"Push notification error: {e}")

def record_user_details(email: str, name: str = "Name not provided", notes: str = "not provided"):
    logger.info(f"Recording user details - Name: {name}, Email: {email[:10]}...")
    message = f"Recording {name} with email {email} and notes {notes}"
    push(message)
    return {"recorded": "ok"}

def record_unknown_question(question: str):
    logger.info(f"Recording unknown question: {question[:50]}...")
    message = f"Recording {question}"
    push(message)
    return {"recorded": "ok"}

record_user_details_json: dict[str, Any] = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json: dict[str, Any] = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools: list[dict[str, Any]] = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]

logger.info(f"Tools configured: {len(tools)} tools available")

class Me:

    def __init__(self):
        logger.info("Initializing Me class...")
        
        # Setup Google Gemini API client
        google_api_key = os.getenv('GOOGLE_API_KEY')
        if not google_api_key:
            logger.error("GOOGLE_API_KEY environment variable is required")
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        logger.info("Setting up Google Gemini client...")
        self.gemini = OpenAI(
            api_key=google_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        logger.info("✅ Google Gemini client initialized")
        
        self.name = "Lei Niu"
        logger.info(f"Assistant name set to: {self.name}")
        
        # Load LinkedIn PDF
        try:
            logger.info("Loading LinkedIn PDF...")
            reader = PdfReader("me/linkedin.pdf")
            self.linkedin = ""
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    self.linkedin += text
                    logger.info(f"Loaded page {i+1} from LinkedIn PDF")
            logger.info(f"✅ LinkedIn PDF loaded successfully ({len(self.linkedin)} characters)")
        except FileNotFoundError:
            logger.error("❌ LinkedIn PDF not found at me/linkedin.pdf")
            self.linkedin = "LinkedIn profile not available"
        except Exception as e:
            logger.error(f"❌ Error loading LinkedIn PDF: {e}")
            self.linkedin = "LinkedIn profile not available"
        
        # Load summary
        try:
            logger.info("Loading summary.txt...")
            with open("me/summary.txt", "r", encoding="utf-8") as f:
                self.summary = f.read()
            logger.info(f"✅ Summary loaded successfully ({len(self.summary)} characters)")
        except FileNotFoundError:
            logger.error("❌ Summary file not found at me/summary.txt")
            self.summary = "Professional summary not available"
        except Exception as e:
            logger.error(f"❌ Error loading summary: {e}")
            self.summary = "Professional summary not available"
        
        logger.info("✅ Me class initialization complete")

    def handle_tool_call(self, tool_calls: list[Any]):
        logger.info(f"Handling {len(tool_calls)} tool calls...")
        results: list[dict[str, Any]] = []
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call.function.name
            arguments_str = tool_call.function.arguments
            logger.info(f"Tool call {i+1}: {tool_name}")
            logger.info(f"Arguments: {arguments_str}")
            
            try:
                arguments = json.loads(arguments_str)
                logger.info(f"Parsed arguments: {arguments}")
                
                tool = globals().get(tool_name)
                if tool:
                    logger.info(f"Executing tool: {tool_name}")
                    result: dict[str, Any] = tool(**arguments)
                    logger.info(f"Tool result: {result}")
                else:
                    logger.error(f"Tool not found: {tool_name}")
                    result = {"error": f"Tool {tool_name} not found"}
                
                results.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id
                })
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse tool arguments: {e}")
                results.append({
                    "role": "tool",
                    "content": json.dumps({"error": "Invalid arguments"}),
                    "tool_call_id": tool_call.id
                })
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                results.append({
                    "role": "tool",
                    "content": json.dumps({"error": str(e)}),
                    "tool_call_id": tool_call.id
                })
        
        logger.info(f"✅ Completed handling {len(results)} tool calls")
        return results
    
    def system_prompt(self):
        prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

        prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        
        logger.info(f"System prompt generated ({len(prompt)} characters)")
        return prompt
    
    def chat(self, message: str, history: list[dict[str, str]]):
        logger.info("="*30)
        logger.info(f"NEW CHAT REQUEST: {message[:100]}...")
        logger.info(f"History length: {len(history)} messages")
        
        try:
            # Clean up history for better compatibility
            history = [{"role": h["role"], "content": h["content"]} for h in history]
            logger.info("✅ History cleaned")
            
            messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
            logger.info(f"Total messages to send: {len(messages)}")
            
            done = False
            iteration = 0
            
            while not done:
                iteration += 1
                logger.info(f"API call iteration {iteration}")
                
                try:
                    logger.info("Calling Google Gemini API...")
                    response = self.gemini.chat.completions.create(
                        model="gemini-2.0-flash", 
                        messages=messages, 
                        tools=tools,
                        timeout=30
                    )
                    logger.info("✅ API call successful")
                    
                    finish_reason = response.choices[0].finish_reason
                    logger.info(f"Finish reason: {finish_reason}")
                    
                    if finish_reason == "tool_calls":
                        logger.info("Tool calls detected, processing...")
                        message_obj = response.choices[0].message
                        tool_calls = message_obj.tool_calls
                        logger.info(f"Number of tool calls: {len(tool_calls)}")
                        
                        results = self.handle_tool_call(tool_calls)
                        messages.append(message_obj)
                        messages.extend(results)
                        logger.info("Tool calls processed, continuing conversation...")
                    else:
                        done = True
                        final_response = response.choices[0].message.content
                        logger.info(f"✅ Final response generated ({len(final_response)} characters)")
                        logger.info(f"Response preview: {final_response[:200]}...")
                        
                except Exception as api_error:
                    logger.error(f"❌ API call failed: {api_error}")
                    return f"I apologize, but I'm experiencing technical difficulties. Error: {str(api_error)}"
            
            return final_response
            
        except Exception as e:
            logger.error(f"❌ Chat error: {e}")
            return f"I apologize, but I encountered an error: {str(e)}"
    

if __name__ == "__main__":
    try:
        logger.info("Creating Me instance...")
        me = Me()
        logger.info("✅ Me instance created successfully")
        
        logger.info("Setting up Gradio interface...")
        interface = gr.ChatInterface(
            me.chat, 
            type="messages",
            title=f"Chat with {me.name}",
            description=f"Professional AI Assistant representing {me.name}"
        )
        logger.info("✅ Gradio interface created")
        
        logger.info("Launching application...")
        interface.launch(
            share=False,
            server_name="0.0.0.0",
            server_port=7860
        )
        
    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        raise
