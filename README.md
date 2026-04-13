# 🤖 Resume Screener Bot

> **AI-powered console application** that screens resumes against job descriptions and generates tailored cover letters — supporting **Anthropic Claude**, **Google Gemini**, and **Groq / LLaMA**, displayed with a beautiful **Rich** terminal UI.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🤖 **Multi-Provider AI** | Choose Claude, Gemini (free), or Groq/LLaMA (free) at startup |
| 📄 **PDF Parsing** | Extracts text from any PDF resume using PyMuPDF |
| 🔍 **AI Resume Screening** | Scores 0–100 with strengths, weaknesses, missing keywords, and suggestions |
| 📊 **Visual Results** | Colour-coded progress bars, side-by-side panels, keyword badges |
| ✉️ **Cover Letter Gen** | Tailored 3-4 paragraph letters in Formal / Conversational / Enthusiastic tone |
| 💾 **File Save** | Save cover letters as timestamped `.txt` files |
| 📈 **Session Summary** | Tracks provider used, resumes screened, average score, and files saved |
| 🛡️ **Robust Error Handling** | Clear messages for missing API key, bad PDF, network errors, rate limits |

---

## 🤖 Supported AI Providers

| # | Provider | Free Tier | API Key Env Var | Get Key |
|---|---|---|---|---|
| 1 | **Anthropic Claude** | ❌ Paid | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| 2 | **Google Gemini** | ✅ Free | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| 3 | **Groq / LLaMA** | ✅ Free | `GROQ_API_KEY` | [console.groq.com](https://console.groq.com/keys) |

> **Tip:** Set any one key to get started. You can set multiple keys to switch between providers.

---

## 🛠 Tech Stack

| Component | Library / Tool |
|---|---|
| Language | Python 3.10+ |
| Console UI | [Rich](https://github.com/Textualize/rich) |
| PDF Parsing | [PyMuPDF (fitz)](https://pymupdf.readthedocs.io) |
| AI — Claude | [Anthropic SDK](https://docs.anthropic.com) · `claude-3-5-sonnet-20241022` |
| AI — Gemini | [google-generativeai](https://ai.google.dev/gemini-api/docs) · `gemini-1.5-flash` |
| AI — Groq | [groq](https://console.groq.com/docs) · `llama3-8b-8192` |

---

## 🚀 Setup

### 1 — Clone the repository

```bash
git clone https://github.com/your-username/Resume-Screener-Bot.git
cd Resume-Screener-Bot
```

### 2 — Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows
```

### 3 — Install dependencies

```bash
pip install -r resume_screener/requirements.txt
```

### 4 — Set at least one AI API key

Pick whichever provider you want to use — you only need **one** key:

```bash
# Option A — Anthropic Claude (paid)
export ANTHROPIC_API_KEY="sk-ant-..."

# Option B — Google Gemini (free)
export GEMINI_API_KEY="AIza..."

# Option C — Groq / LLaMA (free, fastest)
export GROQ_API_KEY="gsk_..."
```

> **Tip:** Add the `export` line(s) to your `~/.bashrc` or `~/.zshrc` so they persist across sessions.

---

## ▶️ How to Run

```bash
cd Resume-Screener-Bot
source venv/bin/activate
cd resume_screener
python main.py
```

### Step 0 — Provider Selection

After the welcome banner, you'll see a provider picker. Keys that are already set show a green ✓:

```
╭────────────────────────────────────────────╮
│ 🤖  Select Your AI Provider                │
├────────────────────────────────────────────┤
│  [1]  Anthropic Claude           ✓         │
│  [2]  Google Gemini   (Free)     ✗         │
│  [3]  Groq / LLaMA    (Free)     ✗         │
╰────────────────────────────────────────────╯
  ✓ = API key found   ✗ = key missing
```

If the key for your chosen provider is missing, the bot shows exactly what to export and lets you pick again.

### Option 1 — Screen Resume

1. Enter the path to a `.pdf` resume
2. Paste or load a job description (direct paste or `.txt` file)
3. The AI analyses the resume and displays:
   - Match score (0-100) with colour-coded progress bar
   - Strengths (green) and weaknesses (red) side-by-side
   - Missing keywords as yellow badges
   - Numbered suggestions for improvement
   - Verdict banner: **Strong / Moderate / Weak Match**

### Option 2 — Generate Cover Letter

1. Enter the path to a `.pdf` resume
2. Paste or load a job description
3. Choose tone: **Formal**, **Conversational**, or **Enthusiastic**
4. Optionally add something specific to highlight
5. The AI generates a tailored 3-4 paragraph cover letter
6. Preview in a styled panel, then save as `.txt`

---

## 📁 Project Structure

```
Resume-Screener-Bot/
├── venv/                    # Virtual environment (not committed)
└── resume_screener/
    ├── main.py              # Entry point, provider picker, menu loop, session tracking
    ├── ai_provider.py       # Unified AI wrapper (Claude / Gemini / Groq)
    ├── parser.py            # PDF text extraction (PyMuPDF)
    ├── screener.py          # AI resume scoring engine
    ├── cover_letter.py      # AI cover letter generator
    ├── utils.py             # Shared console, theme, helpers, JD input
    └── requirements.txt     # Python dependencies
```

---

## 🖼 Screenshots

> _Add screenshots of the running application here._

| Screen | Preview |
|---|---|
| Welcome Banner | _(screenshot)_ |
| Provider Selection | _(screenshot)_ |
| Resume Parsed Summary | _(screenshot)_ |
| Screening Results | _(screenshot)_ |
| Cover Letter Panel | _(screenshot)_ |
| Session Summary | _(screenshot)_ |

---

## ⚙️ Configuration

| Setting | Where to change |
|---|---|
| Claude model | `_MODELS["claude"]` in `ai_provider.py` |
| Gemini model | `_MODELS["gemini"]` in `ai_provider.py` |
| Groq model | `_MODELS["groq"]` in `ai_provider.py` |
| Max resume chars sent to AI | `RESUME_LIMIT` in `screener.py` / `cover_letter.py` |
| Min job description length | `_MIN_JD_CHARS` in `utils.py` |

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| Key env var missing (`✗` in picker) | `export ANTHROPIC_API_KEY='...'` (or GEMINI / GROQ) |
| `No text extracted from PDF` | PDF is image-based — run it through an OCR tool first |
| Claude `AuthenticationError` | Key is invalid — generate a new one at console.anthropic.com |
| Claude `RateLimitError` | Wait 30–60 s, or upgrade your Anthropic plan |
| Gemini quota exceeded | Wait or upgrade at aistudio.google.com |
| Groq rate limit | Groq free tier is very generous — wait a few seconds |
| `APIConnectionError` | Check your internet connection |
| `google-generativeai` import error | `pip install google-generativeai` |
| `groq` import error | `pip install groq` |
| Cover letter is generic | Add a specific highlight when prompted |

---

## 📄 License

MIT — feel free to use, modify, and distribute.

---

## 🙏 Acknowledgements

- [Anthropic](https://anthropic.com) — Claude AI models
- [Google DeepMind](https://deepmind.google) — Gemini models
- [Groq](https://groq.com) — Ultra-fast LLaMA inference
- [Textualize/Rich](https://github.com/Textualize/rich) — Beautiful terminal UI
- [PyMuPDF](https://pymupdf.readthedocs.io) — PDF text extraction
