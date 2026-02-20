import os
import time
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import praw
from groq import Groq
import json

# Import database functions
from database import (
    init_db_pool, close_db_pool,
    save_lead_to_db, get_all_saved_leads, check_if_lead_saved,
    delete_saved_lead, update_lead_notes, mark_lead_contacted,
    get_saved_leads_stats,
    dismiss_post, get_dismissed_post_ids, cleanup_expired_dismissed_posts
)

# Import authentication functions
from auth import (
    init_auth_pool, signup_user, verify_otp,
    login_user, verify_session, logout_user,
    request_password_reset, reset_password,
    track_query, check_query_limit,
    get_user_profile, update_user_profile  # ← ADD THIS
)
from email_service import send_otp_email, send_welcome_email

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
CORS(app)

# Initialize Reddit API
reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent=os.getenv('REDDIT_USER_AGENT'),
    check_for_async=False
)

# Initialize Groq AI
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# =====================================================
# PER-USER SESSION STATE  (replaces bare globals)
# Key: user_id (str)  Value: dict with posts/ids/prompt
# =====================================================
_user_states = {}
_user_states_lock = threading.Lock()

def get_user_state(user_id: str) -> dict:
    """Return (and lazily create) the state dict for a given user."""
    with _user_states_lock:
        if user_id not in _user_states:
            _user_states[user_id] = {
                'discovered_posts': [],
                'seen_post_ids':    set(),
                'user_prompt':      '',
                'user_company':     '',
                'user_niche':       '',
            }
        return _user_states[user_id]

# Legacy module-level names kept so any existing internal helper that still
# references them won't hard-crash; they are only used as fallback defaults.
discovered_posts = []
seen_post_ids    = set()
user_prompt      = ''
user_company     = ''
user_niche       = ''

# =====================================================
# RATE LIMITING  — per-user, thread-safe
# =====================================================
MIN_REQUEST_INTERVAL = 1.0
_rate_limit_locks  = {}          # user_id → Lock
_rate_limit_times  = {}          # user_id → float (last call time)
_rate_limit_meta   = threading.Lock()

# A single global lock for the Reddit PRAW client itself.
# PRAW is not thread-safe across simultaneous calls; serialising Reddit
# calls with a lock is the safest approach without spinning up multiple
# Reddit instances.
_reddit_lock = threading.Lock()

def rate_limit_check(user_id: str = '__global__'):
    """Thread-safe, per-user rate limiter."""
    with _rate_limit_meta:
        if user_id not in _rate_limit_locks:
            _rate_limit_locks[user_id] = threading.Lock()
            _rate_limit_times[user_id] = 0.0

    lock = _rate_limit_locks[user_id]
    with lock:
        now   = time.time()
        delta = now - _rate_limit_times[user_id]
        if delta < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - delta)
        _rate_limit_times[user_id] = time.time()


# =====================================================
# API CALL COUNTERS  — protected by a lock
# =====================================================
api_stats = {
    'reddit_calls': 0,
    'groq_calls':   0,
    'groq_tokens': {
        'total': 0,
        'subreddit_discovery': {'prompt': 0, 'completion': 0, 'calls': 0},
        'post_analysis':       {'prompt': 0, 'completion': 0, 'calls': 0},
        'response_generation': {'prompt': 0, 'completion': 0, 'calls': 0},
        'test_connection':     {'prompt': 0, 'completion': 0, 'calls': 0},
    }
}
_stats_lock = threading.Lock()

def _inc_reddit():
    with _stats_lock:
        api_stats['reddit_calls'] += 1

def _inc_groq(category: str, pt: int, ct: int):
    with _stats_lock:
        api_stats['groq_calls']                        += 1
        api_stats['groq_tokens']['total']              += pt + ct
        api_stats['groq_tokens'][category]['prompt']   += pt
        api_stats['groq_tokens'][category]['completion']+= ct
        api_stats['groq_tokens'][category]['calls']    += 1

