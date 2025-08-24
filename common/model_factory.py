"""
Model configurations for different LLM providers.

This module provides a centralized way to configure and access different models
including OpenAI, Gemini, Perplexity, Groq, Anthropic (Claude), and DeepSeek models 
through OpenAI-compatible endpoints. Uses factory pattern for better organization and maintainability.
"""

import os
from enum import Enum
from typing import Dict, Optional
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


class ModelProvider(Enum):
    """Enum for available model providers."""
    OPENAI = "openai"
    GEMINI = "gemini" 
    PERPLEXITY = "perplexity"
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"


class ModelFactory:
    """Factory class for creating and managing different LLM models."""
    
    # API Base URLs
    GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
    PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
    GROQ_BASE_URL = "https://api.groq.com/openai/v1"
    ANTHROPIC_BASE_URL = "https://api.anthropic.com"
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    
    # Default model names for each provider
    DEFAULT_MODELS = {
        ModelProvider.OPENAI: "gpt-4o-mini",
        ModelProvider.GEMINI: "gemini-2.0-flash",
        ModelProvider.PERPLEXITY: "sonar",
        ModelProvider.GROQ: "llama-3.3-70b-versatile",
        ModelProvider.ANTHROPIC: "claude-3-5-haiku-20241022",
        ModelProvider.DEEPSEEK: "deepseek-chat",
    }
    
    def __init__(self):
        """Initialize the model factory with API keys."""
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.perplexity_api_key = os.getenv('PERPLEXITY_API_KEY')
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        
        # Cache for clients and models
        self._clients: Dict[ModelProvider, AsyncOpenAI] = {}
        self._models: Dict[ModelProvider, OpenAIChatCompletionsModel] = {}
    
    def _get_openai_client(self) -> AsyncOpenAI:
        """Get OpenAI client."""
        if ModelProvider.OPENAI not in self._clients:
            self._clients[ModelProvider.OPENAI] = AsyncOpenAI(api_key=self.openai_api_key)
        return self._clients[ModelProvider.OPENAI]
    
    def _get_gemini_client(self) -> AsyncOpenAI:
        """Get Gemini client using OpenAI-compatible endpoint."""
        if ModelProvider.GEMINI not in self._clients:
            self._clients[ModelProvider.GEMINI] = AsyncOpenAI(
                base_url=self.GEMINI_BASE_URL, 
                api_key=self.google_api_key
            )
        return self._clients[ModelProvider.GEMINI]
    
    def _get_perplexity_client(self) -> AsyncOpenAI:
        """Get Perplexity client using OpenAI-compatible endpoint."""
        if ModelProvider.PERPLEXITY not in self._clients:
            self._clients[ModelProvider.PERPLEXITY] = AsyncOpenAI(
                base_url=self.PERPLEXITY_BASE_URL, 
                api_key=self.perplexity_api_key
            )
        return self._clients[ModelProvider.PERPLEXITY]
    
    def _get_groq_client(self) -> AsyncOpenAI:
        """Get Groq client using OpenAI-compatible endpoint."""
        if ModelProvider.GROQ not in self._clients:
            self._clients[ModelProvider.GROQ] = AsyncOpenAI(
                base_url=self.GROQ_BASE_URL, 
                api_key=self.groq_api_key
            )
        return self._clients[ModelProvider.GROQ]
    
    def _get_anthropic_client(self) -> AsyncOpenAI:
        """Get Anthropic client using OpenAI-compatible endpoint."""
        if ModelProvider.ANTHROPIC not in self._clients:
            self._clients[ModelProvider.ANTHROPIC] = AsyncOpenAI(
                base_url=self.ANTHROPIC_BASE_URL, 
                api_key=self.anthropic_api_key
            )
        return self._clients[ModelProvider.ANTHROPIC]
    
    def _get_deepseek_client(self) -> AsyncOpenAI:
        """Get DeepSeek client using OpenAI-compatible endpoint."""
        if ModelProvider.DEEPSEEK not in self._clients:
            self._clients[ModelProvider.DEEPSEEK] = AsyncOpenAI(
                base_url=self.DEEPSEEK_BASE_URL, 
                api_key=self.deepseek_api_key
            )
        return self._clients[ModelProvider.DEEPSEEK]
    
    def create_model(self, provider: ModelProvider, model_name: Optional[str] = None) -> OpenAIChatCompletionsModel:
        """
        Create a model instance for the specified provider.
        
        Args:
            provider: The model provider enum
            model_name: Optional custom model name, uses default if not provided
            
        Returns:
            OpenAIChatCompletionsModel: The model instance
        """
        if model_name is None:
            model_name = self.DEFAULT_MODELS[provider]
        
        if provider == ModelProvider.OPENAI:
            client = self._get_openai_client()
        elif provider == ModelProvider.GEMINI:
            client = self._get_gemini_client()
        elif provider == ModelProvider.PERPLEXITY:
            client = self._get_perplexity_client()
        elif provider == ModelProvider.GROQ:
            client = self._get_groq_client()
        elif provider == ModelProvider.ANTHROPIC:
            client = self._get_anthropic_client()
        elif provider == ModelProvider.DEEPSEEK:
            client = self._get_deepseek_client()
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)
    
    def get_model(self, provider: ModelProvider, model_name: Optional[str] = None) -> OpenAIChatCompletionsModel:
        """
        Get a cached model instance for the specified provider.
        
        Args:
            provider: The model provider enum
            
        Returns:
            OpenAIChatCompletionsModel: The cached model instance
        """
        if provider not in self._models:
            self._models[provider] = self.create_model(provider=provider, model_name=model_name)
        return self._models[provider]
    
    def check_api_keys(self) -> Dict[str, str]:
        """Check which API keys are available."""
        keys_status: dict[str, str] = {}
        
        if self.openai_api_key:
            keys_status["OpenAI"] = f"Available (begins with {self.openai_api_key[:8]})"
        else:
            keys_status["OpenAI"] = "Not set"
        
        if self.google_api_key:
            keys_status["Google (Gemini)"] = f"Available (begins with {self.google_api_key[:2]})"
        else:
            keys_status["Google (Gemini)"] = "Not set"
        
        if self.perplexity_api_key:
            keys_status["Perplexity"] = f"Available (begins with {self.perplexity_api_key[:4]})"
        else:
            keys_status["Perplexity"] = "Not set"
        
        if self.groq_api_key:
            keys_status["Groq"] = f"Available (begins with {self.groq_api_key[:4]})"
        else:
            keys_status["Groq"] = "Not set"
        
        if self.anthropic_api_key:
            keys_status["Anthropic (Claude)"] = f"Available (begins with {self.anthropic_api_key[:8]})"
        else:
            keys_status["Anthropic (Claude)"] = "Not set"
        
        if self.deepseek_api_key:
            keys_status["DeepSeek"] = f"Available (begins with {self.deepseek_api_key[:8]})"
        else:
            keys_status["DeepSeek"] = "Not set"
        
        return keys_status
    
    def print_api_key_status(self) -> None:
        """Print the status of all API keys."""
        print("API Key Status:")
        print("-" * 40)
        for provider, status in self.check_api_keys().items():
            print(f"{provider}: {status}")
        print("-" * 40)
    
    def get_model_by_provider(self, provider: ModelProvider) -> OpenAIChatCompletionsModel:
        """
        Get a model by provider enum.
        
        Args:
            provider: The model provider enum
            
        Returns:
            OpenAIChatCompletionsModel: The requested model instance
        """
        return self.get_model(provider)
    
    def create_custom_model(self, provider: ModelProvider, model_name: str) -> OpenAIChatCompletionsModel:
        """
        Create a custom model with a specific model name.
        
        Args:
            provider: The model provider enum
            model_name: The specific model name to use
            
        Returns:
            OpenAIChatCompletionsModel: The custom model instance
        """
        return self.create_model(provider, model_name)
    
    def get_default_model(self) -> OpenAIChatCompletionsModel:
        """Get the default model (Gemini Flash - free)."""
        return self.get_model(ModelProvider.GEMINI)
    
    def list_available_providers(self) -> list[str]:
        """Get list of available providers."""
        return [provider.value for provider in ModelProvider]
    
    def print_factory_examples(self) -> None:
        """Print examples of how to use the factory."""
        print("\n" + "="*50)
        print("Factory Pattern Examples:")
        print("="*50)
        
        print("\n1. Using ModelProvider enum:")
        gemini_model = self.get_model_by_provider(ModelProvider.GEMINI)
        print(f"   Gemini model: {gemini_model}")
        
        print("\n2. Creating custom models:")
        custom_gemini = self.create_custom_model(ModelProvider.GEMINI, "gemini-2.0-flash")
        print(f"   Custom Gemini: {custom_gemini}")
        
        print("\n3. Get default model:")
        default_model = self.get_default_model()
        print(f"   Default model: {default_model}")
        
        print("\n4. Available providers:")
        for provider in self.list_available_providers():
            print(f"   - {provider}")
            
        print("\n" + "="*50)


# Global factory instance
model_factory = ModelFactory()


if __name__ == "__main__":
    model_factory.print_api_key_status()
    print(f"\nDefault model: {model_factory.get_default_model()}")
    print(f"Available providers: {model_factory.list_available_providers()}")
    
    # Print factory examples
    model_factory.print_factory_examples()
