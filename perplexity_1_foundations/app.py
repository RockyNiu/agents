# Professional AI Assistant using Google Gemini API
# Updated to use agents library for better structure
# Requires GOOGLE_API_KEY, PUSHOVER_USER, and PUSHOVER_TOKEN environment variables

from dotenv import load_dotenv
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr
import logging
import sys
import asyncio
from datetime import datetime
from pydantic import BaseModel
from agents import Agent, Runner, trace, OpenAIChatCompletionsModel, function_tool
from openai import AsyncOpenAI

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

# Initialize main model using agents library with AsyncOpenAI
main_model = None
if google_key:
    logger.info("Setting up main model with agents library...")
    gemini_client = AsyncOpenAI(
        api_key=google_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    main_model = OpenAIChatCompletionsModel(
        model="gemini-2.0-flash",
        openai_client=gemini_client
    )
    logger.info("✅ Main model initialized")

# Evaluation model for response quality assessment
class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str

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

@function_tool
def record_user_details(email: str, name: str = "Name not provided", notes: str = "not provided"):
    """Record user contact details and notes"""
    logger.info(f"Recording user details - Name: {name}, Email: {email[:10]}...")
    message = f"Recording {name} with email {email} and notes {notes}"
    push(message)
    return {"recorded": "ok"}

@function_tool
def record_unknown_question(question: str):
    """Record questions that the assistant couldn't answer"""
    logger.info(f"Recording unknown question: {question[:50]}...")
    message = f"Recording {question}"
    push(message)
    return {"recorded": "ok"}

# Setup evaluator model (using same model for evaluation)
evaluator_model = None
if google_key:
    logger.info("Setting up evaluator model...")
    evaluator_client = AsyncOpenAI(
        api_key=google_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    evaluator_model = OpenAIChatCompletionsModel(
        model="gemini-2.0-flash",
        openai_client=evaluator_client
    )
    logger.info("✅ Evaluator model initialized")

async def evaluate_response(reply: str, message: str, name: str) -> Evaluation:
    """Evaluate if a response is acceptable quality"""
    if not evaluator_model:
        logger.warning("No evaluator model available, skipping evaluation")
        return Evaluation(is_acceptable=True, feedback="Evaluation skipped - no evaluator available")
    
    try:
        logger.info("Starting response evaluation...")
        
        evaluator_prompt = f"""You are an evaluator that decides whether a response is acceptable quality.
        
You are evaluating a response from an AI assistant representing {name} on their professional website.
The assistant should be professional, engaging, and represent {name} faithfully.

Here's the user's message: {message}
Here's the assistant's response: {reply}

Evaluate whether this response is acceptable. Consider:
1. Professional tone and engagement
2. Accuracy and helpfulness  
3. Staying in character as {name}
4. Appropriate use of tools when needed

Respond with JSON format: {{"is_acceptable": true/false, "feedback": "your detailed feedback"}}"""

        # Create evaluator agent
        evaluator_agent = Agent(
            name="evaluator",
            model=evaluator_model,
            instructions=evaluator_prompt
        )
        
        # Run evaluation
        with trace("evaluate_response"):
            result = await Runner.run(evaluator_agent, message)
        
        result_text = result.final_output or ""
        logger.info(f"Evaluator raw response: {result_text[:200]}...")
        
        # Extract JSON from response
        try:
            # Find JSON in the response
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = result_text[json_start:json_end]
                result_dict = json.loads(json_str)
                evaluation = Evaluation(**result_dict)
                logger.info(f"✅ Evaluation completed: {evaluation.is_acceptable}")
                return evaluation
            else:
                logger.warning("No JSON found in evaluator response")
                return Evaluation(is_acceptable=True, feedback="Could not parse evaluation")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse evaluator JSON: {e}")
            return Evaluation(is_acceptable=True, feedback="JSON parsing failed")
            
    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        return Evaluation(is_acceptable=True, feedback=f"Evaluation failed: {str(e)}")

async def rerun_with_feedback(original_reply: str, message: str, feedback: str, system_prompt: str) -> str:
    """Generate a new response incorporating evaluation feedback"""
    if not evaluator_model:
        logger.warning("No evaluator model for rerun, returning original")
        return original_reply
    
    try:
        logger.info("Generating improved response with feedback...")
        
        improved_prompt = f"""{system_prompt}

## Previous Response Rejected
Your previous response was not acceptable. Here's what you tried to say:
{original_reply}

## Feedback for Improvement:
{feedback}

Please provide a better response that addresses the feedback while maintaining your character and professionalism."""

        # Create improvement agent
        improvement_agent = Agent(
            name="improvement",
            model=evaluator_model,
            instructions=improved_prompt
        )
        
        # Run improvement
        with trace("rerun_with_feedback"):
            result = await Runner.run(improvement_agent, message)

        improved_response = result.final_output or original_reply
        logger.info(f"✅ Improved response generated ({len(improved_response)} characters)")
        return improved_response
        
    except Exception as e:
        logger.error(f"Rerun error: {e}")
        return original_reply

class Me:

    def __init__(self):
        logger.info("Initializing Me class...")
        
        # Check Google API key
        google_api_key = os.getenv('GOOGLE_API_KEY')
        if not google_api_key:
            logger.error("GOOGLE_API_KEY environment variable is required")
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        logger.info("Setting up agent with agents library...")
        
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
        
        # Create the main agent with tools
        if main_model:
            self.agent = Agent(
                name="main_assistant",
                model=main_model,
                instructions=self.system_prompt(),
                tools=[record_user_details, record_unknown_question]
            )
            logger.info("✅ Main agent created with tools")
        else:
            logger.error("❌ Cannot create agent without model")
            raise ValueError("Model not available")
        
        logger.info("✅ Me class initialization complete")
    
    def system_prompt(self):
        prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using the record_user_details tool. "

        prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        
        logger.info(f"System prompt generated ({len(prompt)} characters)")
        return prompt
    
    async def chat_async(self, message, history=None) -> str:
        """Professional AI assistant chat with tool support and evaluation using agents library"""
        try:
            # Convert message to string regardless of format
            message_str = str(message)
            logger.info(f"💬 Processing message: {message_str[:100]}...")
            
            # Check if agent is available
            if not hasattr(self, 'agent'):
                logger.error("No agent available")
                return "I apologize, but the AI service is not available at the moment."
            
            logger.info("🤖 Running agent with trace...")
            
            # Use the agents library to run the conversation
            with trace("chat_interaction"):
                result = await Runner.run(self.agent, message_str)
            
            final_response = result.final_output or ""
            
            if final_response:
                logger.info(f"✅ Response generated ({len(final_response)} characters)")
                logger.info(f"Response preview: {final_response[:200]}...")
            else:
                logger.warning("Empty response received")
                return "I apologize, but I couldn't generate a response. Please try again."
            
            # Evaluate response quality
            if final_response and evaluator_model:
                logger.info("🔍 Evaluating response quality...")
                evaluation = await evaluate_response(final_response, message_str, self.name)
                
                if not evaluation.is_acceptable:
                    logger.warning(f"❌ Response rejected: {evaluation.feedback}")
                    # Generate improved response
                    final_response = await rerun_with_feedback(
                        final_response, message_str, evaluation.feedback, self.system_prompt()
                    )
                    logger.info("🔄 Using improved response")
                else:
                    logger.info("✅ Response approved by evaluator")
            
        except Exception as e:
            logger.error(f"Chat error: {str(e)}", exc_info=True)
            return f"I apologize, but I encountered an error: {str(e)}"
        
        return final_response or "I apologize, but I couldn't generate a response. Please try again."
    
    def chat(self, message, history=None) -> str:
        """Synchronous wrapper for the async chat function"""
        return asyncio.run(self.chat_async(message, history))

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