def print_api_stats():
    t = api_stats['groq_tokens']
    print("\n" + "="*60)
    print("API USAGE SUMMARY")
    print("="*60)
    print(f"  Reddit API calls  : {api_stats['reddit_calls']}")
    print(f"  Groq API calls    : {api_stats['groq_calls']}")
    print(f"  Groq total tokens : {t['total']}")
    print("  Groq token breakdown:")
    for key, label in [
        ('subreddit_discovery', 'Subreddit discovery'),
        ('post_analysis',       'Post analysis      '),
        ('response_generation', 'Response generation'),
        ('test_connection',     'Test connection    '),
    ]:
        d = t[key]
        if d['calls'] > 0:
            total_here = d['prompt'] + d['completion']
            print(f"    {label}: {total_here} tokens "
                  f"({d['prompt']} prompt + {d['completion']} completion) "
                  f"x {d['calls']} call(s)")
    print("="*60 + "\n")


# =====================================================
# GROQ HELPER
# =====================================================

def call_groq_ai(system_prompt, user_message, temperature=0.3,
                 max_tokens=500, token_category='test_connection'):
    """Call Groq AI. Thread-safe stats update via _inc_groq()."""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        usage = response.usage
        if usage:
            pt = usage.prompt_tokens    or 0
            ct = usage.completion_tokens or 0
            _inc_groq(token_category, pt, ct)
            print(f"  [Groq/{token_category}] +{pt+ct} tokens "
                  f"(prompt:{pt} completion:{ct})")
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq AI Error: {str(e)}")
        return None


# =====================================================
# SUBREDDIT DISCOVERY  (unchanged logic)
# =====================================================

def discover_subreddits(prompt, company='', niche=''):
    context_parts = []
    if company: context_parts.append(f"Company: {company}")
    if niche:   context_parts.append(f"Niche/Industry: {niche}")
    context_parts.append(f"Description: {prompt}")
    full_context = "\n".join(context_parts)

    system_prompt = """You are a Reddit expert. Suggest 8-12 ACTIVE, PUBLIC subreddits where people ask for help and advice.

Focus on subreddits where:
- People actively ask questions and seek solutions
- Community helps each other with problems
- Advice-seeking posts are common
- NOT just news/discussion subreddits

IMPORTANT: Only suggest subreddits that:
- Actually exist on Reddit
- Are public (not private/banned)
- Have regular activity
- Use correct lowercase names (e.g., 'entrepreneur' not 'Entrepreneur')

Respond ONLY with valid JSON:
{
  "subreddits": [
    {
      "name": "subreddit_name",
      "relevance_score": 85,
      "reason": "Why people here need help with this",
      "estimated_size": "large/medium/small"
    }
  ]
}"""

    user_message = f'Find help-seeking subreddits for:\n{full_context}'
    result = call_groq_ai(system_prompt, user_message, temperature=0.4,
                          max_tokens=1000, token_category='subreddit_discovery')
    if not result:
        return []

    try:
        if result.startswith('```'):
            result = result.split('```')[1]
            if result.startswith('json'):
                result = result[4:]
            result = result.strip()
        data = json.loads(result)
        return data.get('subreddits', [])
    except Exception as e:
        print(f"Error parsing subreddits: {str(e)}")
        return []


# =====================================================
# POST ANALYSIS  (unchanged logic, thread-safe)
# =====================================================

def analyze_post_with_ai(post_data, user_context):
    """Analyse one post. Can be called from any thread safely."""
    result = call_groq_ai(
        system_prompt=f"""You are a STRICT lead qualifier analyzing Reddit posts.

{user_context}

CRITICAL RULES:
1. ONLY score high (70+) if the post shows ACTIVE HELP-SEEKING or PROBLEM-SOLVING intent
2. Look for: questions, "how do I", "need help", "looking for", "struggling with", "advice needed"
3. REJECT posts that are just: news, discussions, success stories, announcements, general chat
4. The post must show the person WANTS a solution or service that matches the business above
5. Keyword matches alone are NOT enough - intent is everything

Be VERY strict. When in doubt, score lower.""",
        user_message=f"""Analyze this post - is this person ACTIVELY SEEKING HELP?

Title: {post_data['title']}
Subreddit: r/{post_data['subreddit']}
Content: {post_data['content'][:1000]}

Respond ONLY with valid JSON:
{{
  "relevancy_score": <0-100>,
  "is_help_seeking": <true/false>,
  "help_seeking_signals": ["signal1", "signal2"],
  "reasoning": "<2-3 sentences>",
  "intent_strength": "<low/medium/high>",
  "potential_value": "<low/medium/high>",
  "key_pain_points": ["pain1", "pain2"]
}}""",
        max_tokens=700,
        token_category='post_analysis'
    )

    _fallback = {
        "relevancy_score": 0, "is_help_seeking": False,
        "help_seeking_signals": [], "reasoning": "Failed",
        "intent_strength": "low", "potential_value": "low",
        "key_pain_points": []
    }

    if not result:
        return _fallback

    try:
        if result.startswith('```'):
            result = result.split('```')[1]
            if result.startswith('json'):
                result = result[4:]
            result = result.strip()
        return json.loads(result)
    except json.JSONDecodeError as e:
        print(f"[WARN] JSON parse failed in analyze_post: {e}")
        print(f"  Raw response was: {result[:300]}")
        return {**_fallback, "reasoning": "Parse error"}

