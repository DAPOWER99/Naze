# Naze 🤖
> **The AI Task Manager that's judging your life choices.**

Naze is a witty, high-performance, and slightly cynical AI-powered task manager for your terminal. While most task managers just sit there quietly, Naze leverages multiple AI providers (including Llama 3.3 via Groq, OpenRouter, Mistral, Anthropic, DeepSeek, Together, and more) to provide energy ratings, impact scores, and the kind of feedback you'd expect from a disappointed mentor.

## 🔬 Origin Story: From NaSeZn to Naze

The name **Naze** comes from the crystal structure **NaSeZn** — a real mineral phase discovered in materials science. Over time, the acronym was shortened to **Naze**, which we pronounce as **Nayze**. So yes, your trusty task manager started as a crystal lattice and got a little shorter along the way.

## ✨ Core Features

- **🧠 Neural Link (Chat Mode):** Step into an interactive session where Naze manages your tasks and provides life advice (mostly sarcastic). He has full access to your stats, so expect judgment.
- **📊 Performance Reviews:** Use the `review` command to get a brutal, AI-generated assessment of your productivity. Naze looks at your completion rates and tells you how you're *really* doing.
- **🛡️ Graceful Failure:** Naze doesn't crash when his brain is offline. He handles missing API keys, database issues, and connection timeouts with poise (and a bit of snark).
- **⏳ Temporal Awareness:** Naze tracks how long your tasks have been rotting. Tasks older than 3 days are highlighted as "stale" because, let's face it, you're procrastinating.
- **⚡ AI-Driven Analysis:** Every task you add is evaluated for its **Energy Requirement** (1-5 ⚡) and **Impact Score** (1-100%). Naze sorts your list by impact so you stop doing the easy stuff first.
- **🏆 Collective Victories:** Finish multiple tasks at once and get a single, punchy, AI-generated backhanded compliment.
- **🛠️ Self-Healing Core:** Built-in migrations and health checks to ensure your database and AI brain are always in sync.
- **🔌 Multi-Provider Support:** Connect to multiple AI providers (Groq, OpenRouter, Mistral, Anthropic, DeepSeek, Together, etc.) with seamless switching.
- **🔑 Multi-Key Architecture:** Primary, fallback, and unused key support with automatic key rotation and health tracking.

## 🛠️ Multi-Provider & Multi-Key System

Naze uses a sophisticated multi-provider architecture where you can configure multiple AI providers with primary/fallback/unused key support:

- **Providers:** Groq, OpenRouter, Mistral, Anthropic, DeepSeek, Together, and custom providers
- **Key Management:** Primary keys (preferred), fallback keys (backup), unused keys (reserved)
- **Automatic Rotation:** Failed keys are automatically skipped, and fallback keys are promoted when needed
- **Proxy Support:** Configure proxy settings for each provider
- **Custom Endpoints:** Support for custom API endpoints

## 📂 Storage

Your tasks are stored locally in a SQLite database at:
`~/.local/share/Naze/tasks.db`

> **Note:** This database starts completely empty. If you haven't added any tasks yet, you'll see the "Empty Task Database" warning when you run `python main.py list`.

## 🧪 Development & Debugging

- **Health Check:** `python main.py health` - Check system status and key health
- **Provider Management:** `python main.py providers` - List all configured providers
- **Model Management:** `python main.py list_models` - View available free models
- **Key Promotion:** `python main.py promote_key <provider> <key> --to=primary|fallback` - Manage key priority
- **Database Inspection:** Direct SQLite access through built-in commands

## 🚀 Installation

1. **Clone the brain:**
   ```bash
   git clone https://github.com/DAPOWER99/Naze.git
   cd Naze
   ```

2. **Prepare the environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure AI Providers:**
   Create a `.env` file with your provider configurations:
   ```bash
   # Example .env configuration
   DEFAULT_PROVIDER=groq
   GROQ_DEFAULT_MODEL=llama-3.3-70b-versatile
   GROQ_PRIMARY_KEYS='your_primary_key,another_key'
   GROQ_FALLBACK_KEYS='your_fallback_key'
   ```

4. **Feed the AI:**
   Export your API keys as needed for your configured providers.

### 💡 Pro-Tip: Add an Alias
To summon Naze from anywhere, add this to your `.bashrc` or `.zshrc`:
```bash
alias Naze='/path/to/Naze/venv/bin/python /path/to/Naze/main.py'
```

## 📜 Available Commands

### Task Management
- `python main.py add "<description>"` - Add a new task with AI classification
- `python main.py list` - View pending tasks sorted by impact
- `python main.py finish <ids>` - Mark tasks as completed
- `python main.py delete <ids>` - Remove tasks permanently
- `python main.py clear` - Wipe all tasks (with confirmation)

### AI Configuration
- `python main.py switch_model <model>` - Switch to a different AI model
- `python main.py providers` - List all configured AI providers
- `python main.py promote_key <provider> <key> --to=primary|fallback` - Manage key priority

### Diagnostic & Debugging
- `python main.py health` - Comprehensive system health check
- `python main.py exec "<command>"` - Execute shell commands with style

### Interactive Mode
- `python main.py chat` - Enter the Neural Link interactive session

### Advanced Features
- `python main.py review` - Get a performance review from Naze
- `python main.py clear` - Clear the task database
- `python main.py exec "<command>"` - Execute shell commands

## ⚖️ License

Licensed under the [MIT License](LICENSE). Naze doesn't care what you do with the code, as long as you actually finish your tasks.

## 📞 Need Help?

- **Health check:** `python main.py health`
- **Debugging:** `python main.py chat` (the Neural Link can diagnose issues)
- **Emergency wipe:** `python main.py clear` (with confirmation)

Happy optimizing!