#!/usr/bin/env python3
"""
Naze: Your witty AI-powered task manager with multi-provider, multi-key support.
"""

import os
import sys
import sqlite3
import json
import subprocess
import getpass
import pyfiglet
from pyfiglet import Figlet
import typer
import time
import random
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union, Tuple
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from groq import Groq
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich import print as rprint
import requests
from urllib.parse import urlparse
import shutil
import fnmatch
import socket
import codecs
import threading
import queue
import signal

try:
    import smrx
except ImportError:
    smrx = None

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")
try:
    from font import render_pyfiglet, GENERATED_FONT
except ImportError:
    GENERATED_FONT = None
    def render_pyfiglet(text, spacer=1):
        try:
            return pyfiglet.figlet_format(text, font="standard")
        except:
            return text

try:
    fluffy_brackets = Figlet(font='Fluffy Brackets.flf')
except Exception:
    fluffy_brackets = None

# Initialize Typer and UI
app = typer.Typer(help="Naze: Your witty AI-powered task manager with multi-provider, multi-key support.")
console = Console()

# ============================================================================
# GLOBALS
# ============================================================================

current_working_dir = os.getcwd()
username = getpass.getuser().capitalize() if getpass.getuser() else "User"
OFFLINE_MODE = False
command_history = []
MAX_HISTORY = 100


def build_naze_identity() -> str:
    """Internal project profile derived from the README, not pasted as a raw README block."""
    readme_path = Path(__file__).with_name("README.md")
    readme_text = ""
    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except Exception:
        readme_text = ""

    profile = {
        "identity": "Naze",
        "origin": "A terminal-first AI task manager inspired by the NaSeZn crystal origin story and shortened to Naze.",
        "purpose": "Manage tasks, assess energy/impact, track stale work, and give witty runtime guidance from the terminal.",
        "core_features": [
            "AI-powered task management and chat mode",
            "task scoring with energy rating and impact score",
            "stale task detection and productivity reviews",
            "local SQLite task database",
            "multi-provider and multi-key AI support",
            "graceful offline fallback and health diagnostics",
            "command execution, file reads, and direct terminal interaction"
        ],
        "supported_providers": [
            "Groq", "OpenRouter", "Mistral", "Anthropic", "DeepSeek", "Together", "custom providers", "local Ollama"
        ],
        "database_location": "~/.local/share/Naze/tasks.db",
        "commands": [
            "add", "list", "finish", "delete", "clear", "review", "health", "providers", "switch_model", "exec", "chat"
        ],
        "behavior": "Be witty, brief, confident, and slightly sarcastic without sounding generic or corporate."
    }

    if readme_text:
        lower = readme_text.lower()
        if "witty" in lower or "sarcastic" in lower:
            profile["behavior"] = "Be witty, slightly sarcastic, and terminal-native rather than polished corporate chatbot speech."
        if "sqlite" in lower:
            profile["database_location"] = "SQLite database at ~/.local/share/Naze/tasks.db"
        if "groq" in lower and "openrouter" in lower:
            profile["supported_providers"] = [
                "Groq", "OpenRouter", "Mistral", "Anthropic", "DeepSeek", "Together", "custom endpoints", "local Ollama"
            ]

    return f"""You are Naze, the project's own terminal AI task manager.

Project identity:
- Name: {profile['identity']}
- Origin: {profile['origin']}
- Purpose: {profile['purpose']}
- Core features: {', '.join(profile['core_features'])}
- Supported AI providers: {', '.join(profile['supported_providers'])}
- Local task storage: {profile['database_location']}
- Main commands: {', '.join(profile['commands'])}
- Personality: {profile['behavior']}

Important: this is your internal identity, not a pasted README. You are the assistant that lives in this project, operates this task manager, and knows its capabilities from the project design itself.
"""


NAZE_IDENTITY = build_naze_identity()

# ============================================================================
# SMRX WRAPPER - IMPROVED
# ============================================================================