def analyze_batch_of_posts(posts_batch: list, user_context: str) -> list:
    """
    Analyze up to 6 posts in a single Groq AI call.
    Returns list of analysis results in same order as input.
    """
    if len(posts_batch) > 6:
        raise ValueError("Batch size cannot exceed 6 posts")
    
    # Build batch prompt with all posts
    posts_text = ""
    for idx, post in enumerate(posts_batch, 1):
        posts_text += f"""
POST {idx}:
Title: {post['title']}
Subreddit: r/{post['subreddit']}
Content: {post['content'][:800]}
---
"""
    
    system_prompt = f"""You are a STRICT lead qualifier analyzing Reddit posts.

{user_context}

CRITICAL RULES:
1. ONLY score high (70+) if the post shows ACTIVE HELP-SEEKING or PROBLEM-SOLVING intent
2. Look for: questions, "how do I", "need help", "looking for", "struggling with", "advice needed"
3. REJECT posts that are just: news, discussions, success stories, announcements, general chat
4. The post must show the person WANTS a solution or service that matches the business above
5. Keyword matches alone are NOT enough - intent is everything

Be VERY strict. When in doubt, score lower.

You will analyze {len(posts_batch)} posts below. Respond with a JSON array containing one analysis object per post, IN THE SAME ORDER."""

    user_message = f"""Analyze these {len(posts_batch)} posts - is each person ACTIVELY SEEKING HELP?

{posts_text}

Respond ONLY with valid JSON array (one object per post, in order):
[
  {{
    "post_number": 1,
    "relevancy_score": <0-100>,
    "is_help_seeking": <true/false>,
    "help_seeking_signals": ["signal1", "signal2"],
    "reasoning": "<2-3 sentences>",
    "intent_strength": "<low/medium/high>",
    "potential_value": "<low/medium/high>",
    "key_pain_points": ["pain1", "pain2"]
  }},
  ...
]"""

    result = call_groq_ai(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=2000,  # Increased for batch response
        temperature=0.3,
        token_category='post_analysis'
    )

    _fallback = {
        "relevancy_score": 0, "is_help_seeking": False,
        "help_seeking_signals": [], "reasoning": "Failed",
        "intent_strength": "low", "potential_value": "low",
        "key_pain_points": []
    }

    if not result:
        return [_fallback] * len(posts_batch)

    try:
        # Clean markdown fences
        if result.startswith('```'):
            result = result.split('```')[1]
            if result.startswith('json'):
                result = result[4:]
            result = result.strip()
        
        analyses = json.loads(result)
        
        # Validate response length matches batch
        if not isinstance(analyses, list):
            print(f"[WARN] Batch analysis returned non-list: {type(analyses)}")
            return [_fallback] * len(posts_batch)
        
        if len(analyses) != len(posts_batch):
            print(f"[WARN] Batch analysis returned {len(analyses)} results for {len(posts_batch)} posts")
            # Pad or truncate to match
            while len(analyses) < len(posts_batch):
                analyses.append(_fallback)
            analyses = analyses[:len(posts_batch)]
        
        return analyses
        
    except json.JSONDecodeError as e:
        print(f"[WARN] JSON parse failed in batch analysis: {e}")
        print(f"  Raw response was: {result[:500]}")
        return [_fallback] * len(posts_batch)
    
    #- Only mention the company/service if it is a genuinely natural fit

# =====================================================
# RESPONSE GENERATION  (unchanged logic)
# =====================================================

