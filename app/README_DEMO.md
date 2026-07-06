# SPARTA / ICS ATT&CK Demo

Standalone HTML files that visualize attack frameworks offline. Click any technique card, select "Example Script" tab, and generate a Python code sample via local Ollama.

## What you need

- Linux (Ubuntu native), macOS, or any machine that can run Ollama
- Official Ollama install (the `curl | sh` installer, **not** the snap — strict snap confinement strips the CORS env var)
- One model pulled locally (e.g., `gemma3`, ~5GB)
- Modern browser (Firefox, Chrome, Edge)
- No Docker, web server, or internet required at demo time

## One-time setup

```bash
# 1. If you previously had the snap installed, remove it
sudo snap remove ollama

# 2. Install the official Ollama (creates a systemd service)
curl -fsSL https://ollama.ai/install.sh | sh

# 3. Enable CORS so a file:// HTML page can call the API
sudo systemctl edit ollama
# In the editor, paste these lines under the override header and save:
#   [Service]
#   Environment="OLLAMA_ORIGINS=*"

# 4. Restart the service to pick up the env var
sudo systemctl restart ollama

# 5. Pull a model (gemma3 recommended, ~5GB)
ollama pull gemma3

# 6. Verify
ollama list
curl -s http://localhost:11434/api/tags | head
```

## Running the demo

1. Confirm the service is running:
   ```bash
   systemctl is-active ollama   # should print: active
   ```

2. Open `app/sparta_coverage.html` (or `ics_standalone.html`) in your browser.

3. Click any technique card → "Example Script" tab → "Generate". The LLM writes sample Python.

**Tip:** Right-click a technique card to open it directly to the Example Script tab.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| CORS error in DevTools | `systemctl show ollama -p Environment` should show `OLLAMA_ORIGINS=*`. If not, redo step 3 and `sudo systemctl restart ollama`. |
| "Could not reach Ollama" | `curl http://localhost:11434` in another terminal. If refused, `sudo systemctl restart ollama`. |
| 404 from Ollama on Generate | The model isn't pulled. Run `ollama pull gemma3` (or whatever model name is in the input field). |
| First generation is slow | Normal — Ollama loads the model into memory on first use. |
| CPU is maxed out | No GPU detected; CPU inference is slow but works. Try a smaller model (`ollama pull llama3.2:1b`). |
| Output doesn't update | Hard-reload the page (Ctrl+Shift+R) or open in a private window. |

## What this is NOT

This demo generates illustrative Python examples only. It is not a real attack tool, not connected to any spacecraft or live systems, and output is for educational reference. Do not execute generated code without careful review.
