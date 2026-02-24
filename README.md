🎵 Generative Lyrics Analyzer
An NLP-powered web application that performs section-wise semantic analysis of song lyrics using a locally deployed LLM.

🚀 Project Overview
This project analyzes song lyrics and generates:
- Song-level summary
- Section-wise explanations (Verse, Chorus, Bridge)
- Emotional tone detection
- Key lyric lines
- Related YouTube video metadata
- Built using Flask + Genius API + YouTube Data API + Qwen 2.5 (Ollama).

🧠 NLP Techniques Used
- Text preprocessing & normalization
- Regex-based structural parsing
- Prompt engineering with JSON-constrained outputs
- Emotional tone classification
- Generative semantic explanation via local LLM

🛠 Tech Stack
Backend:
- Flask (Python)
- Genius API
- YouTube Data API

NLP Model:
- Qwen 2.5 (3B / 7B)
- Running locally via Ollama

💡 Why This Project?
Music lovers often search separately for lyrics, meanings, and interpretations.
This system combines everything into one structured NLP-powered interface.