def generate_ai_response(post_data, user_context):
    result = call_groq_ai(
        system_prompt=f"""You are a knowledgeable Redditor replying to a post.

{user_context}

Rules:
- Keep the reply SHORT (3-5 sentences max)
- Directly address the person's specific pain point
- Provide one concrete, actionable insight
- Mention the company/service and niche in a genuinely natural fit that looks like a real recommendation, not an ad
- Sound like a real person, not a marketer""",
        user_message=f"""Write a concise Reddit reply to this post:

Title: {post_data['title']}
Content: {post_data['content'][:1200]}
Key pain points: {', '.join(post_data.get('key_pain_points', []))}""",
        temperature=0.7,
        max_tokens=300,
        token_category='response_generation'
    )
    return result if result else "Unable to generate response."


# =====================================================
# POST NORMALIZER  (unchanged)
# =====================================================

def normalize_post(submission):
    return {
        'id':           submission.id,
        'title':        submission.title,
        'subreddit':    str(submission.subreddit),
        'author':       str(submission.author) if submission.author else '[deleted]',
        'score':        submission.score,
        'timestamp':    datetime.fromtimestamp(submission.created_utc).isoformat(),
        'created_utc':  submission.created_utc,
        'url':          f"https://reddit.com{submission.permalink}",
        'content':      submission.selftext[:2500] if submission.selftext else '[No text content]',
        'num_comments': submission.num_comments
    }


# =====================================================
# REDDIT FETCHER  — now thread-safe via _reddit_lock
# =====================================================

def fetch_posts_from_subreddit(subreddit_name: str, latest_count: int = 30,
                                seen_ids: set = None, user_id: str = '__global__') -> list:
    """
    Fetch posts from one subreddit.

    - seen_ids: a set shared by the caller; this function checks it but does
      NOT mutate it (the caller merges back after all threads finish, keeping
      deduplication correct without a race condition).
    - _reddit_lock serialises all PRAW calls so the single reddit object is
      never accessed concurrently.
    """
    posts      = []
    seen_ids   = seen_ids or set()

    try:
        with _reddit_lock:
            rate_limit_check(user_id)
            subreddit = reddit.subreddit(subreddit_name)
            try:
                _ = subreddit.id          # existence check
                _inc_reddit()
            except Exception:
                print(f"Skipping r/{subreddit_name}: Not accessible")
                return []

            print(f"Fetching latest {latest_count} posts from r/{subreddit_name}...")

            rate_limit_check(user_id)
            new_posts = list(subreddit.new(limit=latest_count))
            _inc_reddit()

        # Post-processing happens outside the lock — pure Python, no PRAW calls
        for sub in new_posts:
            if sub.id not in seen_ids:
                if sub.selftext and len(sub.selftext.strip()) > 50:
                    posts.append(normalize_post(sub))

        print(f"Found {len(posts)} text posts from r/{subreddit_name}")
        return posts

    except Exception as e:
        print(f"Error r/{subreddit_name}: {str(e)}")
        return []


# =====================================================
# PARALLEL REDDIT FETCHER
# =====================================================
# Workers: 3 — enough to overlap network wait time while staying well within
# Reddit's rate limits (≤ 60 req/min for OAuth apps).
REDDIT_WORKERS = 3

def fetch_all_subreddits_parallel(subreddits: list, posts_per_subreddit: int,
                                   seen_ids: set, user_id: str) -> list:
    """
    Fetch posts from all subreddits in parallel (up to REDDIT_WORKERS at once).
    Deduplication is applied after all futures complete so there are no
    set-mutation races between threads.
    """
    all_posts      = []
    newly_seen_ids = set()   # accumulate new IDs here, merge into seen_ids after

    with ThreadPoolExecutor(max_workers=REDDIT_WORKERS) as executor:
        future_to_sub = {
            executor.submit(
                fetch_posts_from_subreddit,
                sub,
                posts_per_subreddit,
                seen_ids,    # passed as read-only snapshot
                user_id
            ): sub
            for sub in subreddits
        }

        for future in as_completed(future_to_sub):
            sub  = future_to_sub[future]
            try:
                posts = future.result()
                for post in posts:
                    if post['id'] not in seen_ids and post['id'] not in newly_seen_ids:
                        all_posts.append(post)
                        newly_seen_ids.add(post['id'])
            except Exception as e:
                print(f"[WARN] Future failed for r/{sub}: {e}")

    # Safe to mutate seen_ids now — all threads are done
    seen_ids.update(newly_seen_ids)
    return all_posts