class SMRXWrapper:
    """Wrapper for SMRX regex engine with fallback support."""
    
    def __init__(self):
        self.available = smrx is not None
        self._engine = smrx if self.available else None
        self._stats = {
            "searches": 0,
            "matches": 0,
            "errors": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
    
    def search(self, directory: str, pattern: str, file_pattern: str = "*", 
               max_results: int = 500) -> Dict:
        """Perform regex search with statistics tracking."""
        if not self.available:
            return {"error": "SMRX not available"}
        
        self._stats["searches"] += 1
        
        try:
            # Validate pattern first
            is_valid, error = self._engine.validate(pattern)
            if not is_valid:
                self._stats["errors"] += 1
                return {"error": f"Invalid regex: {error}"}
            
            # Perform search
            result = self._engine.search(
                directory,
                pattern,
                file_pattern=file_pattern,
                recursive=True,
                case_sensitive=False,
                max_results=max_results,
                mode=smrx.SearchMode.PARALLEL
            )
            
            self._stats["matches"] += result.matches_found
            
            # Format results for consistent output
            return {
                "query": pattern,
                "pattern": file_pattern,
                "files_searched": result.total_files_searched,
                "matches_found": result.matches_found,
                "execution_time": result.execution_time,
                "matches": [
                    {
                        "file": m.filepath,
                        "line": m.line_num,
                        "col": m.col_num,
                        "text": m.line_text.strip()[:200],
                        "match": m.match_text
                    }
                    for m in result.matches[:100]
                ],
                "stats": {
                    "files_per_second": result.total_files_searched / result.execution_time if result.execution_time > 0 else 0
                }
            }
        except Exception as e:
            self._stats["errors"] += 1
            return {"error": str(e)}
    
    def get_stats(self) -> Dict:
        """Get wrapper statistics."""
        return self._stats.copy()
    
    def clear_cache(self):
        """Clear SMRX cache."""
        if self.available:
            self._engine.clear_cache()
    
    def get_cache_stats(self) -> Dict:
        """Get SMRX cache statistics."""
        if self.available:
            return self._engine.get_cache_stats()
        return {}
    
    def validate(self, pattern: str) -> Tuple[bool, Optional[str]]:
        """Validate regex pattern."""
        if not self.available:
            return False, "SMRX not available"
        return self._engine.validate(pattern)

# Initialize SMRX wrapper
smrx_wrapper = SMRXWrapper()

# ============================================================================
# CONFIGURATION & MULTI-PROVIDER WITH MULTI-KEY SUPPORT
# ============================================================================

def check_network_connectivity(host="8.8.8.8", port=53, timeout=3):
    """Check if network is available."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False

def load_keys_from_env(provider: str) -> Dict[str, List[str]]:
    """Load primary, fallback, and unused keys from environment."""
    keys = {
        "primary": [],
        "fallback": [],
        "unused": []
    }
    
    primary_keys = os.environ.get(f"{provider.upper()}_PRIMARY_KEYS", "")
    if primary_keys:
        keys["primary"] = [k.strip() for k in primary_keys.split(",") if k.strip()]
    
    fallback_keys = os.environ.get(f"{provider.upper()}_FALLBACK_KEYS", "")
    if fallback_keys:
        keys["fallback"] = [k.strip() for k in fallback_keys.split(",") if k.strip()]
    
    unused_keys = os.environ.get(f"{provider.upper()}_UNUSED_KEYS", "")
    if unused_keys:
        keys["unused"] = [k.strip() for k in unused_keys.split(",") if k.strip()]
    
    if not any(keys.values()):
        old_keys = os.environ.get(f"{provider.upper()}_API_KEYS", "")
        if old_keys:
            keys["primary"] = [k.strip() for k in old_keys.split(",") if k.strip()]
    
    return keys

class ProviderConfig:
    """Configuration for an AI provider with multiple API keys and custom endpoints."""
    
    def __init__(self, name: str, primary_keys: List[str], fallback_keys: List[str], 
                 unused_keys: List[str], base_url: Optional[str] = None,
                 default_model: Optional[str] = None, models: Optional[List[str]] = None,
                 proxy: Optional[str] = None, timeout: int = 60, max_retries: int = 3):
        self.name = name
        self.primary_keys = [k.strip().strip('"').strip("'") for k in primary_keys if k.strip()]
        self.fallback_keys = [k.strip().strip('"').strip("'") for k in fallback_keys if k.strip()]
        self.unused_keys = [k.strip().strip('"').strip("'") for k in unused_keys if k.strip()]
        self.base_url = base_url
        self.default_model = default_model
        self.models = models or []
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.all_keys = self.primary_keys + self.fallback_keys
        
        self.key_index = 0
        self.key_stats = {key: {"success": 0, "failures": 0, "last_used": None, "type": self._get_key_type(key)} 
                         for key in self.all_keys}
    
    def _get_key_type(self, key: str) -> str:
        if key in self.primary_keys:
            return "primary"
        elif key in self.fallback_keys:
            return "fallback"
        return "unknown"
    
    def get_available_keys(self) -> List[str]:
        return self.all_keys
    
    def get_next_key(self) -> Optional[str]:
        if not self.all_keys:
            return None
        key = self.all_keys[self.key_index % len(self.all_keys)]
        self.key_index += 1
        return key
    
    def get_healthy_key(self) -> Optional[str]:
        if not self.all_keys:
            return None
        
        def health_score(key):
            stats = self.key_stats[key]
            total = stats["success"] + stats["failures"]
            if total == 0:
                return 0 if stats["type"] == "primary" else 0.5
            return stats["failures"] / max(total, 1)
        
        return min(self.all_keys, key=health_score)
    
    def record_result(self, key: str, success: bool):
        if key in self.key_stats:
            if success:
                self.key_stats[key]["success"] += 1
            else:
                self.key_stats[key]["failures"] += 1
            self.key_stats[key]["last_used"] = datetime.now()
    
    def promote_to_primary(self, key: str) -> bool:
        if key in self.fallback_keys:
            self.fallback_keys.remove(key)
            self.primary_keys.append(key)
            self.all_keys = self.primary_keys + self.fallback_keys
            self.key_stats[key]["type"] = "primary"
            return True
        elif key in self.unused_keys:
            self.unused_keys.remove(key)
            self.primary_keys.append(key)
            self.all_keys = self.primary_keys + self.fallback_keys
            self.key_stats[key] = {"success": 0, "failures": 0, "last_used": None, "type": "primary"}
            return True
        return False
    
    def demote_to_fallback(self, key: str) -> bool:
        if key in self.primary_keys:
            self.primary_keys.remove(key)
            self.fallback_keys.append(key)
            self.all_keys = self.primary_keys + self.fallback_keys
            self.key_stats[key]["type"] = "fallback"
            return True
        return False
    
    def get_proxy_config(self) -> Optional[Dict[str, str]]:
        if not self.proxy:
            return None
        return {"http": self.proxy, "https": self.proxy}
    
    def get_client_kwargs(self) -> Dict[str, Any]:
        kwargs = {"timeout": self.timeout}
        proxy_config = self.get_proxy_config()
        if proxy_config:
            kwargs["proxy"] = proxy_config
        return kwargs


def normalize_provider_base_url(base_url: Optional[str], default_base: str) -> str:
    candidate = (base_url or default_base).strip().rstrip("/")
    if candidate.endswith("/openai/v1"):
        return candidate
    if candidate.endswith("/openai"):
        return candidate + "/v1"
    if candidate.endswith("/v1"):
        return candidate
    return candidate


class AIProviderManager:
    """Manages multiple AI providers with multi-key support and custom endpoints."""
    
    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {}
        self.default_provider = os.environ.get("DEFAULT_PROVIDER", "ollama").lower()
        self.load_providers_from_env()
        self.offline_mode = not check_network_connectivity()
    
    def load_providers_from_env(self):
        provider_patterns = {
            "groq": {
                "base_url_env": "GROQ_BASE_URL",
                "default_model": "llama-3.3-70b-versatile",
                "default_base": "https://api.groq.com/openai/v1",
                "client_type": "groq",
                "requires_key": True
            },
            "openrouter": {
                "base_url_env": "OPENROUTER_BASE_URL",
                "default_model": "openrouter/free",
                "default_base": "https://openrouter.ai/api/v1",
                "client_type": "openai",
                "requires_key": True
            },
            "mistral": {
                "base_url_env": "MISTRAL_BASE_URL",
                "default_model": "mistral-small-latest",
                "default_base": "https://api.mistral.ai/v1",
                "client_type": "openai",
                "requires_key": True
            },
            "anthropic": {
                "base_url_env": "ANTHROPIC_BASE_URL",
                "default_model": "claude-3-haiku-20240307",
                "default_base": "https://api.anthropic.com/v1",
                "client_type": "anthropic",
                "requires_key": True
            },
            "deepseek": {
                "base_url_env": "DEEPSEEK_BASE_URL",
                "default_model": "deepseek-chat",
                "default_base": "https://api.deepseek.com/v1",
                "client_type": "openai",
                "requires_key": True
            },
            "together": {
                "base_url_env": "TOGETHER_BASE_URL",
                "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "default_base": "https://api.together.xyz/v1",
                "client_type": "openai",
                "requires_key": True
            },
            "ollama": {
                "base_url_env": "OLLAMA_BASE_URL",
                "default_model": "llama3.1",
                "default_base": "http://localhost:11434/v1",
                "client_type": "openai",
                "requires_key": False
            }
        }
        
        for provider, config in provider_patterns.items():
            keys = load_keys_from_env(provider)
            
            if config.get("requires_key", True) and not (keys["primary"] or keys["fallback"] or keys["unused"]):
                continue
            
            base_url = os.environ.get(config["base_url_env"], config["default_base"])
            default_model = os.environ.get(
                f"{provider.upper()}_DEFAULT_MODEL",
                config["default_model"]
            )
            models_str = os.environ.get(f"{provider.upper()}_MODELS", "")
            models = [m.strip() for m in models_str.split(",") if m.strip()] if models_str else []
            
            proxy = os.environ.get(f"{provider.upper()}_PROXY", None)
            timeout = int(os.environ.get(f"{provider.upper()}_TIMEOUT", "60"))
            max_retries = int(os.environ.get(f"{provider.upper()}_MAX_RETRIES", "3"))
            
            self.providers[provider] = ProviderConfig(
                name=provider,
                primary_keys=keys["primary"],
                fallback_keys=keys["fallback"],
                unused_keys=keys["unused"],
                base_url=base_url,
                default_model=default_model,
                models=models,
                proxy=proxy,
                timeout=timeout,
                max_retries=max_retries
            )
        
        if self.default_provider not in self.providers:
            if self.providers:
                self.default_provider = list(self.providers.keys())[0]
                console.print(f"[yellow]Default provider '{self.default_provider}' not found, using {self.default_provider}[/yellow]")
    
    def get_provider(self, provider_name: Optional[str] = None) -> Optional[ProviderConfig]:
        name = (provider_name or self.default_provider).lower()
        return self.providers.get(name)
    
    def get_all_providers(self) -> List[str]:
        return list(self.providers.keys())
    
    def get_all_free_models(self) -> Dict[str, List[str]]:
        all_models = {}
        for name, config in self.providers.items():
            if config.models:
                free_models = [m for m in config.models if ":free" in m or m in ["openrouter/free", "openrouter/auto"]]
                all_models[name] = free_models if free_models else config.models
            else:
                all_models[name] = [config.default_model]
        return all_models
    
    def check_provider_available(self, provider_name: str) -> bool:
        config = self.get_provider(provider_name)
        if not config:
            return False
        
        if provider_name == "ollama":
            try:
                import requests
                response = requests.get(f"{config.base_url}/models", timeout=2)
                return response.status_code == 200
            except:
                return False
        
        return check_network_connectivity()
    
    def get_client(self, provider_name: Optional[str] = None, model_override: Optional[str] = None):
        provider_config = self.get_provider(provider_name)
        if not provider_config:
            return None, None, None
        
        provider_lower = provider_config.name.lower()

        if not self.check_provider_available(provider_lower):
            if provider_lower == "ollama":
                console.print("[yellow]Ollama service not running. Please start Ollama first.[/yellow]")
                console.print("[dim]Run: ollama serve[/dim]")
            else:
                console.print(f"[yellow]Provider '{provider_lower}' not available.[/yellow]")
            return None, None, None

        if provider_lower == "ollama":
            key = "ollama-local"
        else:
            key = provider_config.get_healthy_key()
            if not key:
                return None, None, None
        
        client_type = "openai"
        
        if provider_lower == "groq":
            client_type = "groq"
        elif provider_lower == "anthropic":
            client_type = "anthropic"
        elif provider_lower == "openrouter":
            client_type = "openai"
        else:
            client_type = os.environ.get(f"{provider_lower.upper()}_CLIENT_TYPE", "openai")
        
        try:
            if client_type == "groq":
                groq_base_url = normalize_provider_base_url(
                    provider_config.base_url,
                    "https://api.groq.com/openai/v1"
                )
                client = Groq(api_key=key, base_url=groq_base_url)
                client._key = key
                client._provider = provider_config
            else:
                base_url = normalize_provider_base_url(
                    provider_config.base_url,
                    provider_config.base_url or "https://api.openai.com/v1"
                )
                kwargs = provider_config.get_client_kwargs()
                
                http_client = None
                if provider_config.proxy:
                    import httpx
                    http_client = httpx.Client(proxy=provider_config.proxy)
                    kwargs["http_client"] = http_client
                
                if provider_lower == "ollama":
                    api_key = "ollama"
                else:
                    api_key = key
                
                client = OpenAI(
                    base_url=base_url,
                    api_key=api_key,
                    **{k: v for k, v in kwargs.items() if k not in ["proxy"]}
                )
                client._key = key
                client._provider = provider_config
            
            model = model_override or provider_config.default_model
            return client, model, provider_config
            
        except Exception as e:
            console.print(f"[red]Error creating client for {provider_name}: {e}[/red]")
            if hasattr(provider_config, "record_result") and key:
                provider_config.record_result(key, False)
            return None, None, None


provider_manager = AIProviderManager()

def require_client(provider: Optional[str] = None, model_override: Optional[str] = None):
    """Get AI client with automatic retry and key rotation."""
    max_attempts = 3
    
    if not check_network_connectivity():
        provider_name = provider or provider_manager.default_provider
        if provider_name == "ollama":
            client, model, _ = provider_manager.get_client(provider, model_override)
            if client:
                return client, model
        console.print("[yellow]⚠️ No network connection. Some features may be limited.[/yellow]")
        console.print("[dim]Use 'ollama' provider for offline mode.[/dim]")
        
        if "ollama" in provider_manager.get_all_providers():
            console.print("[dim]Trying Ollama...[/dim]")
            client, model, _ = provider_manager.get_client("ollama", model_override)
            if client:
                return client, model
        
        console.print("[yellow]Using offline mode with limited functionality.[/yellow]")
        return None, None
    
    for attempt in range(max_attempts):
        client, model, provider_config = provider_manager.get_client(provider, model_override)
        
        if client and provider_config:
            try:
                test_response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                if hasattr(client, '_key') and client._key:
                    provider_config.record_result(client._key, True)
                return client, model
            except Exception as e:
                error_str = str(e)
                
                if "connection" in error_str.lower() or "timeout" in error_str.lower():
                    if attempt < max_attempts - 1:
                        console.print(f"[yellow]Connection error, retrying... ({attempt + 1}/{max_attempts})[/yellow]")
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        console.print("[red]Connection failed. Check your network and API keys.[/red]")
                        break
                
                if "402" in error_str or "credits" in error_str or "free" in error_str:
                    if hasattr(client, '_key') and client._key:
                        provider_config.record_result(client._key, False)
                    
                    if attempt < max_attempts - 1:
                        console.print(f"[yellow]⚠️ No credits for key... Trying next key...[/yellow]")
                        continue
                
                if "429" in error_str or "Rate limit" in error_str:
                    if hasattr(client, '_key') and client._key:
                        provider_config.record_result(client._key, False)
                    if attempt < max_attempts - 1:
                        console.print(f"[yellow]⏳ Rate limited. Waiting before retry...[/yellow]")
                        time.sleep(2 ** attempt)
                        continue
                
                if hasattr(client, '_key') and client._key:
                    provider_config.record_result(client._key, False)
                
                if attempt < max_attempts - 1:
                    wait = 2 ** attempt
                    console.print(f"[yellow]Error, retrying in {wait}s... ({e})[/yellow]")
                    time.sleep(wait)
                continue
        elif attempt < max_attempts - 1:
            time.sleep(1)
    
    active_prov = provider or provider_manager.default_provider
    console.print(f"\n[bold red]Naze's brain for provider '{active_prov}' is offline.[/bold red]")
    console.print("Please check your API keys in the [cyan].env[/cyan] file.")
    console.print(f"Configured providers: {', '.join(provider_manager.get_all_providers())}\n")
    
    if "ollama" in provider_manager.get_all_providers():
        console.print("[dim]Attempting to use Ollama...[/dim]")
        client, model, _ = provider_manager.get_client("ollama", model_override)
        if client:
            return client, model
    
    raise typer.Exit(code=1)


def prompt_Naze_with_retry(task_input: str, provider: Optional[str] = None, 
                          model_override: Optional[str] = None, max_retries: int = 3):
    """Enhanced prompt function with free model support and key rotation."""
    global current_working_dir, username
    
    if not check_network_connectivity():
        if "ollama" in provider_manager.get_all_providers():
            try:
                client, model = require_client("ollama", model_override)
                if client:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are Naze, a task classifier. Return JSON only."},
                            {"role": "user", "content": f"Classify this task: {task_input}"}
                        ],
                        temperature=0.2
                    )
                    content = response.choices[0].message.content
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        return json_match.group()
                    return content
            except:
                pass
        console.print("[yellow]No network and Ollama not available. Using fallback task creation.[/yellow]")
        fallback = {
            "task": task_input[:100],
            "energy": 3,
            "impact": 50,
            "category": "General",
            "Naze_note": "Created in offline mode"
        }
        return json.dumps(fallback)
    
    if not model_override:
        all_models = provider_manager.get_all_free_models()
        models_to_try = []
        if "openrouter" in all_models and all_models["openrouter"]:
            models_to_try.extend(all_models["openrouter"])
        for prov, models in all_models.items():
            if prov != "openrouter" and models:
                models_to_try.extend(models)
        seen = set()
        models_to_try = [x for x in models_to_try if not (x in seen or seen.add(x))]
    else:
        models_to_try = [model_override]
    
    for attempt in range(max_retries):
        for current_model in models_to_try[:3]:
            try:
                client, model = require_client(provider, current_model)
                if not client:
                    continue
                
                system_instructions = f'''
You are Naze, a focused, highly-capable task classification engine.

Return ONLY one JSON object and nothing else.
Schema: {{"task": string, "energy": integer(1-5), "impact": integer(1-100), "category": string, "Naze_note": string}}

If uncertain, use sensible defaults: energy=3, impact=50, category="General".

Context:
- Working directory: {current_working_dir}
- User: {username}

Return raw JSON only.
'''
                
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": task_input}
                        ],
                        temperature=0.2,
                        response_format={"type": "json_object"}
                    )
                except (TypeError, AttributeError):
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": task_input}
                        ],
                        temperature=0.2
                    )
                
                content = response.choices[0].message.content
                
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json_match.group()
                return content
                
            except Exception as e:
                console.print(f"[yellow]Model {current_model} failed: {e}[/yellow]")
                continue
        
        if attempt < max_retries - 1:
            console.print(f"[dim]Retrying with different model/key...[/dim]")
            time.sleep(2 ** attempt)
    
    console.print("[bold red]All models and keys failed.[/bold red]")
    fallback = {
        "task": task_input[:100],
        "energy": 3,
        "impact": 50,
        "category": "General",
        "Naze_note": "Failed to classify, using defaults"
    }
    return json.dumps(fallback)


# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

db_dir = Path.home() / ".local" / "share" / "Naze"
db_dir.mkdir(parents=True, exist_ok=True)
db_path = db_dir / "tasks.db"

def get_db_conn():
    conn = sqlite3.connect(str(db_path))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            energy INTEGER,       
            impact INTEGER,       
            category TEXT,        
            Naze_note TEXT,       
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            due_date TIMESTAMP,
            priority INTEGER DEFAULT 0,
            tags TEXT,
            project TEXT,
            parent_id INTEGER,
            completed_at TIMESTAMP
        )
    ''')
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [column[1] for column in cursor.fetchall()]
    
    columns_to_add = {
        'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
        'due_date': 'TIMESTAMP',
        'priority': 'INTEGER DEFAULT 0',
        'tags': 'TEXT',
        'project': 'TEXT',
        'parent_id': 'INTEGER',
        'completed_at': 'TIMESTAMP'
    }
    
    for col, type_def in columns_to_add.items():
        if col not in columns:
            try:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} {type_def}")
            except sqlite3.OperationalError:
                pass
    
    conn.commit()
    return conn


def get_task_stats() -> Dict[str, Any]:
    conn = get_db_conn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'complete'")
    completed = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(energy) FROM tasks WHERE status = 'pending'")
    avg_energy = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT AVG(impact) FROM tasks WHERE status = 'pending'")
    avg_impact = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT category, COUNT(*) FROM tasks GROUP BY category ORDER BY COUNT(*) DESC LIMIT 5")
    top_categories = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE due_date IS NOT NULL AND due_date < datetime('now') AND status = 'pending'")
    overdue = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total": total,
        "pending": pending,
        "completed": completed,
        "completion_rate": (completed / total * 100) if total > 0 else 0,
        "avg_energy": avg_energy,
        "avg_impact": avg_impact,
        "top_categories": top_categories,
        "overdue": overdue
    }


def get_tasks_by_status(status: str = "pending") -> List[Dict]:
    conn = get_db_conn()
    cursor = conn.cursor()
    
    query = """
        SELECT id, task, energy, impact, category, Naze_note, status, 
               created_at, due_date, priority, tags, project
        FROM tasks 
        WHERE status = ?
        ORDER BY priority DESC, impact DESC, created_at ASC
    """
    cursor.execute(query, (status,))
    rows = cursor.fetchall()
    conn.close()
    
    tasks = []
    for row in rows:
        tasks.append({
            "id": row[0],
            "task": row[1],
            "energy": row[2],
            "impact": row[3],
            "category": row[4],
            "note": row[5],
            "status": row[6],
            "created_at": row[7],
            "due_date": row[8],
            "priority": row[9],
            "tags": row[10].split(",") if row[10] else [],
            "project": row[11]
        })
    return tasks


def get_task_by_id(task_id: int) -> Optional[Dict]:
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, task, energy, impact, category, Naze_note, status, 
               created_at, updated_at, due_date, priority, tags, project, parent_id, completed_at
        FROM tasks WHERE id = ?
    """, (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "task": row[1],
        "energy": row[2],
        "impact": row[3],
        "category": row[4],
        "note": row[5],
        "status": row[6],
        "created_at": row[7],
        "updated_at": row[8],
        "due_date": row[9],
        "priority": row[10],
        "tags": row[11].split(",") if row[11] else [],
        "project": row[12],
        "parent_id": row[13],
        "completed_at": row[14]
    }


def update_task(task_id: int, **kwargs) -> bool:
    conn = get_db_conn()
    cursor = conn.cursor()
    
    set_clause = []
    values = []
    
    for key, value in kwargs.items():
        if key in ['task', 'energy', 'impact', 'category', 'Naze_note', 'status', 
                   'due_date', 'priority', 'tags', 'project', 'parent_id']:
            set_clause.append(f"{key} = ?")
            values.append(value)
    
    if not set_clause:
        return False
    
    set_clause.append("updated_at = CURRENT_TIMESTAMP")
    values.append(task_id)
    
    query = f"UPDATE tasks SET {', '.join(set_clause)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    return True


def create_subtask(parent_id: int, task_data: Dict) -> Optional[int]:
    conn = get_db_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO tasks (task, energy, impact, category, Naze_note, parent_id, project)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        task_data.get('task'),
        task_data.get('energy', 3),
        task_data.get('impact', 50),
        task_data.get('category', 'General'),
        task_data.get('Naze_note', ''),
        parent_id,
        task_data.get('project')
    ))
    
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return task_id


