import re
import json
import os

import streamlit as st
import google.generativeai as genai

# ──────────────── PAGE CONFIG ───────────────────────────────
st.set_page_config(page_title="Quiz AI Game Show", layout="wide")

# ──────────────── CSS INJECTION ─────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    /* Force dark, high-contrast UI in both themes */
    body[data-theme="light"], body[data-theme="dark"] {
      background-color: #121212 !important;
      color: #eee !important;
    }
    /* Clear any light-theme panel backgrounds */
    .css-1d391kg, .css-1lcbmhc, .css-1pv0x7i {
      background-color: transparent !important;
    }
    /* Title & subtitle */
    .title {
      text-align: center;
      font-size: 4rem;
      font-weight: 900;
      color: #00e5ff !important;
      text-shadow: 4px 4px 8px rgba(0,0,0,0.5);
      margin-bottom: 0.2em;
    }
    .subtitle {
      text-align: center;
      font-size: 1.5rem;
      color: #80deea !important;
      margin-bottom: 1em;
    }
    .banner { display: flex; justify-content: center; margin-bottom: 1em; }
    /* Question container */
    .question {
      font-size: 2rem;
      padding: 20px;
      background: linear-gradient(135deg, #1e1e1e, #272727) !important;
      border: 3px solid #00e5ff !important;
      border-radius: 12px !important;
      margin: 20px 0 !important;
      color: #fff !important;
    }
    /* Feedback banners */
    .feedback {
      font-size: 1.25rem;
      padding: 15px;
      border-radius: 8px;
      margin-bottom: 1em;
      text-align: center;
    }
    .feedback.success { background-color: #2e7d32 !important; color: #fff !important; }
    .feedback.error   { background-color: #c62828 !important; color: #fff !important; }
    /* Centered buttons */
    .stButton > button {
      display: block;
      margin: 1em auto;
      font-size: 1.25rem;
      padding: 0.75em 2em;
      background: #00e5ff !important;
      color: #121212 !important;
      border: none !important;
      border-radius: 8px !important;
      box-shadow: 2px 2px 8px rgba(0,0,0,0.4) !important;
      transition: background 0.2s ease !important;
    }
    .stButton > button:hover { background: #00b8d4 !important; }
    /* Score metrics */
    .stMetric {
      background: #1e1e1e !important;
      border-radius: 12px !important;
      padding: 1em !important;
    }
    /* Footer */
    .footer {
      text-align: center;
      font-size: 1.25rem !important;
      color: #aaa !important;
      margin-top: 40px !important;
      padding-top: 20px !important;
      border-top: 1px solid #333 !important;
    }
    </style>
    """, unsafe_allow_html=True)

inject_css()

# ──────────────── HEADER VISUALS ───────────────────────────
st.markdown('<div class="title">QUIZ AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Test your knowledge in a fun, game-show style!</div>', unsafe_allow_html=True)
if os.path.exists("images/banner.png"):
    st.markdown(f'<div class="banner"><img src="images/banner.png" width="600"></div>', unsafe_allow_html=True)

# ──────────────── LOAD API KEY ──────────────────────────────
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("🔑 Please add your GEMINI_API_KEY to `.streamlit/secrets.toml` and restart.")
    st.stop()
genai.configure(api_key=api_key)
MODEL_NAME = "gemini-1.5-flash"

# ──────────────── QUIZ GENERATION ───────────────────────────
def generate_quiz(topic: str, num_q: int, difficulty: str):
    prompt = (
        "You are a quiz-making assistant.\n"
        "Output ONLY valid JSON in this exact shape:\n\n"
        '{ "questions": [ { "q": "QUESTION TEXT", "a": "ANSWER TEXT" }, ... ] }\n\n'
        f"Please create {num_q} {difficulty.lower()} difficulty questions on the topic: \"{topic}\"."
    )
    resp = genai.GenerativeModel(MODEL_NAME).generate_content(prompt)
    text = resp.text.strip()
    match = re.search(r"\{[\s\S]*\}", text)
    json_str = match.group(0) if match else text
    try:
        return json.loads(json_str)["questions"]
    except Exception as e:
        st.error(f"Failed to parse quiz JSON: {e}\n\nExtracted:\n```json\n{json_str}\n```")
        return []

# ──────────────── ANSWER EVALUATION ─────────────────────────
def evaluate_answer(question: str, correct_ans: str, user_ans: str):
    prompt = (
        "You are a quiz grader.\n"
        f"Question: \"{question}\"\n"
        f"Correct answer: \"{correct_ans}\"\n"
        f"User's answer: \"{user_ans}\"\n\n"
        "Determine if the user's answer is correct (allow minor synonyms/casing), "
        "then provide a brief, friendly feedback message.\n"
        "Output ONLY valid JSON in this exact shape:\n"
        '{ "correct": true|false, "feedback": "..." }'
    )
    resp = genai.GenerativeModel(MODEL_NAME).generate_content(prompt)
    text = resp.text.strip()
    match = re.search(r"\{[\s\S]*\}", text)
    json_str = match.group(0) if match else text
    try:
        return json.loads(json_str)
    except Exception:
        correct = user_ans.strip().lower() == correct_ans.strip().lower()
        return {
            "correct": correct,
            "feedback": "Great job!" if correct else f"The correct answer was “{correct_ans}.”"
        }

# ──────────────── CALLBACKS ─────────────────────────────────
def handle_submit(idx: int):
    q = st.session_state.questions[idx]
    ua = st.session_state.pop(f"ans_{idx}", "")
    result = evaluate_answer(q["q"], q["a"], ua)
    st.session_state.feedback = result
    if result["correct"]:
        st.session_state.user_score += 1
    else:
        st.session_state.ai_score += 1
    st.session_state.idx += 1

def reset_quiz():
    for k in ["questions", "idx", "user_score", "ai_score", "generated", "feedback", "difficulty"]:
        st.session_state.pop(k, None)

# ──────────────── APP STATE SETUP ───────────────────────────
if "questions" not in st.session_state:
    st.session_state.update({
        "questions": [], "idx": 0,
        "user_score": 0, "ai_score": 0,
        "generated": False, "feedback": {}
    })

# ──────────────── SIDEBAR: SETUP FORM ──────────────────────
with st.sidebar.form("setup_form"):
    topic = st.text_input("Quiz Topic", placeholder="e.g. Astronomy")
    difficulty = st.selectbox("Difficulty Level", ["Easy", "Medium", "Hard"])
    num_q = st.number_input("Number of Questions", min_value=1, max_value=30, value=5)
    if st.form_submit_button("Generate Quiz"):
        st.session_state.difficulty = difficulty
        st.session_state.questions = generate_quiz(topic, num_q, difficulty)
        st.session_state.idx = 0
        st.session_state.user_score = 0
        st.session_state.ai_score = 0
        st.session_state.generated = True
        st.session_state.feedback = {}

# ──────────────── MAIN QUIZ FLOW ───────────────────────────
if st.session_state.get("generated", False):
    qs = st.session_state.questions
    total = len(qs)

    # Show selected difficulty
    st.markdown(f"**Difficulty:** {st.session_state.difficulty}")

    # Scoreboard
    c1, c2 = st.columns(2)
    c1.metric("Your Score", st.session_state.user_score)
    c2.metric("AI Score", st.session_state.ai_score)

    # In-quiz
    if total and st.session_state.idx < total:
        fb = st.session_state.feedback
        if fb:
            cls = "success" if fb["correct"] else "error"
            st.markdown(f'<div class="feedback {cls}">{fb["feedback"]}</div>', unsafe_allow_html=True)
            st.session_state.feedback = {}

        i = st.session_state.idx
        q = qs[i]
        st.markdown(f'<div class="question">Q{i+1}/{total}: {q["q"]}</div>', unsafe_allow_html=True)

        with st.form(f"form_{i}", clear_on_submit=True):
            st.text_input("Your Answer", key=f"ans_{i}", label_visibility="collapsed")
            st.form_submit_button(
                "Submit & Next ▶️",
                on_click=lambda i=i: handle_submit(i)
            )

    # Quiz complete
    elif total:
        fb = st.session_state.feedback
        if fb:
            cls = "success" if fb["correct"] else "error"
            st.markdown(f'<div class="feedback {cls}">{fb["feedback"]}</div>', unsafe_allow_html=True)

        st.markdown("## 🎉 Quiz Complete!")
        st.write(f"**Topic:** {topic} • **Difficulty:** {st.session_state.difficulty}")
        st.write(f"**Your final score:** {st.session_state.user_score}")
        st.write(f"**AI final score:** {st.session_state.ai_score}")
        if st.session_state.user_score > st.session_state.ai_score:
            st.balloons()
            st.success("You beat the AI! 🏆")
        else:
            st.warning("The AI wins… better luck next time.")

        st.button("🔄 Take Another Quiz", on_click=reset_quiz)

    else:
        st.error("No questions were generated. Try a different topic or fewer questions.")
else:
    st.write("Use the sidebar to choose a topic, difficulty, and start the quiz!")

# ──────────────── FOOTER ────────────────────────────────────
st.markdown(
    """
    <div class="footer">
      Created by 
      <a href="https://your-website.com" target="_blank"
         style="color:inherit; text-decoration:underline;">
        Naadir
      </a>
      • Powered by Gemini 1.5-flash
    </div>
    """,
    unsafe_allow_html=True
)