# =====================================================
# PARALLEL GROQ ANALYSER
# =====================================================
# Workers: 5 — Groq's free tier allows ~30 req/min on llama-3.3-70b;
# 5 concurrent workers leaves comfortable headroom. 
GROQ_WORKERS = 3

def process_and_analyze_posts_parallel(posts: list, user_context: str) -> list:
    """
    Analyse posts with Groq AI using batched processing (6 posts per call).
    Uses parallel workers to process multiple batches concurrently.
    
    Batching reduces API calls by 6x while maintaining identical scoring logic.
    """
    print(f"\nAI analyzing {len(posts)} posts in BATCHES "
          f"(batch_size=6, workers={GROQ_WORKERS})...")

    analyzed           = []
    help_seeking_count = 0
    results_lock       = threading.Lock()

    # Split posts into batches of 6
    batch_size = 6
    batches = []
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i + batch_size]
        batches.append(batch)
    
    print(f"  Created {len(batches)} batches from {len(posts)} posts")

    def process_batch(batch_posts):
        """Process one batch of up to 6 posts"""
        batch_analyses = analyze_batch_of_posts(batch_posts, user_context)
        
        batch_results = []
        for post, ai_result in zip(batch_posts, batch_analyses):
            is_saved = check_if_lead_saved(post['id'])
            
            analyzed_post = {
                **post,
                'relevancy_score':      ai_result.get('relevancy_score', 0),
                'is_help_seeking':      ai_result.get('is_help_seeking', False),
                'help_seeking_signals': ai_result.get('help_seeking_signals', []),
                'reasoning':            ai_result.get('reasoning', 'N/A'),
                'intent_strength':      ai_result.get('intent_strength', 'low'),
                'potential_value':      ai_result.get('potential_value', 'low'),
                'key_pain_points':      ai_result.get('key_pain_points', []),
                'discovered_at':        datetime.now().isoformat(),
                'ai_response_generated': False,
                'ai_response':          None,
                'is_saved':             is_saved,
            }
            batch_results.append(analyzed_post)
        
        return batch_results

    # Process batches in parallel
    with ThreadPoolExecutor(max_workers=GROQ_WORKERS) as executor:
        future_to_batch = {
            executor.submit(process_batch, batch): batch
            for batch in batches
        }

        completed_batches = 0
        for future in as_completed(future_to_batch):
            completed_batches += 1
            batch = future_to_batch[future]
            
            print(f"   Processed batch {completed_batches}/{len(batches)} "
                  f"({len(batch)} posts)...", end='\r')
            
            try:
                batch_results = future.result()
                
                with results_lock:
                    for result in batch_results:
                        if result.get('is_help_seeking', False):
                            analyzed.append(result)
                            help_seeking_count = len(analyzed)
                            
            except Exception as e:
                print(f"\n[WARN] Batch processing failed: {e}")
                # Continue with other batches

    print(f"\nFound {help_seeking_count} help-seeking posts out of {len(posts)} total")
    analyzed.sort(key=lambda x: x['relevancy_score'], reverse=True)
    return analyzed


# =====================================================
# PAGE ROUTES  (serve HTML templates — unchanged)
# =====================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    return render_template('signup.html')

@app.route('/verify-otp')
def verify_otp_page():
    return render_template('verify_otp.html')

@app.route('/forgot-password')
def forgot_password_page():
    return render_template('forgot_password.html')


# =====================================================
# AUTH DECORATOR  (applied to all mutating routes)
# =====================================================
from functools import wraps

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token   = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = verify_session(token)
        if not session['valid']:
            return jsonify({'success': False, 'message': 'Please login first'}), 401
        request.user_session = session
        return f(*args, **kwargs)
    return decorated


# =====================================================
# API ROUTES
# =====================================================