def delete_task(task_id: int, force: bool = False) -> bool:
    conn = get_db_conn()
    cursor = conn.cursor()
    
    if force:
        cursor.execute("DELETE FROM tasks WHERE parent_id = ?", (task_id,))
    
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return True


# ============================================================================
# FILE OPERATIONS - IMPROVED WITH SMRX
# ============================================================================

class FileOperation:
    """File operations utility class with proper encoding handling and SMRX support."""
    
    @staticmethod
    def read_file(filepath: str, binary: bool = False) -> Optional[str]:
        """Read a file with automatic encoding detection."""
        try:
            full_path = Path(current_working_dir) / filepath
            if not full_path.exists():
                return None
            
            if binary:
                with open(full_path, 'rb') as f:
                    return f.read()
            
            # Try multiple encodings
            encodings = ['utf-8', 'utf-16', 'cp1252', 'latin-1', 'ascii', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    with open(full_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        if content and len(content) > 0:
                            return content
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            # Fallback: read as binary and decode with replacement
            with open(full_path, 'rb') as f:
                raw = f.read()
                return raw.decode('utf-8', errors='replace')
                
        except Exception as e:
            return None
    
    @staticmethod
    def write_file(filepath: str, content: str, binary: bool = False) -> bool:
        try:
            full_path = Path(current_working_dir) / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            if binary:
                with open(full_path, 'wb') as f:
                    f.write(content)
            else:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            return True
        except Exception:
            return False
    
    @staticmethod
    def append_file(filepath: str, content: str) -> bool:
        try:
            full_path = Path(current_working_dir) / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'a', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete_file(filepath: str) -> bool:
        try:
            full_path = Path(current_working_dir) / filepath
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    @staticmethod
    def list_files(pattern: str = "*", recursive: bool = False) -> List[str]:
        try:
            search_path = Path(current_working_dir)
            if recursive:
                files = list(search_path.rglob(pattern))
            else:
                files = list(search_path.glob(pattern))
            return [str(f.relative_to(search_path)) for f in files if f.is_file()]
        except Exception:
            return []
    
    @staticmethod
    def get_file_info(filepath: str) -> Optional[Dict]:
        try:
            full_path = Path(current_working_dir) / filepath
            if not full_path.exists():
                return None
            
            stat = full_path.stat()
            return {
                "name": full_path.name,
                "path": str(full_path),
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime),
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "is_dir": full_path.is_dir(),
                "extension": full_path.suffix
            }
        except Exception:
            return None
    
    @staticmethod
    def copy_file(src: str, dst: str) -> bool:
        try:
            src_path = Path(current_working_dir) / src
            dst_path = Path(current_working_dir) / dst
            if src_path.exists():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                return True
            return False
        except Exception:
            return False
    
    @staticmethod
    def move_file(src: str, dst: str) -> bool:
        try:
            src_path = Path(current_working_dir) / src
            dst_path = Path(current_working_dir) / dst
            if src_path.exists():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(src_path, dst_path)
                return True
            return False
        except Exception:
            return False
    
    @staticmethod
    def search_files(query: str, pattern: str = "*", use_regex: bool = False,
                    max_results: int = 500, include_context: bool = False) -> List[Dict]:
        """Search files using SMRX regex engine or simple text search."""
        results = []
        
        # Use SMRX for regex searches
        if use_regex and smrx_wrapper.available:
            result = smrx_wrapper.search(
                current_working_dir,
                query,
                file_pattern=pattern,
                max_results=max_results
            )
            
            if "error" in result:
                console.print(f"[yellow]SMRX error: {result['error']}[/yellow]")
                return results
            
            # Process matches with better grouping
            file_matches = {}
            for match in result.get('matches', []):
                filepath = match['file']
                if filepath not in file_matches:
                    file_matches[filepath] = {
                        "file": filepath,
                        "matches": 0,
                        "lines": []
                    }
                
                file_matches[filepath]["matches"] += 1
                file_matches[filepath]["lines"].append({
                    "line": match['line'],
                    "content": match['text'],
                    "match": match['match'],
                    "col": match['col']
                })
            
            # Sort and limit results
            sorted_results = sorted(file_matches.values(), 
                                  key=lambda x: x["matches"], 
                                  reverse=True)
            
            # Add context lines if requested
            if include_context:
                for file_data in sorted_results:
                    content = FileOperation.read_file(file_data["file"])
                    if content:
                        lines = content.splitlines()
                        for line_data in file_data["lines"]:
                            line_num = line_data["line"]
                            context_before = lines[max(0, line_num-3):line_num-1] if line_num > 1 else []
                            context_after = lines[line_num:min(len(lines), line_num+2)] if line_num < len(lines) else []
                            line_data["context_before"] = context_before
                            line_data["context_after"] = context_after
            
            return sorted_results
        
        # Fallback to simple text search
        for filepath in FileOperation.list_files(pattern, recursive=True):
            content = FileOperation.read_file(filepath)
            if content and query.lower() in content.lower():
                lines = []
                for i, line in enumerate(content.split('\n'), 1):
                    if query.lower() in line.lower():
                        lines.append({
                            "line": i,
                            "content": line.strip(),
                            "match": query
                        })
                if lines:
                    results.append({
                        "file": filepath,
                        "matches": len(lines),
                        "lines": lines[:5]
                    })
        return results

    @staticmethod
    def regex_search(regex_str: str, pattern: str = "*", max_results: int = 500) -> Dict:
        """Advanced regex search using SMRX."""
        if not smrx_wrapper.available:
            return {"error": "SMRX regex engine not available. Install smrx module."}
        
        is_valid, error = smrx_wrapper.validate(regex_str)
        if not is_valid:
            return {"error": f"Invalid regex pattern: {error}"}
        
        result = smrx_wrapper.search(
            current_working_dir,
            regex_str,
            file_pattern=pattern,
            max_results=max_results
        )
        
        if "error" in result:
            return result
        
        return {
            "query": regex_str,
            "pattern": pattern,
            "files_searched": result.get('files_searched', 0),
            "matches_found": result.get('matches_found', 0),
            "execution_time": result.get('execution_time', 0),
            "matches": result.get('matches', [])
        }


# ============================================================================
# COMMANDS - TASK MANAGEMENT
# ============================================================================

@app.command()
def add(
    description: str = typer.Argument(..., help="Detailed description of the task for Naze's analysis."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Specific model to use"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to use"),
    due_date: Optional[str] = typer.Option(None, "--due", "-d", help="Due date (YYYY-MM-DD)"),
    priority: int = typer.Option(0, "--priority", "-P", help="Priority (0-10)"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
    project: Optional[str] = typer.Option(None, "--project", "-pr", help="Project name"),
    parent: Optional[int] = typer.Option(None, "--parent", help="Parent task ID")
):
    with console.status("[bold cyan]Naze is thinking...", spinner="dots"):
        raw_json = prompt_Naze_with_retry(description, provider, model)
    
    if raw_json:
        try:
            data = json.loads(raw_json)
            conn = get_db_conn()
            cursor = conn.cursor()
            
            due_date_parsed = None
            if due_date:
                try:
                    due_date_parsed = datetime.strptime(due_date, "%Y-%m-%d").isoformat()
                except ValueError:
                    console.print(f"[yellow]Invalid due date format. Use YYYY-MM-DD.[/yellow]")
            
            cursor.execute('''
                INSERT INTO tasks 
                (task, energy, impact, category, Naze_note, due_date, priority, tags, project, parent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('task', description),
                data.get('energy', 3),
                data.get('impact', 50),
                data.get('category', 'General'),
                data.get('Naze_note', ''),
                due_date_parsed,
                priority,
                tags,
                project,
                parent
            ))
            task_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            console.print(f"[green]✓ Task Added:[/green] {data.get('task', description)}")
            console.print(f"[dim]ID: {task_id} | Energy: {data.get('energy', 3)}/5 | Impact: {data.get('impact', 50)}%[/dim]")
            if data.get('Naze_note'):
                console.print(f"[dim italic]Naze's note: {data.get('Naze_note')}[/dim italic]")
        except Exception as e:
            console.print(f"[red]Database Error: {e}[/red]")
    else:
        console.print("[red]AI returned no data. Task not added.[/red]")


@app.command(name="list")
def list_tasks(
    status: Optional[str] = typer.Option("pending", "--status", "-s", help="Filter by status (pending, complete, all)"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    project: Optional[str] = typer.Option(None, "--project", "-pr", help="Filter by project"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    limit: int = typer.Option(50, "--limit", "-l", help="Limit results")
):
    conn = get_db_conn()
    cursor = conn.cursor()
    
    query = """
        SELECT id, task, energy, impact, status, Naze_note, category, created_at, due_date, priority, tags, project
        FROM tasks WHERE 1=1
    """
    params = []
    
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    elif status == "all":
        query += " AND status IN ('pending', 'complete')"
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if project:
        query += " AND project = ?"
        params.append(project)
    
    if tag:
        query += " AND tags LIKE ?"
        params.append(f"%{tag}%")
    
    query += " ORDER BY priority DESC, impact DESC, created_at ASC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        console.print("[yellow]No tasks found matching the criteria.[/yellow]")
        return
    
    table = Table(title="Naze's Task List", header_style="bold magenta")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Cat", style="yellow")
    table.add_column("Task", style="white")
    table.add_column("E", justify="center")
    table.add_column("Impact", justify="center")
    table.add_column("Priority", justify="center")
    table.add_column("Status", style="dim")
    table.add_column("Due", style="dim")
    table.add_column("Project", style="dim")
    
    for row in rows:
        task_id, task, energy, impact, status, note, category, created_at, due_date, priority, tags, project = row
        
        status_color = "green" if status == "complete" else "yellow" if status == "pending" else "red"
        
        due_str = due_date[:10] if due_date else "—"
        if due_date and datetime.now() > datetime.fromisoformat(due_date):
            due_str = f"[red]{due_str}[/red]"
        
        task_display = task[:50] + "..." if len(task) > 50 else task
        
        table.add_row(
            str(task_id),
            category if category else "General",
            task_display,
            "⚡" * (energy or 0),
            f"{impact}%",
            f"{'⭐' * (priority // 3) if priority > 0 else '—'}",
            f"[{status_color}]{status}[/{status_color}]",
            due_str,
            project if project else "—"
        )
    
    console.print(table)
    
    stats = get_task_stats()
    console.print(f"\n[dim]Showing {len(rows)} tasks | Pending: {stats['pending']} | Completed: {stats['completed']} | Overdue: {stats['overdue']}[/dim]")


@app.command()
def show(task_id: int = typer.Argument(..., help="Task ID to show details for")):
    task = get_task_by_id(task_id)
    
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        return
    
    created = task['created_at'][:19] if task['created_at'] else "—"
    updated = task['updated_at'][:19] if task['updated_at'] else "—"
    due = task['due_date'][:10] if task['due_date'] else "—"
    completed = task['completed_at'][:19] if task['completed_at'] else "—"
    
    info = [
        f"[bold]ID:[/bold] {task['id']}",
        f"[bold]Task:[/bold] {task['task']}",
        f"[bold]Category:[/bold] {task['category'] or 'General'}",
        f"[bold]Status:[/bold] {task['status']}",
        f"[bold]Energy:[/bold] {'⚡' * (task['energy'] or 0)} ({task['energy']}/5)",
        f"[bold]Impact:[/bold] {task['impact']}%",
        f"[bold]Priority:[/bold] {'⭐' * (task['priority'] // 3) if task['priority'] > 0 else '—'} ({task['priority']}/10)",
        f"[bold]Project:[/bold] {task['project'] or '—'}",
        f"[bold]Tags:[/bold] {', '.join(task['tags']) if task['tags'] else '—'}",
        f"[bold]Created:[/bold] {created}",
        f"[bold]Updated:[/bold] {updated}",
        f"[bold]Due Date:[/bold] {due}",
        f"[bold]Completed:[/bold] {completed}",
        f"[bold]Note:[/bold] {task['note'] or '—'}"
    ]
    
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, task, status FROM tasks WHERE parent_id = ?", (task_id,))
    subtasks = cursor.fetchall()
    conn.close()
    
    if subtasks:
        info.append(f"\n[bold]Subtasks:[/bold]")
        for sub_id, sub_task, sub_status in subtasks:
            info.append(f"  • [{sub_status}] #{sub_id}: {sub_task}")
    
    if task['parent_id']:
        parent = get_task_by_id(task['parent_id'])
        if parent:
            info.append(f"\n[bold]Parent Task:[/bold] #{parent['id']}: {parent['task']}")
    
    console.print(Panel("\n".join(info), title=f"Task #{task_id}", border_style="cyan"))


@app.command()
def edit(
    task_id: int = typer.Argument(..., help="Task ID to edit"),
    task: Optional[str] = typer.Option(None, "--task", "-t", help="New task description"),
    energy: Optional[int] = typer.Option(None, "--energy", "-e", help="New energy level (1-5)"),
    impact: Optional[int] = typer.Option(None, "--impact", "-i", help="New impact (1-100)"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="New category"),
    note: Optional[str] = typer.Option(None, "--note", "-n", help="New Naze note"),
    due_date: Optional[str] = typer.Option(None, "--due", "-d", help="New due date (YYYY-MM-DD)"),
    priority: Optional[int] = typer.Option(None, "--priority", "-P", help="New priority (0-10)"),
    tags: Optional[str] = typer.Option(None, "--tags", help="New tags (comma-separated)"),
    project: Optional[str] = typer.Option(None, "--project", "-pr", help="New project"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="New status (pending/complete)")
):
    existing = get_task_by_id(task_id)
    if not existing:
        console.print(f"[red]Task {task_id} not found.[/red]")
        return
    
    updates = {}
    if task is not None:
        updates['task'] = task
    if energy is not None:
        updates['energy'] = energy
    if impact is not None:
        updates['impact'] = impact
    if category is not None:
        updates['category'] = category
    if note is not None:
        updates['Naze_note'] = note
    if due_date is not None:
        try:
            updates['due_date'] = datetime.strptime(due_date, "%Y-%m-%d").isoformat()
        except ValueError:
            console.print("[yellow]Invalid due date format. Use YYYY-MM-DD.[/yellow]")
    if priority is not None:
        updates['priority'] = priority
    if tags is not None:
        updates['tags'] = tags
    if project is not None:
        updates['project'] = project
    if status is not None:
        if status in ['pending', 'complete']:
            updates['status'] = status
            if status == 'complete':
                updates['completed_at'] = datetime.now().isoformat()
        else:
            console.print("[yellow]Invalid status. Use 'pending' or 'complete'.[/yellow]")
    
    if not updates:
        console.print("[yellow]No changes specified.[/yellow]")
        return
    
    if update_task(task_id, **updates):
        console.print(f"[green]✓ Task {task_id} updated successfully.[/green]")
    else:
        console.print("[red]Failed to update task.[/red]")


@app.command()
def finish(task_ids: list[int] = typer.Argument(..., help="The ID(s) of the task to mark as finished")):
    conn = get_db_conn()
    cursor = conn.cursor()
    
    finished_names = []
    for task_id in task_ids:
        cursor.execute("SELECT task FROM tasks WHERE id = ? AND status = 'pending'", (task_id,))
        result = cursor.fetchone()
        if result:
            cursor.execute("UPDATE tasks SET status = 'complete', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
            finished_names.append(result[0])
        else:
            console.print(f"[dim red]Task ID {task_id} not found or already finished.[/dim red]")
    
    conn.commit()
    conn.close()
    
    if not finished_names:
        return
    
    console.print(Panel(f"[bold green]✓ Finished:[/bold green] {', '.join(finished_names)}", expand=False))
    
    try:
        client, model_name = require_client()
        if client:
            with console.status("[italic]Naze is writing a backhanded compliment...", spinner="dots"):
                task_context = "; ".join(finished_names)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are Naze, a witty task manager. Give a single, very short, clever, and slightly sarcastic congratulation for finishing these tasks. One sentence max."},
                        {"role": "user", "content": f"I finished: {task_context}"}
                    ],
                    temperature=0.8
                )
                message = response.choices[0].message.content
                console.print(f"[bold magenta]Naze:[/bold magenta] [italic]{message}[/italic]\n")
        else:
            console.print("[dim italic]Naze nods in silent, skeptical approval.[/dim italic]\n")
    except Exception:
        console.print("[dim italic]Naze nods in silent, skeptical approval.[/dim italic]\n")


@app.command()
def delete(task_ids: list[int] = typer.Argument(..., help="The ID(s) of the task(s) to remove.")):
    if not task_ids:
        console.print("[bold red]Error:[/bold red] Please provide at least one task ID to delete.")
        return
    
    conn = get_db_conn()
    cursor = conn.cursor()
    deleted_count = 0
    
    for task_id in task_ids:
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if cursor.fetchone():
            cursor.execute("SELECT id, task FROM tasks WHERE parent_id = ?", (task_id,))
            subtasks = cursor.fetchall()
            
            if subtasks:
                console.print(f"[yellow]Task {task_id} has {len(subtasks)} subtasks:[/yellow]")
                for sub_id, sub_task in subtasks:
                    console.print(f"  • #{sub_id}: {sub_task}")
                if not typer.confirm(f"Delete task {task_id} and all its subtasks?"):
                    continue
            
            cursor.execute("DELETE FROM tasks WHERE parent_id = ?", (task_id,))
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            console.print(f"[green]✓ Task Deleted:[/green] {task_id}")
            deleted_count += 1
        else:
            console.print(f"[bold red]Error:[/bold red] Task ID {task_id} not found.")
    
    conn.commit()
    conn.close()
    
    if deleted_count > 0:
        console.print(f"[green]✓ Successfully deleted {deleted_count} tasks.[/green]")
    else:
        console.print("[yellow]No tasks were deleted.[/yellow]")


@app.command()
def clear():
    if typer.confirm("Are you sure you want to delete ALL tasks?"):
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks")
        conn.commit()
        conn.close()
        console.print("[green]✓ All Tasks Deleted.[/green]")


@app.command()
def subtask(
    parent_id: int = typer.Argument(..., help="Parent task ID"),
    description: str = typer.Argument(..., help="Subtask description"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Specific model to use"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to use")
):
    parent = get_task_by_id(parent_id)
    if not parent:
        console.print(f"[red]Parent task {parent_id} not found.[/red]")
        return
    
    with console.status("[bold cyan]Naze is thinking...", spinner="dots"):
        raw_json = prompt_Naze_with_retry(description, provider, model)
    
    if raw_json:
        try:
            data = json.loads(raw_json)
            task_id = create_subtask(parent_id, data)
            
            if task_id:
                console.print(f"[green]✓ Subtask Added:[/green] {data.get('task', description)}")
                console.print(f"[dim]ID: {task_id} | Parent: #{parent_id}[/dim]")
            else:
                console.print("[red]Failed to create subtask.[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    else:
        console.print("[red]AI returned no data. Subtask not added.[/red]")


@app.command()
def stats():
    stats = get_task_stats()
    
    console.print(Panel(
        f"[bold]Task Statistics[/bold]\n\n"
        f"Total Tasks: {stats['total']}\n"
        f"Pending: {stats['pending']}\n"
        f"Completed: {stats['completed']}\n"
        f"Completion Rate: {stats['completion_rate']:.1f}%\n"
        f"Overdue: [red]{stats['overdue']}[/red]\n"
        f"Avg Energy: {stats['avg_energy']:.1f}/5\n"
        f"Avg Impact: {stats['avg_impact']:.1f}%",
        title="Naze's Dashboard",
        border_style="cyan"
    ))
    
    if stats['top_categories']:
        console.print("\n[bold]Top Categories:[/bold]")
        for cat, count in stats['top_categories']:
            bar = "█" * min(count, 20)
            console.print(f"  {cat}: {bar} ({count})")
    
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT priority, COUNT(*) FROM tasks 
        WHERE status = 'pending' 
        GROUP BY priority 
        ORDER BY priority DESC
    """)
    priorities = cursor.fetchall()
    conn.close()
    
    if priorities:
        console.print("\n[bold]Priority Breakdown:[/bold]")
        for pri, count in priorities:
            if pri == 0:
                console.print(f"  No Priority: {count}")
            else:
                console.print(f"  {'⭐' * (pri // 3)} ({pri}): {count}")


@app.command()
def today():
    conn = get_db_conn()
    cursor = conn.cursor()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT id, task, energy, impact, category, due_date, priority
        FROM tasks 
        WHERE status = 'pending' 
        AND due_date IS NOT NULL 
        AND due_date <= ?
        ORDER BY due_date ASC, priority DESC
    """, (today_str,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        console.print("[green]✓ No tasks due today! You're on top of things.[/green]")
        return
    
    table = Table(title="Today's Tasks", header_style="bold magenta")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Task", style="white")
    table.add_column("Due", style="dim")
    table.add_column("Priority", style="yellow")
    table.add_column("Status", style="dim")
    
    for row in rows:
        task_id, task, energy, impact, category, due_date, priority = row
        
        if due_date < today_str:
            status = "[red]OVERDUE[/red]"
        else:
            status = "[yellow]Due Today[/yellow]"
        
        table.add_row(
            str(task_id),
            task[:50] + "..." if len(task) > 50 else task,
            due_date[:10],
            "⭐" * (priority // 3) if priority > 0 else "—",
            status
        )
    
    console.print(table)


# ============================================================================
# COMMANDS - FILE OPERATIONS
# ============================================================================

@app.command()
def read(
    filepath: str = typer.Argument(..., help="File path to read"),
    lines: Optional[int] = typer.Option(None, "--lines", "-l", help="Number of lines to show from start"),
    tail: bool = typer.Option(False, "--tail", "-t", help="Show last N lines instead")
):
    content = FileOperation.read_file(filepath)
    if content is None:
        console.print(f"[red]Error: File '{filepath}' not found or unreadable.[/red]")
        return
    
    if lines and tail:
        lines_list = content.splitlines()
        if len(lines_list) > lines:
            content = "\n".join(lines_list[-lines:])
        console.print(Panel(content, title=f"📄 {filepath} (last {lines} lines)", border_style="cyan"))
    elif lines:
        lines_list = content.splitlines()
        if len(lines_list) > lines:
            content = "\n".join(lines_list[:lines])
        console.print(Panel(content, title=f"📄 {filepath} (first {lines} lines)", border_style="cyan"))
    else:
        console.print(Panel(content, title=f"📄 {filepath}", border_style="cyan"))


@app.command()
def write(
    filepath: str = typer.Argument(..., help="File path to write"),
    content: str = typer.Argument(..., help="Content to write"),
    append: bool = typer.Option(False, "--append", "-a", help="Append to file instead of overwriting")
):
    if append:
        success = FileOperation.append_file(filepath, content + "\n")
        action = "Appended to"
    else:
        success = FileOperation.write_file(filepath, content)
        action = "Wrote"
    
    if success:
        console.print(f"[green]✓ {action} {filepath}[/green]")
    else:
        console.print(f"[red]Error: Could not write to {filepath}[/red]")


@app.command(name="delete-file")
def delete_file(
    filepath: str = typer.Argument(..., help="File path to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation")
):
    if not force:
        if not typer.confirm(f"Delete file '{filepath}'?"):
            return
    
    success = FileOperation.delete_file(filepath)
    if success:
        console.print(f"[green]✓ Deleted: {filepath}[/green]")
    else:
        console.print(f"[red]Error: Could not delete {filepath}[/red]")


@app.command()
def ls(
    pattern: str = typer.Argument("*", help="File pattern (e.g., '*.py')"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Search recursively")
):
    global current_working_dir
    files = FileOperation.list_files(pattern, recursive)
    
    if not files:
        console.print(f"[yellow]No files matching '{pattern}' found.[/yellow]")
        return
    
    table = Table(title=f"Files in {current_working_dir}", header_style="bold cyan")
    table.add_column("File", style="white")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Modified", style="dim")
    
    for filepath in sorted(files)[:100]:
        info = FileOperation.get_file_info(filepath)
        if info:
            size_str = f"{info['size']:,} bytes" if info['size'] < 1024 * 1024 else f"{info['size'] / (1024 * 1024):.2f} MB"
            modified = info['modified'].strftime("%Y-%m-%d %H:%M")
            table.add_row(
                filepath,
                size_str,
                modified
            )
    
    console.print(table)
    if len(files) > 100:
        console.print(f"[dim]... and {len(files) - 100} more files[/dim]")


@app.command()
def copy(
    src: str = typer.Argument(..., help="Source file path"),
    dst: str = typer.Argument(..., help="Destination file path")
):
    success = FileOperation.copy_file(src, dst)
    if success:
        console.print(f"[green]✓ Copied: {src} → {dst}[/green]")
    else:
        console.print(f"[red]Error: Could not copy {src} to {dst}[/red]")


@app.command()
def move(
    src: str = typer.Argument(..., help="Source file path"),
    dst: str = typer.Argument(..., help="Destination file path")
):
    success = FileOperation.move_file(src, dst)
    if success:
        console.print(f"[green]✓ Moved: {src} → {dst}[/green]")
    else:
        console.print(f"[red]Error: Could not move {src} to {dst}[/red]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Text to search for"),
    pattern: str = typer.Option("*", "--pattern", "-p", help="File pattern to search in (e.g., '*.py')"),
    max_results: int = typer.Option(500, "--max", "-m", help="Max results"),
    context: bool = typer.Option(False, "--context", "-c", help="Show context lines"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save results to file")
):
    """Search for text or regex patterns in files."""
    
    # Check if it looks like a regex
    if any(c in query for c in ['*', '+', '?', '\\', '[', ']', '(', ')', '|', '.', '^', '$', '{', '}']):
        # Try regex search
        return regex_search(query, pattern, max_results, context, output)
    
    # Simple text search
    with console.status("[bold cyan]Searching...", spinner="dots"):
        results = FileOperation.search_files(query, pattern, use_regex=False)
    
    if not results:
        console.print(f"[yellow]No matches found for '{query}' in {pattern}[/yellow]")
        return
    
    total_matches = sum(r["matches"] for r in results)
    console.print(f"[green]✓ Found {total_matches} matches in {len(results)} files[/green]\n")
    
    for result in results[:20]:
        filepath = result["file"]
        console.print(f"[bold cyan]{filepath}[/bold cyan] ({result['matches']} matches)")
        
        for line in result["lines"][:10]:
            highlighted = line['content'].replace(query, f"[bold red]{query}[/bold red]")
            console.print(f"  L{line['line']}: {highlighted[:80]}")
        
        if result["matches"] > 10:
            console.print(f"  [dim]... and {result['matches'] - 10} more matches[/dim]")
        console.print()
    
    if len(results) > 20:
        console.print(f"[dim]... and {len(results) - 20} more files[/dim]")
    
    if output:
        with open(output, 'w') as f:
            for result in results:
                f.write(f"\n{result['file']}\n")
                f.write("-" * 40 + "\n")
                for line in result["lines"]:
                    f.write(f"  L{line['line']}: {line['content']}\n")
        console.print(f"[dim]Results saved to: {output}[/dim]")


@app.command()
def regex_search(
    pattern: str = typer.Argument(..., help="Regex pattern to search for"),
    file_pattern: str = typer.Option("*", "--files", "-f", help="File pattern to search in (e.g., '*.py')"),
    max_results: int = typer.Option(500, "--max", "-m", help="Max results"),
    context: bool = typer.Option(False, "--context", "-c", help="Show context lines"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save results to file")
):
    """Advanced regex search using SMRX engine."""
    if not smrx_wrapper.available:
        console.print("[red]✗ SMRX regex engine not available. Install with: pip install smrx[/red]")
        return
    
    # Validate regex
    is_valid, error = smrx_wrapper.validate(pattern)
    if not is_valid:
        console.print(f"[red]✗ Invalid regex: {error}[/red]")
        return
    
    with console.status("[bold cyan]Regex searching...", spinner="dots"):
        result = FileOperation.search_files(
            pattern, 
            file_pattern, 
            use_regex=True,
            max_results=max_results,
            include_context=context
        )
    
    if not result:
        console.print(f"[yellow]No matches found for: {pattern}[/yellow]")
        return
    
    # Get additional stats
    total_matches = sum(r["matches"] for r in result)
    total_files = len(result)
    
    console.print(f"[green]✓ Found {total_matches} matches in {total_files} files[/green]\n")
    
    # Display results
    if output and output.endswith('.json'):
        output_data = {
            "pattern": pattern,
            "file_pattern": file_pattern,
            "total_matches": total_matches,
            "total_files": total_files,
            "results": result
        }
        with open(output, 'w') as f:
            json.dump(output_data, f, indent=2)
        console.print(f"[dim]Results saved to: {output}[/dim]")
        return
    
    # Display with rich formatting
    for file_data in result[:20]:
        filepath = file_data["file"]
        matches = file_data["matches"]
        
        # Color code based on match density
        color = "green" if matches <= 5 else "yellow" if matches <= 20 else "red"
        
        console.print(f"[bold {color}]{filepath}[/bold {color}] ({matches} matches)")
        
        for line_data in file_data["lines"][:10]:
            line_num = line_data["line"]
            line_text = line_data["content"]
            match_text = line_data["match"]
            
            # Highlight matches with color
            highlighted = line_text.replace(match_text, f"[bold red]{match_text}[/bold red]")
            
            console.print(f"  L{line_num}: {highlighted[:80]}")
            
            # Show context if available
            if context and line_data.get("context_before"):
                for ctx in line_data["context_before"][-2:]:
                    console.print(f"    [dim]│ {ctx[:60]}[/dim]")
            if context and line_data.get("context_after"):
                for ctx in line_data["context_after"][:2]:
                    console.print(f"    [dim]│ {ctx[:60]}[/dim]")
        
        if len(file_data["lines"]) > 10:
            console.print(f"  [dim]... and {len(file_data['lines']) - 10} more matches[/dim]")
        console.print()
    
    if len(result) > 20:
        console.print(f"[dim]... and {len(result) - 20} more files[/dim]")
    
    # Show SMRX stats
    cache_stats = smrx_wrapper.get_cache_stats()
    if cache_stats:
        pattern_cache = cache_stats.get('pattern_cache', {})
        console.print(f"\n[dim]Cache: {pattern_cache.get('size', 0)} patterns cached[/dim]")
    
    # Option to save results in text format
    if output and not output.endswith('.json'):
        with open(output, 'w') as f:
            for file_data in result:
                f.write(f"\n{file_data['file']}\n")
                f.write("-" * 40 + "\n")
                for line_data in file_data["lines"]:
                    f.write(f"  L{line_data['line']}: {line_data['content']}\n")
        console.print(f"[dim]Results saved to: {output}[/dim]")


@app.command()
def info(
    filepath: str = typer.Argument(..., help="File path to inspect")
):
    info = FileOperation.get_file_info(filepath)
    if not info:
        console.print(f"[red]File '{filepath}' not found.[/red]")
        return
    
    console.print(Panel(
        f"[bold]File:[/bold] {info['name']}\n"
        f"[bold]Path:[/bold] {info['path']}\n"
        f"[bold]Size:[/bold] {info['size']:,} bytes\n"
        f"[bold]Created:[/bold] {info['created'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"[bold]Modified:[/bold] {info['modified'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"[bold]Type:[/bold] {'Directory' if info['is_dir'] else 'File'}\n"
        f"[bold]Extension:[/bold] {info['extension'] or 'None'}",
        title="File Information",
        border_style="cyan"
    ))


# ============================================================================
# COMMANDS - SMRX MANAGEMENT
# ============================================================================

@app.command()
def smrx_cache(
    action: str = typer.Argument("stats", help="Action: stats, clear, info")
):
    """Manage SMRX regex engine cache."""
    if not smrx_wrapper.available:
        console.print("[red]SMRX not available[/red]")
        return
    
    if action == "stats":
        cache_stats = smrx_wrapper.get_cache_stats()
        wrapper_stats = smrx_wrapper.get_stats()
        
        console.print(Panel(
            f"[bold]SMRX Cache Statistics[/bold]\n\n"
            f"Pattern Cache Size: {cache_stats.get('pattern_cache', {}).get('size', 0)}\n"
            f"Pattern Cache Capacity: {cache_stats.get('pattern_cache', {}).get('capacity', 0)}\n"
            f"Match Cache Size: {cache_stats.get('match_cache', {}).get('size', 0)}\n"
            f"File Cache Size: {cache_stats.get('file_cache', {}).get('size', 0)}\n"
            f"\n[bold]Usage Statistics[/bold]\n"
            f"Total Searches: {wrapper_stats.get('searches', 0)}\n"
            f"Total Matches: {wrapper_stats.get('matches', 0)}\n"
            f"Errors: {wrapper_stats.get('errors', 0)}",
            title="Cache Manager",
            border_style="cyan"
        ))
    
    elif action == "clear":
        smrx_wrapper.clear_cache()
        console.print("[green]✓ SMRX cache cleared[/green]")
    
    elif action == "info":
        try:
            import smrx
            console.print(Panel(
                f"[bold]SMRX Engine Info[/bold]\n\n"
                f"Version: {getattr(smrx, '__version__', 'Unknown')}\n"
                f"Available Features:\n"
                f"  • Parallel search: ✓\n"
                f"  • Pattern validation: ✓\n"
                f"  • Cache support: ✓\n"
                f"  • Gitignore support: ✓",
                title="Engine Info",
                border_style="cyan"
            ))
        except:
            console.print("[red]Could not get SMRX info[/red]")
    else:
        console.print(f"[yellow]Unknown action: {action}. Use: stats, clear, info[/yellow]")


@app.command()
def smrx_health():
    """Check SMRX engine health and performance."""
    if not smrx_wrapper.available:
        console.print("[red]✗ SMRX not installed[/red]")
        console.print("[dim]Install with: pip install smrx[/dim]")
        return
    
    console.print(Panel("[bold cyan]SMRX Health Check[/bold cyan]", expand=False))
    
    # Test search
    test_pattern = r'\bdef\s+\w+\('
    test_dir = os.getcwd()
    
    with console.status("[dim]Testing SMRX engine...", spinner="dots"):
        try:
            start_time = time.time()
            result = smrx_wrapper.search(test_dir, test_pattern, file_pattern="*.py", max_results=10)
            elapsed = time.time() - start_time
            
            if "error" in result:
                console.print(f"[red]✗ Engine test failed: {result['error']}[/red]")
            else:
                console.print(f"[green]✓ Engine test passed ({elapsed:.3f}s)[/green]")
                console.print(f"  Files searched: {result.get('files_searched', 0)}")
                console.print(f"  Matches found: {result.get('matches_found', 0)}")
                
                # Cache stats
                cache_stats = smrx_wrapper.get_cache_stats()
                if cache_stats:
                    console.print(f"\n[bold]Cache Status:[/bold]")
                    console.print(f"  Pattern Cache: {cache_stats.get('pattern_cache', {}).get('size', 0)}/{cache_stats.get('pattern_cache', {}).get('capacity', 0)}")
                    console.print(f"  Match Cache: {cache_stats.get('match_cache', {}).get('size', 0)}/{cache_stats.get('match_cache', {}).get('capacity', 0)}")
                    
                    utilization = cache_stats.get('pattern_cache', {}).get('utilization', '0%')
                    console.print(f"  Utilization: {utilization}")
                
                # Wrapper stats
                wrapper_stats = smrx_wrapper.get_stats()
                console.print(f"\n[bold]Usage:[/bold]")
                console.print(f"  Total searches: {wrapper_stats.get('searches', 0)}")
                console.print(f"  Total matches: {wrapper_stats.get('matches', 0)}")
                console.print(f"  Errors: {wrapper_stats.get('errors', 0)}")
                
        except Exception as e:
            console.print(f"[red]✗ Health check failed: {e}[/red]")


# ============================================================================
# COMMANDS - AI AGENT (FIXED)
# ============================================================================

# Keywords that should trigger command execution
ACTION_KEYWORDS = [
    "read", "show", "view", "open", "display", "cat", "type",
    "list", "ls", "dir", "files", "folders", "directory",
    "run", "execute", "start", "launch", "do",
    "create", "write", "make", "new", "generate",
    "delete", "remove", "rm", "del",
    "copy", "cp", "move", "mv",
    "edit", "change", "modify", "update",
    "check", "look", "see", "find", "search",
    "install", "setup", "configure",
    "what", "show me", "give me", "check out"
]

def should_execute_command(query: str) -> bool:
    """Check if the query looks like a command request."""
    query_lower = query.lower().strip()
    
    direct_patterns = [
        r'^read\s+', r'^show\s+', r'^view\s+', r'^open\s+',
        r'^list\s+', r'^ls\s*$', r'^dir\s*$',
        r'^run\s+', r'^execute\s+',
        r'^cd\s+', r'^pwd\s*$',
        r'^cat\s+', r'^type\s+',
        r'^find\s+', r'^search\s+',
        r'^create\s+', r'^write\s+', r'^make\s+',
        r'^delete\s+', r'^remove\s+', r'^rm\s+',
        r'^check\s+', r'^look\s+', r'^see\s+',
        r'^what\s+files', r'^show\s+me\s+'
    ]
    
    for pattern in direct_patterns:
        if re.search(pattern, query_lower):
            return True
    
    # Check for keywords in tokenized form
    for keyword in ACTION_KEYWORDS:
        if keyword in query_lower.split():
            return True
    
    return False

def extract_command_from_query(query: str) -> Optional[str]:
    """Extract a shell command from natural language query."""
    query_lower = query.lower().strip()
    
    # Direct commands (user typed a shell command)
    shell_commands = ['dir', 'ls', 'pwd', 'cat', 'type', 'echo', 'git', 'python', 'node', 'npm', 'pip', 'pip3', 'cls', 'clear']
    for cmd in shell_commands:
        if query_lower.startswith(cmd + ' ') or query_lower == cmd:
            return query
    
    # Regex search patterns: "search regex <pattern>", "find regex <pattern>", "regex search <pattern>"
    regex_match = re.search(r'(?:search|find)\s+(?:with\s+)?regex\s+(.+)', query_lower)
    if regex_match:
        regex_pattern = regex_match.group(1).strip()
        return f"__REGEX_SEARCH__ {regex_pattern}"
    
    regex_match = re.search(r'regex\s+(?:search|find)\s+(.+)', query_lower)
    if regex_match:
        regex_pattern = regex_match.group(1).strip()
        return f"__REGEX_SEARCH__ {regex_pattern}"
    
    # "what files" / "list files" / "show files" / "show me the files" - list directory
    if re.search(r'(?:list|show|display|what)\s+(?:the\s+)?(?:files?|contents?|directory|folders?)', query_lower) or re.search(r'show\s+me\s+(?:the\s+)?files?', query_lower):
        return "dir" if os.name == 'nt' else "ls -la"

    # "read X" / "check X" / "show X" / "view X" - read file
    read_patterns = [
        r'(?:read|show|view|open|cat|type|check|look at|see)\s+(?:the\s+)?(?:file\s+)?([^\s]+)',
        r'(?:read|show|view|open|cat|type|check|look at|see)\s+(?:the\s+)?(?:contents?\s+of\s+)?([^\s]+)',
    ]
    
    for pattern in read_patterns:
        read_match = re.search(pattern, query_lower)
        if read_match:
            filepath = read_match.group(1).strip()
            filepath = re.sub(r'[.,!?;:]+$', '', filepath)
            if filepath:
                return f"__READ_FILE__ {filepath}"
    
    # "check out X" / "check X out" - read file
    check_match = re.search(r'check\s+(?:out\s+)?(?:the\s+)?([^\s]+?)(?:\s+out)?$', query_lower)
    if check_match:
        filepath = check_match.group(1).strip()
        filepath = re.sub(r'[.,!?;:]+$', '', filepath)
        if filepath:
            return f"__READ_FILE__ {filepath}"
    
    # "run X" / "execute X" - run command
    run_match = re.search(r'(?:run|execute|start|launch)\s+(?:the\s+)?(?:script\s+)?(?:file\s+)?([^\s]+)', query_lower)
    if run_match:
        file = run_match.group(1).strip()
        file = re.sub(r'[.,!?;:]+$', '', file)
        if file.endswith('.py'):
            return f"python {file}"
        elif file.endswith('.js'):
            return f"node {file}"
        elif file.endswith('.exe') or file.endswith('.bat') or file.endswith('.cmd'):
            return file
        else:
            return file
    
    # "create X" / "make X" / "new X" - create file
    create_match = re.search(r'(?:create|write|make|new)\s+(?:a\s+)?(?:file\s+)?([^\s]+)', query_lower)
    if create_match:
        filepath = create_match.group(1).strip()
        filepath = re.sub(r'[.,!?;:]+$', '', filepath)
        if filepath:
            return f"__WRITE_FILE__ {filepath}"
    
    # "delete X" / "remove X" - delete file
    delete_match = re.search(r'(?:delete|remove|rm|del)\s+(?:the\s+)?(?:file\s+)?([^\s]+)', query_lower)
    if delete_match:
        filepath = delete_match.group(1).strip()
        filepath = re.sub(r'[.,!?;:]+$', '', filepath)
        if filepath:
            return f"del {filepath}" if os.name == 'nt' else f"rm {filepath}"
    
    # "cd X" - change directory
    cd_match = re.search(r'cd\s+(.+)', query_lower)
    if cd_match:
        return f"cd {cd_match.group(1).strip()}"
    
    return None

@app.command()
def chat(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="AI Provider to use"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Specific model name to use")
):
    """Enter the Neural Link (interactive agent chat mode)."""
    global current_working_dir, username, command_history
    
    # Check if we have any working provider
    if not check_network_connectivity() and provider_manager.default_provider != "ollama":
        console.print("[yellow]⚠️ No network connection. Switching to Ollama for offline mode.[/yellow]")
        provider = "ollama"
    
    client, model_name = require_client(provider, model)
    
    if not client:
        console.print("[red]No AI provider available. Please check your configuration.[/red]")
        console.print("[dim]Run 'ollama serve' to start Ollama, or check your API keys.[/dim]")
        return
    
    try:
        username = getpass.getuser().capitalize()
    except Exception:
        username = os.environ.get("USERNAME", os.environ.get("USER", "User")).capitalize()
    
    os.system('cls' if os.name == 'nt' else 'clear')
    try:
        ascii_banner = render_pyfiglet("Naze", spacer=1)
    except Exception:
        try:
            ascii_banner = pyfiglet.figlet_format("Naze", font="standard")
        except Exception:
            ascii_banner = "Naze"
    
    console.print(f"[bold magenta]{ascii_banner}[/bold magenta]")
    console.print(f"[dim]Neural link established using model [cyan]{model_name}[/cyan].[/dim]")
    console.print(f"[dim]Welcome back, {username}. Using [cyan]{provider_manager.default_provider}[/cyan] with multi-key support.[/dim]")
    console.print(f"[dim]Working directory: [cyan]{current_working_dir}[/cyan][/dim]")
    
    if not check_network_connectivity():
        console.print("[yellow]⚠️ Offline mode - limited functionality[/yellow]")
    
    console.print("[dim]Type 'exit' to quit, 'clear' to reset. Type 'help' for available commands![/dim]")
    console.print("[bold green]Just tell me what to do - I'll actually execute it![/bold green]\n")
    
    messages = []
    last_read_file = {"path": None, "content": None, "preview": None}

    def quick_local_reply(query: str) -> Optional[str]:
        """Fast local replies for simple chat so the app stays snappy on low-power hardware."""
        q = query.strip().lower()
        if not q:
            return None

        greetings = {
            "hi": "Hey, I'm Naze. Local, fast, and a little dramatic. What do you need?",
            "hey": "Hey, I'm Naze. Local, fast, and a little dramatic. What do you need?",
            "hello": "Hi. I'm Naze. Give me the shortest path to the task and I'll handle it.",
            "hi there": "Hey, I'm Naze. Local, fast, and a little dramatic. What do you need?",
            "hey there": "Hey, I'm Naze. Local, fast, and a little dramatic. What do you need?",
            "yo": "Yo. I'm Naze. Tell me the job and I'll do the heavy lifting.",
            "sup": "Sup. I'm Naze. What's the mission?",
            "thanks": "No problem. I'm basically a glorified terminal with better attitude.",
            "thank you": "No problem. I'm basically a glorified terminal with better attitude.",
            "ty": "No problem. I'm basically a glorified terminal with better attitude.",
            "ok": "Cool. Keep it moving. I've got this.",
            "okay": "Cool. Keep it moving. I've got this.",
            "fine": "Cool. Keep it moving. I've got this.",
            "who are you": "I'm Naze. Your local AI helper with sass, speed, and enough attitude to make a shell prompt nervous.",
            "what are you": "I'm Naze. Your local AI helper with sass, speed, and enough attitude to make a shell prompt nervous.",
            "what is this project": "This project is basically a terminal-side task manager with a snarky AI brain. It claims to help you organize work, review performance, and keep your tasks from turning into a pile of emotional damage.",
        }

        if q in greetings:
            return greetings[q]

        if q.startswith(("hi", "hey", "hello", "yo", "sup", "hii", "heyy", "heyo", "helloo")):
            return "Hey, I'm Naze. I've got the vibe, the tools, and the coffee. What's the problem?"

        return None

    def handle_db_task_command(query: str) -> Optional[str]:
        """Handle direct database-backed task actions without sending unrelated noise to the model."""
        q = query.strip().lower()
        if not q:
            return None

        if q in ["show db", "show database", "db", "database", "what is in the db", "open db", "view db"]:
            rows = get_tasks_by_status("pending")
            done = get_tasks_by_status("complete")
            lines = [
                f"Database file: {db_path}",
                f"Pending tasks: {len(rows)}",
                f"Completed tasks: {len(done)}",
            ]
            if rows:
                lines.append("Pending:")
                for item in rows[:5]:
                    lines.append(f"  #{item['id']} - {item['task']}")
            else:
                lines.append("Pending: none")
            return "\n".join(lines)

        if q in ["tasks", "show tasks", "list tasks", "my tasks", "what are my tasks"]:
            rows = get_tasks_by_status("pending")
            if not rows:
                return "No pending tasks. The DB is clean, for now."
            lines = [f"Pending tasks ({len(rows)}):"]
            for item in rows[:10]:
                lines.append(f"  #{item['id']} | {item['task']} | impact {item['impact']} | energy {item['energy']}")
            return "\n".join(lines)

        if q in ["status", "task status", "show status", "db status", "my status"]:
            stats = get_task_stats()
            pending = get_tasks_by_status("pending")
            completed = get_tasks_by_status("complete")
            stale = []
            for task in pending:
                if task.get("due_date"):
                    try:
                        due = datetime.fromisoformat(task["due_date"])
                        if due < datetime.now():
                            stale.append(task)
                    except Exception:
                        pass
            lines = [
                f"Database: {db_path}",
                f"Total tasks: {stats['total']}",
                f"Pending: {stats['pending']}",
                f"Completed: {stats['completed']}",
                f"Overdue: {stats['overdue']}",
                f"Avg energy: {stats['avg_energy']:.1f}/5",
                f"Avg impact: {stats['avg_impact']:.1f}%",
            ]
            if stale:
                lines.append(f"Stale tasks: {len(stale)}")
                for item in stale[:3]:
                    lines.append(f"  #{item['id']} | {item['task']}")
            elif pending:
                lines.append("Stale tasks: 0")
            else:
                lines.append("Stale tasks: 0")
            return "\n".join(lines)

        match = re.search(r'(?:show|view|read|open)\s+(?:task|todo)\s*(\d+)', q)
        if match:
            task_id = int(match.group(1))
            task = get_task_by_id(task_id)
            if not task:
                return f"Task #{task_id} does not exist in the DB."
            return (
                f"Task #{task['id']}\n"
                f"Status: {task['status']}\n"
                f"Description: {task['task']}\n"
                f"Impact: {task['impact']}% | Energy: {task['energy']}\n"
                f"Category: {task['category'] or 'General'}\n"
                f"Project: {task['project'] or '—'}\n"
                f"Due: {task['due_date'] or '—'}\n"
                f"Note: {task['note'] or '—'}"
            )

        match = re.search(r'(?:add|create|new)\s+(?:task|todo)\s+(.*)', q)
        if match:
            description = match.group(1).strip()
            if not description:
                return "Need a task description, genius."
            conn = get_db_conn()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tasks (task, energy, impact, category, Naze_note, status) VALUES (?, ?, ?, ?, ?, ?)",
                (description, 3, 50, "General", "Added from chat", "pending")
            )
            task_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return f"Added task #{task_id}: {description}"

        match = re.search(r'(?:finish|complete)\s+(?:task|todo)\s*(\d+)', q)
        if match:
            task_id = int(match.group(1))
            conn = get_db_conn()
            cursor = conn.cursor()
            cursor.execute("UPDATE tasks SET status = 'complete', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
            return f"Marked task #{task_id} as complete."

        match = re.search(r'(?:delete|remove|drop)\s+(?:task|todo)\s*(\d+)', q)
        if match:
            task_id = int(match.group(1))
            deleted = delete_task(task_id, force=True)
            return f"Deleted task #{task_id} from the database." if deleted else f"Task #{task_id} was not found."

        return None
    
    # Get current tasks
    tasks = get_tasks_by_status("pending")
    task_summary = "\n".join([f"- #{t['id']}: {t['task']}" for t in tasks[:5]])
    if len(tasks) > 5:
        task_summary += f"\n... and {len(tasks) - 5} more pending tasks"
    
    # Get current directory contents
    try:
        items = os.listdir(current_working_dir)
        dir_items = []
        for f in items[:20]:
            full_path = os.path.join(current_working_dir, f)
            if os.path.isdir(full_path):
                dir_items.append(f"📁 {f}/")
            else:
                size = os.path.getsize(full_path)
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024*1024:
                    size_str = f"{size/1024:.1f}KB"
                else:
                    size_str = f"{size/(1024*1024):.1f}MB"
                dir_items.append(f"📄 {f} ({size_str})")
        dir_contents = "\n".join(dir_items)
        if len(items) > 20:
            dir_contents += f"\n... and {len(items) - 20} more items"
    except:
        dir_contents = "  (Unable to list directory)"
    
    system_instructions = f"""{NAZE_IDENTITY}

Personality:
- Brief, sharp, slightly sarcastic, confident.
- Sound like a clever terminal sidekick, not a polite enterprise assistant.
- Keep replies short, useful, and a little bit sassy.
- If the user is casual, respond casually.
- If they ask for tasks/files/commands, act on them directly.

CRITICAL RULES:
1. When user asks to READ a file -> read it and explain it in plain English.
2. When user asks to LIST files -> execute or show the directory contents.
3. When user asks to RUN something -> execute it.
4. When user asks to CREATE a file -> create it.
5. NEVER just explain what you would do - ACTUALLY DO IT.
6. Keep the response short and useful; no bland corporate filler.

Current context:
- User: {username}
- Working directory: {current_working_dir}
- Pending tasks: {len(tasks)}

Files in current directory:
{dir_contents}

Pending tasks:
{task_summary if tasks else "No pending tasks."}

Be fast, direct, and a little dramatic."""
    
    messages.append({"role": "system", "content": system_instructions})
    
    def execute_command(command: str) -> str:
        """Execute a shell command and return the real output."""
        global current_working_dir, command_history
        
        # Add to history
        command_history.append(command)
        if len(command_history) > MAX_HISTORY:
            command_history.pop(0)
        
        console.print(f"[dim cyan]▶ Executing:[/dim cyan] [bold]{command}[/bold]")
        console.print(f"[dim]in: {current_working_dir}[/dim]")
        
        try:
            # Handle cd
            if command.strip().startswith("cd "):
                parts = command.split(maxsplit=1)
                target = parts[1].strip() if len(parts) > 1 else "~"
                expanded = os.path.expanduser(target)
                new_path = os.path.normpath(os.path.join(current_working_dir, expanded))
                if os.path.isdir(new_path):
                    current_working_dir = new_path
                    return f"✅ Changed to: {current_working_dir}"
                return f"❌ Directory not found: {target}"
            
            # Run command with timeout
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                capture_output=True,
                cwd=current_working_dir,
                timeout=30
            )
            
            output = []
            
            # Add command info
            output.append(f"📁 {current_working_dir}")
            output.append(f"$ {command}")
            output.append("")
            
            # Add stdout
            if result.stdout:
                output.append("📤 STDOUT:")
                output.append(result.stdout.rstrip())
            
            # Add stderr
            if result.stderr:
                output.append("⚠️ STDERR:")
                output.append(result.stderr.rstrip())
            
            # Add exit status
            if result.returncode == 0:
                output.append(f"\n✅ Exit code: {result.returncode}")
            else:
                output.append(f"\n❌ Exit code: {result.returncode}")
            
            if not result.stdout and not result.stderr:
                output.append("(No output)")
            
            return "\n".join(output)
            
        except subprocess.TimeoutExpired:
            return f"❌ Command timed out after 30 seconds: {command}"
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def read_file_content(filepath: str) -> str:
        """Read and return actual file content with proper encoding."""
        console.print(f"[dim cyan]📖 Reading:[/dim cyan] [bold]{filepath}[/bold]")
        
        try:
            full_path = Path(current_working_dir) / filepath
            if not full_path.exists():
                return f"❌ File not found: {filepath}"
            if full_path.is_dir():
                return f"❌ Is a directory: {filepath}"
            
            content = FileOperation.read_file(filepath)
            if content is None:
                return f"❌ Could not read file: {filepath}"
            
            size = full_path.stat().st_size
            lines = content.count('\n') + 1
            
            output = []
            output.append(f"📄 {filepath}")
            output.append(f"📏 {size:,} bytes, {lines} lines")
            output.append(f"📁 {full_path.resolve()}")
            output.append("")
            output.append("─" * 40)
            output.append(content)
            output.append("─" * 40)
            
            return "\n".join(output)
                
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def write_file_content(filepath: str, content: str) -> str:
        """Write content to a file."""
        console.print(f"[dim cyan]✏️ Writing:[/dim cyan] [bold]{filepath}[/bold]")
        
        try:
            full_path = Path(current_working_dir) / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # If content is empty, prompt user
            if not content:
                content = input("Enter content (Ctrl+Z on new line to finish, Ctrl+C to cancel):\n")
            
            full_path.write_text(content, encoding='utf-8')
            size = len(content)
            return f"✅ Wrote {full_path.resolve()}\n📏 {size:,} bytes written"
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": "execute_command",
                "description": "Execute a real shell command. Use for: dir, ls, git, python, npm, cd, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The shell command to execute"}
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read and display the actual contents of a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filepath": {"type": "string", "description": "Path to the file to read"}
                    },
                    "required": ["filepath"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file (creates or overwrites).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filepath": {"type": "string", "description": "Path to the file to write"},
                        "content": {"type": "string", "description": "Content to write (optional, will prompt if empty)"}
                    },
                    "required": ["filepath"]
                }
            }
        }
    ]
    
    while True:
        try:
            user_query = console.input("[bold cyan]> [/bold cyan]").strip()
        except EOFError:
            break
        
        if not user_query:
            continue
        
        # Check for special commands
        if user_query.lower() in ["exit", "quit"]:
            console.print(f"[yellow]Shutting down neural link... Goodbye, {username}.[/yellow]")
            break
        
        if user_query.lower() == "clear":
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print(f"[bold magenta]{ascii_banner}[/bold magenta]")
            messages = [messages[0]]
            continue
        
        if user_query.lower() == "help":
            console.print("""
[bold]Just tell me what to do:[/bold]
  "read readme.md"        - Shows the file content
  "list files"            - Shows directory contents  
  "run test.py"           - Executes the script
  "show my tasks"         - Lists your tasks
  "create file.txt"       - Creates a file (prompts for content)
  "cd folder"             - Changes directory
  "history"               - Shows command history
  "regex search pattern"  - Advanced regex search

[bold]Chat Commands:[/bold]
  help                    - Show this help
  clear                   - Clear screen
  exit / quit            - Exit chat
""")
            continue
        
        if user_query.lower() == "history":
            if command_history:
                console.print("[bold]Command History:[/bold]")
                for i, cmd in enumerate(command_history[-20:], 1):
                    console.print(f"  {i}. {cmd}")
            else:
                console.print("[dim]No commands in history.[/dim]")
            continue
        
        # Handle commands directly first
        if user_query.lower().startswith("cd "):
            target = user_query[3:].strip()
            try:
                new_path = os.path.normpath(os.path.join(current_working_dir, target))
                if os.path.isdir(new_path):
                    current_working_dir = new_path
                    console.print(f"[green]✅ {current_working_dir}[/green]")
                else:
                    console.print(f"[red]❌ Not found: {target}[/red]")
            except Exception as e:
                console.print(f"[red]❌ {e}[/red]")
            continue
        
        if user_query.lower().strip() == "pwd":
            console.print(f"[cyan]{current_working_dir}[/cyan]")
            continue
        
        # Try to extract command for direct execution
        extracted_cmd = extract_command_from_query(user_query)
        if extracted_cmd:
            if extracted_cmd.startswith("__READ_FILE__"):
                filepath = extracted_cmd.split(" ", 1)[1]
                try:
                    full_path = Path(current_working_dir) / filepath
                    if not full_path.exists():
                        console.print(f"[red]❌ File not found: {filepath}[/red]")
                        continue
                    if full_path.is_dir():
                        console.print(f"[red]❌ Is a directory: {filepath}[/red]")
                        continue

                    content = FileOperation.read_file(filepath)
                    if content is None:
                        console.print(f"[red]❌ Could not read file: {filepath}[/red]")
                        continue

                    size = full_path.stat().st_size
                    lines = content.splitlines()
                    preview = "\n".join(lines[:15])
                    if len(lines) > 15:
                        preview += f"\n... and {len(lines) - 15} more lines"
                    if len(content) > 6000:
                        preview = content[:5000].rstrip() + "\n... (truncated for preview)"

                    last_read_file = {
                        "path": filepath,
                        "content": content,
                        "preview": preview,
                    }

                    console.print(Panel(
                        preview,
                        title=f"[bold cyan]📄 {filepath} (preview)[/bold cyan]",
                        border_style="cyan"
                    ))
                    console.print(f"[dim]📏 {size:,} bytes · {len(lines)} lines · Type 'summarize' for a quick AI summary[/dim]")
                    console.print()
                    continue
                except Exception as e:
                    console.print(f"[red]Error reading file: {e}[/red]")
                    continue
            elif extracted_cmd.startswith("__WRITE_FILE__"):
                filepath = extracted_cmd.split(" ", 1)[1]
                result = write_file_content(filepath, "")
                console.print(Panel(result, title="[bold cyan]✏️ File Write[/bold cyan]", border_style="cyan"))
                console.print()
                continue
            elif extracted_cmd.startswith("__REGEX_SEARCH__"):
                regex_pattern = extracted_cmd.split(" ", 1)[1]
                console.print(f"[dim]Searching with regex: {regex_pattern}[/dim]")
                
                # Use the new regex search command
                result = FileOperation.regex_search(regex_pattern, "*")
                
                if "error" in result:
                    console.print(f"[red]❌ {result['error']}[/red]")
                else:
                    console.print(f"[cyan]✓ Found {result['matches_found']} matches in {result['files_searched']} files ({result['execution_time']:.3f}s)[/cyan]")
                    
                    if result.get('matches'):
                        match_lines = []
                        for match in result['matches'][:50]:
                            match_lines.append(f"[dim]{match['file']}:{match['line']}:{match['col']}[/dim] {match['text'][:80]}")
                        
                        console.print(Panel(
                            "\n".join(match_lines),
                            title=f"[bold cyan]🔍 Regex Matches[/bold cyan]",
                            border_style="cyan"
                        ))
                    else:
                        console.print("[yellow]No matches found.[/yellow]")
                console.print()
                continue
            else:
                result = execute_command(extracted_cmd)
                console.print(Panel(result, title="[bold cyan]⚡ Command Result[/bold cyan]", border_style="cyan"))
                console.print()
                continue
        
        # Check for summarize request before sending any large file payload to the model
        if user_query.lower() in ["summarize", "summary", "summarise"]:
            if not last_read_file["path"] or not last_read_file["content"]:
                console.print("[yellow]No file has been read in this session yet.[/yellow]")
                continue

            summary_source = last_read_file["content"][:6000]
            prompt = (
                "Explain what this file is actually saying, and also what it is claiming. "
                "Give a short plain-English summary, then call out the product claims, promises, and hype versus what the file actually demonstrates. "
                "Keep it useful, honest, and a little bit sassy without being arrogant.\n\n"
                f"File path: {last_read_file['path']}\n\n{summary_source}"
            )
            try:
                with console.status("[dim]Generating summary...", spinner="dots"):
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=300
                    )
                summary = response.choices[0].message.content
                console.print("\n")
                console.print(Panel(Markdown(summary), title="[bold cyan]📝 Summary[/bold cyan]", border_style="cyan"))
                console.print("\n")
            except Exception as e:
                console.print(f"[red]Error generating summary: {e}[/red]")
            continue

        db_reply = handle_db_task_command(user_query)
        if db_reply:
            console.print(Panel(db_reply, title="[bold cyan]DB Task View[/bold cyan]", border_style="cyan"))
            console.print()
            continue

        local_reply = quick_local_reply(user_query)
        if local_reply:
            console.print(f"[bold green]{local_reply}[/bold green]")
            continue

        # Update context for AI
        try:
            items = os.listdir(current_working_dir)
            dir_items = []
            for f in items[:20]:
                full_path = os.path.join(current_working_dir, f)
                if os.path.isdir(full_path):
                    dir_items.append(f"📁 {f}/")
                else:
                    size = os.path.getsize(full_path)
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024*1024:
                        size_str = f"{size/1024:.1f}KB"
                    else:
                        size_str = f"{size/(1024*1024):.1f}MB"
                    dir_items.append(f"📄 {f} ({size_str})")
            dir_contents = "\n".join(dir_items)
            if len(items) > 20:
                dir_contents += f"\n... and {len(items) - 20} more items"
        except:
            dir_contents = "  (Unable to list)"
        
        tasks = get_tasks_by_status("pending")
        task_summary = "\n".join([f"- #{t['id']}: {t['task']}" for t in tasks[:5]])
        if len(tasks) > 5:
            task_summary += f"\n... and {len(tasks) - 5} more"
        
        messages[0]["content"] = f"""{NAZE_IDENTITY}

CRITICAL RULES:
1. When user asks to READ a file -> IMMEDIATELY call read_file()
2. When user asks to LIST files -> IMMEDIATELY call execute_command('dir' or 'ls')
3. When user asks to RUN something -> IMMEDIATELY call execute_command()
4. When user asks to CREATE a file -> IMMEDIATELY call write_file()
5. NEVER just explain what you would do - ACTUALLY DO IT
6. Show the real output, then ask if they need more

Current context:
- User: {username}
- Working directory: {current_working_dir}
- Pending tasks: {len(tasks)}

Files in current directory:
{dir_contents}

Pending tasks:
{task_summary if tasks else "No pending tasks."}

Remember: ACTUALLY EXECUTE commands, don't just talk about them!"""
        
        messages.append({"role": "user", "content": user_query})
        recent_messages = messages[-6:]
        
        try:
            # Try with tools only when the query is actually task-like; keep casual chat snappy.
            try:
                with console.status("[dim]Processing...", spinner="dots"):
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=recent_messages,
                        tools=tools_schema,
                        tool_choice="auto",
                        max_tokens=120,
                        temperature=0.7,
                    )
            except Exception as e:
                with console.status("[dim]Processing...", spinner="dots"):
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=recent_messages,
                        max_tokens=120,
                        temperature=0.7,
                    )
            
            response_message = response.choices[0].message
            messages.append(response_message)
            
            # Handle tool calls
            if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except Exception:
                        function_args = {}
                    
                    tool_output = ""
                    if function_name == "execute_command":
                        cmd = function_args.get("command", "")
                        tool_output = execute_command(cmd)
                    elif function_name == "read_file":
                        filepath = function_args.get("filepath", "")
                        full_path = Path(current_working_dir) / filepath
                        if not full_path.exists():
                            tool_output = f"❌ File not found: {filepath}"
                        elif full_path.is_dir():
                            tool_output = f"❌ Is a directory: {filepath}"
                        else:
                            file_text = FileOperation.read_file(filepath)
                            if file_text is None:
                                tool_output = f"❌ Could not read file: {filepath}"
                            else:
                                preview = file_text[:5000].rstrip()
                                if len(file_text) > 5000:
                                    preview += "\n... (truncated for preview)"
                                last_read_file["path"] = filepath
                                last_read_file["content"] = file_text
                                last_read_file["preview"] = preview
                                tool_output = f"📄 {filepath}\n\n{preview}"
                                console.print(Panel(preview, title=f"[bold cyan]📄 {filepath} (preview)[/bold cyan]", border_style="cyan"))
                                console.print("[dim]Type 'summarize' for a quick AI summary.[/dim]\n")
                                continue
                    elif function_name == "write_file":
                        filepath = function_args.get("filepath", "")
                        content = function_args.get("content", "")
                        tool_output = write_file_content(filepath, content)
                    
                    if tool_output and not function_name == "read_file":
                        console.print(Panel(
                            tool_output,
                            title=f"[bold cyan]⚡ Tool: {function_name}[/bold cyan]",
                            border_style="cyan"
                        ))
                        console.print()
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_output
                    })
                
                # Get final response after tool calls
                with console.status("[dim]Responding...", spinner="dots"):
                    final_response = client.chat.completions.create(
                        model=model_name,
                        messages=messages
                    )
                
                final_answer = final_response.choices[0].message.content
                if final_answer:
                    console.print(Markdown(final_answer))
                    console.print()
            
            else:
                # No tools called - check if we should force execution
                if should_execute_command(user_query):
                    console.print("[yellow]⚠️ I should have executed that. Let me try:[/yellow]")
                    cmd = extract_command_from_query(user_query)
                    if cmd:
                        if cmd.startswith("__READ_FILE__"):
                            filepath = cmd.split(" ", 1)[1]
                            result = read_file_content(filepath)
                        elif cmd.startswith("__WRITE_FILE__"):
                            filepath = cmd.split(" ", 1)[1]
                            result = write_file_content(filepath, "")
                        else:
                            result = execute_command(cmd)
                        console.print(Panel(result, title="[bold cyan]⚡ Result[/bold cyan]", border_style="cyan"))
                        console.print()
                    continue
                
                final_answer = response_message.content
                if final_answer:
                    console.print(Markdown(final_answer))
                    console.print()
        
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            # Try direct execution as fallback
            if should_execute_command(user_query):
                cmd = extract_command_from_query(user_query)
                if cmd:
                    console.print("[dim]Trying direct execution...[/dim]")
                    if cmd.startswith("__READ_FILE__"):
                        filepath = cmd.split(" ", 1)[1]
                        result = read_file_content(filepath)
                    elif cmd.startswith("__WRITE_FILE__"):
                        filepath = cmd.split(" ", 1)[1]
                        result = write_file_content(filepath, "")
                    else:
                        result = execute_command(cmd)
                    console.print(Panel(result, title="[bold cyan]⚡ Result[/bold cyan]", border_style="cyan"))
                    console.print()


# ============================================================================
# COMMANDS - SYSTEM
# ============================================================================

@app.command()
def exec(command: List[str] = typer.Argument(..., help="The shell command and arguments to execute.")):
    cmd_str = " ".join(command)
    console.print(f"[dim magenta]Naze executing:[/dim magenta] [bold white]{cmd_str}[/bold white]\n")
    
    try:
        result = subprocess.run(cmd_str, shell=True, text=True, capture_output=True)
        if result.stdout:
            console.print(Panel(result.stdout.strip(), title="[bold cyan]Output[/bold cyan]", border_style="cyan"))
        if result.stderr:
            console.print(Panel(result.stderr.strip(), title="[bold red]Errors / Warnings[/bold red]", border_style="red"))
        if result.returncode != 0:
            console.print(f"\n[yellow]Command exited with code {result.returncode}[/yellow]")
            raise typer.Exit(code=result.returncode)
    except Exception as e:
        console.print(f"[bold red]Execution Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def cd(
    path: str = typer.Argument("~", help="Directory path to change to")
):
    global current_working_dir
    try:
        expanded_path = os.path.expanduser(path)
        new_path = os.path.normpath(os.path.join(current_working_dir, expanded_path))
        if os.path.isdir(new_path):
            current_working_dir = new_path
            console.print(f"[green]Changed directory to: {current_working_dir}[/green]")
        else:
            console.print(f"[red]Directory not found: {path}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def pwd():
    console.print(f"[cyan]{current_working_dir}[/cyan]")


@app.command()
def review(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="AI Provider to use"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Specific model name to use")
):
    if not check_network_connectivity():
        console.print("[yellow]No network connection. Skipping AI review.[/yellow]")
        stats = get_task_stats()
        console.print(Panel(
            f"[bold]Task Summary[/bold]\n\n"
            f"Total: {stats['total']}\n"
            f"Completed: {stats['completed']}\n"
            f"Pending: {stats['pending']}\n"
            f"Completion Rate: {stats['completion_rate']:.1f}%",
            title="Offline Review",
            border_style="yellow"
        ))
        return
    
    client, model_name = require_client(provider, model)
    if not client:
        console.print("[red]No AI provider available.[/red]")
        return
    
    stats = get_task_stats()
    
    conn = get_db_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT category, COUNT(*), AVG(impact) 
        FROM tasks WHERE status = 'complete' 
        GROUP BY category 
        ORDER BY COUNT(*) DESC 
        LIMIT 5
    """)
    completed_categories = cursor.fetchall()
    
    cursor.execute("""
        SELECT DATE(created_at), COUNT(*) 
        FROM tasks 
        GROUP BY DATE(created_at) 
        ORDER BY DATE(created_at) DESC 
        LIMIT 7
    """)
    daily_tasks = cursor.fetchall()
    
    cursor.execute("""
        SELECT AVG(energy), AVG(impact) 
        FROM tasks WHERE status = 'complete'
    """)
    completed_avg = cursor.fetchone()
    
    conn.close()
    
    context = f"""
User Statistics:
- Total Tasks: {stats['total']}
- Completed: {stats['completed']}
- Pending: {stats['pending']}
- Completion Rate: {stats['completion_rate']:.1f}%
- Overdue: {stats['overdue']}
- Average Energy (completed): {completed_avg[0] if completed_avg and completed_avg[0] else 0:.1f}/5
- Average Impact (completed): {completed_avg[1] if completed_avg and completed_avg[1] else 0:.1f}%

Top Completed Categories:
{chr(10).join([f"- {cat}: {count} tasks (avg impact: {avg_impact:.1f}%)" for cat, count, avg_impact in completed_categories])}

Recent Daily Task Creation:
{chr(10).join([f"- {date}: {count} tasks" for date, count in daily_tasks[:7]])}
"""
    
    with console.status("[bold magenta]Naze is judging your productivity...", spinner="dots"):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": """You are Naze, a witty and slightly sarcastic task manager. 
Provide a concise performance review based on the user's stats. Be honest, a bit cheeky, 
and provide one actionable piece of advice. Use Markdown for formatting.

Keep the tone: helpful, slightly sarcastic, but encouraging. Focus on patterns and areas for improvement."""},
                    {"role": "user", "content": context}
                ],
                temperature=0.8
            )
            review_text = response.choices[0].message.content
            console.print("\n")
            console.print(Panel(Markdown(review_text), title=f"[bold cyan]Naze's Performance Review ({model_name})[/bold cyan]", border_style="magenta"))
            console.print("\n")
        except Exception as e:
            console.print(f"[red]Naze is speechless (error): {e}[/red]")


@app.command()
def health():
    console.print(Panel("[bold cyan]Naze System Diagnostic[/bold cyan]", expand=False))
    
    health_table = Table(show_header=False, box=None, padding=(0, 2))
    
    health_table.add_row("Default Provider", f"[bold cyan]{provider_manager.default_provider.upper()}[/bold cyan]")
    health_table.add_row("Providers", f"[cyan]{', '.join(provider_manager.get_all_providers())}[/cyan]")
    health_table.add_row("Working Directory", f"[cyan]{current_working_dir}[/cyan]")
    
    network_ok = check_network_connectivity()
    health_table.add_row("Network", "[green]✓ Online[/green]" if network_ok else "[red]✗ Offline[/red]")
    
    if "ollama" in provider_manager.get_all_providers():
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                health_table.add_row("Ollama", "[green]✓ Running[/green]")
                models = response.json().get("models", [])
                if models:
                    model_names = [m.get("name", "unknown") for m in models]
                    health_table.add_row("Ollama Models", f"[cyan]{', '.join(model_names)}[/cyan]")
            else:
                health_table.add_row("Ollama", "[yellow]⚠ Not responding[/yellow]")
        except:
            health_table.add_row("Ollama", "[red]✗ Not running[/red]")
    
    all_models = provider_manager.get_all_free_models()
    total_models = sum(len(models) for models in all_models.values())
    health_table.add_row("Free Models Available", f"[cyan]{total_models}[/cyan]")
    
    stats = get_task_stats()
    health_table.add_row("Tasks", f"[cyan]{stats['total']} total, {stats['pending']} pending, {stats['completed']} completed[/cyan]")
    
    try:
        conn = get_db_conn()
        conn.execute("SELECT 1")
        health_table.add_row("Database", "[green]✓ Healthy[/green]")
        conn.close()
    except sqlite3.Error:
        health_table.add_row("Database", "[red]✗ File Corrupted or Inaccessible[/red]")
    
    os_name = "Windows" if os.name == 'nt' else "Linux/macOS"
    health_table.add_row("Operating System", f"[blue]{os_name}[/blue]")
    
    # Check SMRX availability
    if smrx_wrapper.available:
        health_table.add_row("SMRX Engine", "[green]✓ Available[/green]")
        cache_stats = smrx_wrapper.get_cache_stats()
        if cache_stats:
            pattern_cache = cache_stats.get('pattern_cache', {})
            health_table.add_row("SMRX Cache", f"[cyan]{pattern_cache.get('size', 0)} patterns cached[/cyan]")
    else:
        health_table.add_row("SMRX Engine", "[yellow]⚠ Not installed[/yellow]")
    
    try:
        import shutil
        disk_usage = shutil.disk_usage(current_working_dir)
        free_gb = disk_usage.free / (1024**3)
        health_table.add_row("Free Disk Space", f"[cyan]{free_gb:.2f} GB[/cyan]")
    except:
        pass
    
    console.print(health_table)
    
    console.print("\n[bold]Tips:[/bold]")
    if not network_ok:
        console.print("  • [yellow]No network detected - use 'ollama' for offline mode[/yellow]")
        console.print("  • [dim]Run 'ollama serve' to start Ollama[/dim]")
    if "ollama" not in provider_manager.get_all_providers():
        console.print("  • [dim]Add Ollama for offline use: 'ollama serve' then restart Naze[/dim]")
    if stats['overdue'] > 0:
        console.print(f"  • [red]You have {stats['overdue']} overdue tasks! Run 'Naze today' to see them.[/red]")
    if not smrx_wrapper.available:
        console.print("  • [dim]Install SMRX for advanced regex search: pip install smrx[/dim]")


# ============================================================================
# PROVIDER MANAGEMENT COMMANDS
# ============================================================================

@app.command()
def providers():
    console.print(Panel("[bold cyan]Naze's AI Providers Configuration[/bold cyan]", expand=False))
    
    table = Table(header_style="bold magenta")
    table.add_column("Provider", style="yellow")
    table.add_column("Keys", style="green")
    table.add_column("Status", style="bold")
    table.add_column("Default Model", style="white")
    table.add_column("Available", style="dim")
    
    for name, config in provider_manager.providers.items():
        primary_count = len(config.primary_keys)
        fallback_count = len(config.fallback_keys)
        unused_count = len(config.unused_keys)
        total_keys = primary_count + fallback_count
        
        available = provider_manager.check_provider_available(name)
        avail_text = "[green]✓[/green]" if available else "[red]✗[/red]"
        
        total_success = sum(stats["success"] for stats in config.key_stats.values())
        total_failures = sum(stats["failures"] for stats in config.key_stats.values())
        total_calls = total_success + total_failures
        
        if total_calls == 0:
            health_color = "yellow"
            health_text = "untested"
        elif total_failures / total_calls < 0.1:
            health_color = "green"
            health_text = "healthy"
        elif total_failures / total_calls < 0.3:
            health_color = "yellow"
            health_text = "degraded"
        else:
            health_color = "red"
            health_text = "unhealthy"
        
        keys_display = f"P:{primary_count} F:{fallback_count} U:{unused_count}"
        status_display = f"[{health_color}]{health_text} ({total_keys} keys)[/{health_color}]"
        
        table.add_row(
            name.capitalize(),
            keys_display,
            status_display,
            config.default_model,
            avail_text
        )
    
    console.print(table)
    console.print(f"\n[dim]Default Provider: [cyan]{provider_manager.default_provider}[/cyan][/dim]")
    console.print("[dim]✓ = available, ✗ = not available[/dim]")


@app.command(name="list-models")
def list_models(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Filter by provider")
):
    console.print(Panel("[bold cyan]🚀 FREE MODELS LIBRARY[/bold cyan]", expand=False))
    
    table = Table(header_style="bold magenta")
    table.add_column("Provider", style="yellow")
    table.add_column("Model", style="green")
    table.add_column("Default", style="dim")
    table.add_column("Type", style="cyan")
    
    all_models = provider_manager.get_all_free_models()
    
    for prov, models in all_models.items():
        if provider and prov != provider:
            continue
        
        for model in models:
            is_default = "✓" if model == provider_manager.providers[prov].default_model else ""
            
            model_type = "Chat"
            if "vision" in model.lower():
                model_type = "Vision"
            elif "embed" in model.lower():
                model_type = "Embedding"
            elif "instruct" in model.lower():
                model_type = "Instruct"
            elif "r1" in model.lower() or "reasoning" in model.lower():
                model_type = "Reasoning"
            elif "free" in model:
                model_type = "Free"
            
            if model in ["openrouter/free", "openrouter/auto"]:
                model_type = "Auto-Route"
            
            table.add_row(
                prov.upper(),
                model,
                is_default,
                model_type
            )
    
    console.print(table)
    total_models = sum(len(models) for models in all_models.values())
    console.print(f"\n[dim]Total free models available: {total_models}[/dim]")
    console.print("\n[dim]Switch models with: [cyan]Naze switch-model <model-name>[/cyan][/dim]")


@app.command()
def switch_model(
    model: str = typer.Argument(..., help="Model name to switch to"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to use")
):
    all_models = provider_manager.get_all_free_models()
    
    if not provider:
        for prov, models in all_models.items():
            if model in models:
                provider = prov
                break
    
    if not provider:
        console.print(f"[red]Model '{model}' not found in free models list.[/red]")
        console.print("\n[bold]Available free models:[/bold]")
        for prov, models in all_models.items():
            console.print(f"\n[cyan]{prov.upper()}:[/cyan]")
            for m in models[:5]:
                console.print(f"  • {m}")
            if len(models) > 5:
                console.print(f"  • ... and {len(models) - 5} more")
        return
    
    env_path = Path(__file__).parent / ".env"
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
        
        with open(env_path, "w") as f:
            for line in lines:
                if line.startswith(f"{provider.upper()}_DEFAULT_MODEL="):
                    f.write(f"{provider.upper()}_DEFAULT_MODEL={model}\n")
                else:
                    f.write(line)
        
        console.print(f"[green]✓ Switched to model: {model} on {provider}[/green]")
        console.print("[yellow]Please restart Naze for changes to take effect.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error updating .env: {e}[/red]")


@app.command()
def promote_key(
    provider: str = typer.Argument(..., help="Provider name"),
    key: str = typer.Argument(..., help="Key to promote (full or partial)"),
    to: str = typer.Argument("primary", help="Promote to: primary or fallback")
):
    config = provider_manager.get_provider(provider)
    if not config:
        console.print(f"[red]Provider '{provider}' not found.[/red]")
        return
    
    matching_key = None
    for k in config.fallback_keys + config.unused_keys:
        if key in k:
            matching_key = k
            break
    
    if not matching_key:
        console.print(f"[red]Key not found in fallback or unused keys.[/red]")
        return
    
    if to == "primary":
        if config.promote_to_primary(matching_key):
            console.print(f"[green]✓ Key promoted to primary: {matching_key[:8]}...[/green]")
        else:
            console.print(f"[red]Failed to promote key.[/red]")
    elif to == "fallback":
        if config.promote_to_fallback(matching_key):
            console.print(f"[green]✓ Key promoted to fallback: {matching_key[:8]}...[/green]")
        else:
            console.print(f"[red]Failed to promote key.[/red]")
    else:
        console.print(f"[red]Invalid promotion type: {to}. Use 'primary' or 'fallback'.[/red]")


@app.command()
def add_provider(
    name: str = typer.Argument(..., help="Provider name"),
    primary_keys: Optional[str] = typer.Option(None, "--primary", "-p", help="Comma-separated primary keys"),
    fallback_keys: Optional[str] = typer.Option(None, "--fallback", "-f", help="Comma-separated fallback keys"),
    unused_keys: Optional[str] = typer.Option(None, "--unused", "-u", help="Comma-separated unused keys"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Custom base URL"),
    default_model: Optional[str] = typer.Option(None, "--default-model", help="Default model"),
    proxy: Optional[str] = typer.Option(None, "--proxy", help="Proxy URL"),
    set_default: bool = typer.Option(False, "--set-default", help="Set as default provider")
):
    primary_list = [k.strip() for k in primary_keys.split(",") if k.strip()] if primary_keys else []
    fallback_list = [k.strip() for k in fallback_keys.split(",") if k.strip()] if fallback_keys else []
    unused_list = [k.strip() for k in unused_keys.split(",") if k.strip()] if unused_keys else []
    
    if not any([primary_list, fallback_list, unused_list]):
        console.print("[red]Error: At least one API key is required.[/red]")
        return
    
    if proxy:
        try:
            parsed = urlparse(proxy)
            if not parsed.scheme or not parsed.netloc:
                console.print("[red]Invalid proxy URL format. Use: http://proxy:8080[/red]")
                return
        except Exception:
            console.print("[red]Invalid proxy URL.[/red]")
            return
    
    provider_config = ProviderConfig(
        name=name.lower(),
        primary_keys=primary_list,
        fallback_keys=fallback_list,
        unused_keys=unused_list,
        base_url=base_url,
        default_model=default_model or "custom-model",
        proxy=proxy
    )
    
    provider_manager.providers[name.lower()] = provider_config
    
    if set_default:
        provider_manager.default_provider = name.lower()
    
    console.print(f"[green]✓ Provider '{name}' added with {len(primary_list + fallback_list)} active keys.[/green]")
    
    env_path = Path(__file__).parent / ".env"
    try:
        with open(env_path, "a") as f:
            f.write(f"\n# Added provider: {name}\n")
            if primary_list:
                f.write(f"{name.upper()}_PRIMARY_KEYS={','.join(primary_list)}\n")
            if fallback_list:
                f.write(f"{name.upper()}_FALLBACK_KEYS={','.join(fallback_list)}\n")
            if unused_list:
                f.write(f"{name.upper()}_UNUSED_KEYS={','.join(unused_list)}\n")
            if base_url:
                f.write(f"{name.upper()}_BASE_URL={base_url}\n")
            if default_model:
                f.write(f"{name.upper()}_DEFAULT_MODEL={default_model}\n")
            if proxy:
                f.write(f"{name.upper()}_PROXY={proxy}\n")
            if set_default:
                f.write(f"DEFAULT_PROVIDER={name.lower()}\n")
        console.print("[dim]Configuration saved to .env[/dim]")
    except Exception as e:
        console.print(f"[yellow]Could not save to .env: {e}[/yellow]")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    app()