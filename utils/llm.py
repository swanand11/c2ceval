import requests
import re
import time

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi3"  # Optimized for speed


def get_architecture_score(text):
    """
    Score repository architecture using local Ollama.
    Optimized for:
    - Limited concurrency (3 max)
    - Fast responses (~20-30s)
    - Short token generation
    """
    # Cap input to 2000 chars for faster processing
    text = text[:2000]

    prompt = f"""Rate code architecture 0-100 (number only):

{text}"""

    print("    🚀 Sending request to Ollama...")
    start = time.perf_counter()

    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 10,  # Max tokens for output
                    "temperature": 0.1,  # Very deterministic
                    "top_k": 10,  # Limit to top 10 tokens
                    "top_p": 0.3,  # Nucleus sampling
                }
            },
            timeout=(5, 90),  # 5s connect, 90s read (optimized for Ollama)
            headers={"Connection": "close"},
        )

        elapsed = time.perf_counter() - start
        print(f"    ⏱️ Ollama responded in {elapsed:.2f}s")

        res.raise_for_status()
        data = res.json()

        output = data.get("response", "").strip()
        print(f"    🧠 Raw output: {output!r}")

        # ✅ STRICT PARSING
        match = re.search(r"\b\d{1,3}\b", output)

        if not match:
            print("    ⚠️ No number found → returning 50")
            return 50, "No numeric score in LLM output"

        score = int(match.group())

        if score < 0 or score > 100:
            print("    ⚠️ Score out of range → returning 50")
            return 50, f"Invalid score: {score}"

        print(f"    ✅ Score: {score}")
        return score, "OK"

    except requests.exceptions.ConnectTimeout:
        return 50, "Connection timeout (Ollama not reachable)"

    except requests.exceptions.ReadTimeout:
        return 50, "Read timeout (model too slow)"

    except requests.exceptions.ConnectionError:
        return 50, "Ollama not running"

    except Exception as e:
        return 50, f"Unexpected error: {e}"