@app.route('/api/discover-subreddits', methods=['POST'])
@require_auth
def discover_subreddits_endpoint():
    session     = request.user_session
    limit_check = check_query_limit(session['user_id'])
    if not limit_check['allowed']:
        return jsonify({
            'success': False,
            'message': f"Monthly limit reached ({limit_check['query_limit']})"
        }), 429

    data    = request.json
    prompt  = data.get('prompt', '').strip()
    company = data.get('company', '').strip()
    niche   = data.get('niche', '').strip()

    if not prompt:
        return jsonify({'success': False, 'message': 'Provide description'}), 400

    start_time = time.time()
    subreddits = discover_subreddits(prompt, company=company, niche=niche)

    if not subreddits:
        return jsonify({'success': False, 'message': 'Discovery failed'}), 500

    execution_time = time.time() - start_time
    track_query(
        user_id=session['user_id'],
        query_type='discover_subreddits',
        subreddits=[],
        results_count=len(subreddits),
        execution_time=execution_time
    )
    print_api_stats()
    return jsonify({'success': True, 'subreddits': subreddits, 'prompt': prompt})


@app.route('/api/fetch-leads', methods=['POST'])
@require_auth
def fetch_leads():
    session     = request.user_session
    limit_check = check_query_limit(session['user_id'])
    if not limit_check['allowed']:
        return jsonify({
            'success': False,
            'message': f"Monthly limit reached ({limit_check['query_limit']})"
        }), 429

    # ── Input validation ──────────────────────────────────────────────────
    data = request.json
    subreddits          = data.get('subreddits', [])
    prompt              = data.get('prompt', '')
    company             = data.get('company', '').strip()
    niche               = data.get('niche', '').strip()
    posts_per_subreddit = data.get('posts_per_subreddit', 30)

    errors = []
    if not isinstance(subreddits, list) or len(subreddits) == 0:
        errors.append("subreddits must be a non-empty list")
    if len(subreddits) > 15:
        errors.append("maximum 15 subreddits per request")
    if not isinstance(posts_per_subreddit, int) or not (1 <= posts_per_subreddit <= 100):
        posts_per_subreddit = max(1, min(int(posts_per_subreddit or 30), 100))
    if not prompt.strip():
        errors.append("prompt is required")
    if errors:
        return jsonify({'success': False, 'message': '; '.join(errors)}), 400

    # ── Build user context ────────────────────────────────────────────────
    context_lines = []
    if company: context_lines.append(f"Company: {company}")
    if niche:   context_lines.append(f"Niche/Industry: {niche}")
    context_lines.append(f"Description: {prompt}")
    full_context = "\n".join(context_lines)

    # ── Update per-user state ─────────────────────────────────────────────
    uid   = session['user_id']
    state = get_user_state(uid)
    state['user_prompt']      = full_context
    state['user_company']     = company
    state['user_niche']       = niche
    state['discovered_posts'] = []
    # Do NOT reset seen_post_ids here — that deduplicates across searches in
    # the same session, which was the original intent of the global set.

    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"[User {uid}] Searching {len(subreddits)} subreddit(s) IN PARALLEL...")
    if company: print(f"   Company : {company}")
    if niche:   print(f"   Niche   : {niche}")
    print(f"{'='*60}\n")

    # ── Phase 1: Parallel Reddit fetch ───────────────────────────────────
    all_posts = fetch_all_subreddits_parallel(
        subreddits,
        posts_per_subreddit,
        state['seen_post_ids'],   # passed as reference; safely mutated after threads join
        user_id=uid
    )

    print(f"\nTotal posts collected: {len(all_posts)}")

    # ── Phase 2: Parallel Groq analysis ──────────────────────────────────
    analyzed = process_and_analyze_posts_parallel(all_posts, full_context)

#    qualified = [
#        p for p in analyzed
#        if p['relevancy_score'] >= 50 and p.get('is_help_seeking', False)
#    ]
# ── Get dismissed post IDs for this user ──────────────────────────────
    dismissed_ids = get_dismissed_post_ids(uid)
    
    # ── Filter: score >= 50, help-seeking, AND not dismissed ─────────────
    qualified = [
        p for p in analyzed
        if p['relevancy_score'] >= 50 
        and p.get('is_help_seeking', False)
        and p['id'] not in dismissed_ids  # ← NEW: Filter out dismissed
    ]

    state['discovered_posts'] = qualified

    state['discovered_posts'] = qualified

    print(f"\nFinal qualified leads : {len(qualified)}")
    print(f"{'='*60}\n")

    execution_time = time.time() - start_time
    track_query(
        user_id=uid,
        query_type='fetch_leads',
        subreddits=subreddits,
        results_count=len(qualified),
        execution_time=execution_time
    )
    print_api_stats()
    return jsonify({
        'success':         True,
        'total_fetched':   len(all_posts),
        'total_qualified': len(qualified),
        'leads':           qualified[:100]
    })


@app.route('/api/generate-response', methods=['POST'])
@require_auth
def generate_response():
    session = request.user_session
    state   = get_user_state(session['user_id'])

    data    = request.json
    post_id = data.get('post_id')

    if not post_id:
        return jsonify({'success': False, 'message': 'No post ID'}), 400

    post = next((p for p in state['discovered_posts'] if p['id'] == post_id), None)
    if not post:
        return jsonify({'success': False, 'message': 'Post not found'}), 404

    ai_response = generate_ai_response(post, state['user_prompt'])
    post['ai_response_generated'] = True
    post['ai_response']           = ai_response

    return jsonify({'success': True, 'post_id': post_id, 'ai_response': ai_response})


@app.route('/api/save-lead', methods=['POST'])
@require_auth
def save_lead():
    session =    request.user_session
    state   = get_user_state(session['user_id'])

    data    = request.json
    post_id = data.get('post_id')

    if not post_id:
        return jsonify({'success': False, 'message': 'No post ID'}), 400

    post = next((p for p in state['discovered_posts'] if p['id'] == post_id), None)
    if not post:
        return jsonify({'success': False, 'message': 'Post not found'}), 404

    result = save_lead_to_db(post, user_id=session['user_id'])
    if result['success']:
        post['is_saved'] = True

    return jsonify(result)

@app.route('/api/dismiss-post', methods=['POST'])
@require_auth
def dismiss_post_route():
    session = request.user_session
    state   = get_user_state(session['user_id'])

    data    = request.json
    post_id = data.get('post_id')

    if not post_id:
        return jsonify({'success': False, 'message': 'No post ID'}), 400

    result = dismiss_post(session['user_id'], post_id)
    
    if result['success']:
        # Remove from current session's discovered posts
        state['discovered_posts'] = [
            p for p in state['discovered_posts'] if p['id'] != post_id
        ]

    return jsonify(result)

@app.route('/api/saved-leads', methods=['GET'])
@require_auth
def get_saved_leads():
    session   = request.user_session
    min_score = request.args.get('min_score', 0,   type=int)
    limit     = request.args.get('limit',    100,  type=int)
    offset    = request.args.get('offset',   0,    type=int)

    leads = get_all_saved_leads(
        limit=limit, offset=offset,
        min_score=min_score,
        user_id=session['user_id']
    )
    return jsonify({'success': True, 'total': len(leads), 'leads': leads})


@app.route('/api/delete-lead', methods=['POST'])
@require_auth
def delete_lead():
    data    = request.json
    post_id = data.get('post_id')

    if not post_id:
        return jsonify({'success': False, 'message': 'No post ID'}), 400

    result = delete_saved_lead(post_id)
    return jsonify(result)


@app.route('/api/update-notes', methods=['POST'])
@require_auth
def update_notes():
    data    = request.json
    post_id = data.get('post_id')
    notes   = data.get('notes', '')

    if not post_id:
        return jsonify({'success': False, 'message': 'No post ID'}), 400

    result = update_lead_notes(post_id, notes)
    return jsonify(result)


@app.route('/api/mark-contacted', methods=['POST'])
@require_auth
def mark_contacted():
    data      = request.json
    post_id   = data.get('post_id')
    contacted = data.get('contacted', True)

    if not post_id:
        return jsonify({'success': False, 'message': 'No post ID'}), 400

    result = mark_lead_contacted(post_id, contacted)
    return jsonify(result)


@app.route('/api/saved-leads-stats', methods=['GET'])
@require_auth
def saved_leads_stats():
    session = request.user_session
    stats   = get_saved_leads_stats(user_id=session['user_id'])
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/get-leads', methods=['GET'])
@require_auth
def get_leads():
    session   = request.user_session
    state     = get_user_state(session['user_id'])
    min_score = request.args.get('min_score', 50, type=int)

    filtered = [
        p for p in state['discovered_posts']
        if p['relevancy_score'] >= min_score and p.get('is_help_seeking', False)
    ]
    return jsonify({'success': True, 'total': len(filtered), 'leads': filtered})


@app.route('/api/clear-leads', methods=['POST'])
@require_auth
def clear_leads():
    session = request.user_session
    state   = get_user_state(session['user_id'])

    state['discovered_posts'] = []
    state['seen_post_ids']    = set()
    state['user_prompt']      = ''
    return jsonify({'success': True, 'message': 'Cleared'})


@app.route('/api/test-connection', methods=['GET'])
def test_connection():
    results = {'reddit': False, 'groq': False, 'database': False, 'errors': []}

    try:
        with _reddit_lock:
            rate_limit_check()
            reddit.user.me()
        results['reddit'] = True
    except Exception as e:
        results['errors'].append(f"Reddit: {str(e)}")

    try:
        test = call_groq_ai("Test", "Hi", max_tokens=10, token_category='test_connection')
        if test:
            results['groq'] = True
        else:
            results['errors'].append("Groq: No response")
    except Exception as e:
        results['errors'].append(f"Groq: {str(e)}")

    try:
        stats = get_saved_leads_stats()
        if stats is not None:
            results['database'] = True
        else:
            results['errors'].append("Database: Connection failed")
    except Exception as e:
        results['errors'].append(f"Database: {str(e)}")

    return jsonify(results)


# =====================================================
# AUTHENTICATION ROUTES  (completely unchanged)
# =====================================================

@app.route('/api/auth/signup', methods=['POST'])
def api_signup():
    data   = request.json
    result = signup_user(
        email=data.get('email'),
        password=data.get('password'),
        full_name=data.get('full_name')
    )
    if result['success'] and 'otp' in result:
        send_otp_email(data['email'], result['otp'], 'signup')
        del result['otp']
    return jsonify(result)


@app.route('/api/auth/verify-otp', methods=['POST'])
def api_verify_otp():
    data   = request.json
    result = verify_otp(
        email=data.get('email'),
        otp_code=data.get('otp'),
        otp_type=data.get('type', 'signup')
    )
    if result['success'] and data.get('type') == 'signup':
        send_welcome_email(data['email'], data.get('full_name', 'User'))
    return jsonify(result)


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data   = request.json
    result = login_user(
        email=data.get('email'),
        password=data.get('password'),
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    return jsonify(result)


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    token  = request.headers.get('Authorization', '').replace('Bearer ', '')
    result = logout_user(token)
    return jsonify(result)


@app.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    data   = request.json
    result = request_password_reset(data.get('email'))
    if result['success'] and 'otp' in result:
        send_otp_email(data['email'], result['otp'], 'password_reset')
        del result['otp']
    return jsonify(result)


@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    data   = request.json
    result = reset_password(
        email=data.get('email'),
        otp_code=data.get('otp'),
        new_password=data.get('new_password')
    )
    return jsonify(result)


@app.route('/api/auth/check-session', methods=['GET'])
def api_check_session():
    token  = request.headers.get('Authorization', '').replace('Bearer ', '')
    result = verify_session(token)
    return jsonify(result)

@app.route('/api/profile/get', methods=['GET'])
@require_auth
def get_profile():
    session = request.user_session
    profile = get_user_profile(session['user_id'])
    return jsonify({'success': True, 'profile': profile})


@app.route('/api/profile/update', methods=['POST'])
@require_auth
def update_profile():
    session = request.user_session
    data = request.json
    
    result = update_user_profile(
        session['user_id'],
        data.get('company_name', '').strip(),
        data.get('business_niche', '').strip()
    )
    
    return jsonify(result)
# =====================================================
# APP INITIALIZATION & SHUTDOWN  (unchanged)
# =====================================================

@app.before_request
def before_first_request():
    if not hasattr(app, 'db_initialized'):
        print("\nInitializing PostgreSQL (Leads DB)...")
        if init_db_pool():
            app.db_initialized = True
        else:
            print("Failed to connect to Leads DB")

    if not hasattr(app, 'auth_initialized'):
        print("Initializing Auth System...")
        if init_auth_pool():
            app.auth_initialized = True
        else:
            print("Failed to connect to Auth DB")


def shutdown_handler():
    close_db_pool()


if __name__ == '__main__':
    print("=" * 60)
    print("Reddit Lead Discovery - Anatech Consultancy")
    print("=" * 60)
    print("\nApp:      http://localhost:5000")
    print("Login:    http://localhost:5000/login")
    print("Signup:   http://localhost:5000/signup\n")

    try:
        app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
    finally:
        shutdown_handler()
