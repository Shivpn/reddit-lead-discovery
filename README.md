# AI-Powered Reddit Lead Discovery Platform
## Anatech Consultancy

A sophisticated, AI-driven system that discovers Reddit leads tailored to your business, scores them for relevance, and generates personalized responses.

---

## 🚀 Key Features

### 1️⃣ **AI Subreddit Discovery**
- Describe your product/service/niche in plain English
- AI analyzes and suggests 8-12 highly relevant subreddits
- Each suggestion includes relevance score and reasoning
- Mix of broad and niche-specific communities

### 2️⃣ **Smart Lead Extraction**
- Fetches posts from last 30 days across selected subreddits
- Pulls from hot, new, and top feeds for comprehensive coverage
- Automatic deduplication
- Rate-limited to respect Reddit's API guidelines

### 3️⃣ **AI-Powered Lead Scoring**
- Each post scored 0-100 on relevance to your business
- Analyzes: buying intent, advice-seeking signals, problem awareness
- Identifies key pain points automatically
- Ranks leads by potential value

### 4️⃣ **AI Response Generation**
- Click "Generate AI Response" on any lead
- AI crafts personalized, helpful responses
- Context-aware based on your business and the post
- Follows Reddit etiquette (helpful first, promotional never)
- One-click copy to clipboard

### 5️⃣ **Beautiful, Smooth UI**
- Professional design (doesn't look AI-generated)
- Smooth animations and transitions
- 3-step wizard workflow
- Real-time stats dashboard
- Responsive on all devices

---

## 🎯 How It Works

### Workflow:

```
Step 1: Describe Business
  ↓
  AI discovers relevant subreddits
  ↓
Step 2: Select Subreddits
  ↓
  System fetches posts (last 30 days)
  ↓
  AI analyzes each post
  ↓
Step 3: Review Ranked Leads
  ↓
  Generate AI responses as needed
  ↓
  Copy & engage manually on Reddit
```

---

## 📦 Installation

### Prerequisites
- Python 3.8+
- Reddit API credentials (free)
- Groq API key (free tier available)

### Quick Setup

1. **Extract the project files**
   ```
   reddit-lead-discovery/
   ├── app.py
   ├── requirements.txt
   ├── .env.example
   ├── templates/
   │   └── index.html
   └── static/
       ├── css/style.css
       └── js/app.js
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Get API Credentials**

   **Reddit:**
   - Go to https://www.reddit.com/prefs/apps
   - Click "Create App" → Select "script"
   - Note your `client_id` and `client_secret`

   **Groq:**
   - Visit https://console.groq.com/
   - Create API key

4. **Configure .env**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env`:
   ```env
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USER_AGENT=LeadDiscovery/1.0 by YourRedditUsername
   GROQ_API_KEY=your_groq_api_key
   FLASK_SECRET_KEY=any_random_string
   ```

5. **Run the app**
   ```bash
   python app.py
   ```

6. **Open browser**
   ```
   http://localhost:5000
   ```

---

## 💡 Usage Guide

### Step 1: Describe Your Business

Enter a detailed description of your product, service, or niche. Be specific!

**Good examples:**
- "I'm a digital marketing consultant helping small e-commerce businesses grow through SEO and paid ads"
- "We sell eco-friendly home cleaning products for health-conscious families"
- "I'm a freelance web developer specializing in React and Next.js for startups"

**Pro tip:** The more detailed your description, the better the subreddit suggestions.

### Step 2: Select Subreddits

- AI suggests 8-12 relevant subreddits
- Each shows:
  - Relevance score (how well it matches your business)
  - Estimated size (large/medium/small)
  - Reasoning (why it's relevant)
- Click cards to select (multiple allowed)
- Hit "Fetch & Analyze Leads"

### Step 3: Review Leads

Leads are ranked by score (highest first):
- **80-100:** Excellent - High intent, very relevant
- **60-79:** Good - Strong potential
- **40-59:** Moderate - Some relevance

Each lead shows:
- Post title and content
- Subreddit and author info
- AI relevance score
- Intent strength (low/medium/high)
- Key pain points identified
- Engagement stats (upvotes, comments)

**Actions:**
- **View on Reddit** → Opens post in new tab
- **Generate AI Response** → Creates personalized reply
- **Copy Response** → Copy AI response to clipboard

---

## 🤖 AI Response Generation

Click "Generate AI Response" on any lead:

1. AI analyzes the post in context of your business
2. Identifies the person's specific pain points
3. Crafts a helpful, genuine response
4. Subtly positions your solution (if appropriate)
5. Follows Reddit's community guidelines

**The AI:**
- Writes naturally (not promotional)
- Addresses specific questions
- Provides real value first
- Mentions your service only if truly relevant

**You should:**
- Review the AI response
- Customize as needed
- Post manually on Reddit
- Never spam or hard-sell

---

## 🔒 Reddit API Compliance

This platform is **100% compliant** with Reddit's API terms:

✅ **Read-only operations** - No automated posting
✅ **Rate limiting** - Max 1 request per second
✅ **Proper authentication** - OAuth2 via PRAW
✅ **Respectful scraping** - Only public data
✅ **Manual engagement** - You post, not the bot

**What this means:**
- Your Reddit API key is safe
- No risk of bans
- All actions are suggestions
- You control what gets posted

---

## 📊 Understanding the Stats

**Total Discovered:** All leads that scored 40+

**Excellent (80+):** Highest priority - strong intent, very relevant

**Good (60-79):** Worth engaging - solid relevance

**Average Score:** Overall lead quality indicator

---

## 🎨 UI Features

### Smooth Animations
- Fade-in effects for content
- Smooth transitions between steps
- Loading states with spinners
- Toast notifications

### Professional Design
- Clean, modern aesthetic
- Not overly polished (avoids "AI-generated" look)
- Anatech branding throughout
- Responsive on mobile/tablet/desktop

### User Experience
- Clear 3-step wizard
- Visual feedback on all actions
- Inline AI responses
- Modal for full response view
- One-click copying

---

## 🛠️ Technical Details

### Backend
- **Framework:** Flask
- **Reddit API:** PRAW (Python Reddit API Wrapper)
- **AI:** Groq (Llama 3.3 70B Versatile)
- **Rate Limiting:** 1 request/second to Reddit

### Frontend
- **HTML5** with semantic markup
- **CSS3** with animations and gradients
- **Vanilla JavaScript** (no framework bloat)

### Data Flow
```
User Input → AI Analysis → Reddit API → AI Scoring → Frontend Display
```

### Storage
- In-memory (no database needed)
- Data persists until app restart
- Easy to add SQLite/PostgreSQL later

---

## 🔧 Troubleshooting

### "Template Not Found" Error
1. Ensure folder structure is correct:
   ```
   templates/index.html
   static/css/style.css
   static/js/app.js
   ```
2. Run from the same directory as `app.py`

### API Connection Fails
1. Click "Test APIs" button
2. Verify credentials in `.env`
3. Check Reddit app type is "script"
4. Ensure Groq API key is valid

### No Subreddits Discovered
1. Make description more detailed (50+ characters recommended)
2. Be specific about your niche
3. Check Groq API quota

### No Leads Found
1. Try different subreddits
2. Lower the minimum score filter
3. Wait - some subreddits have less activity
4. Verify subreddit names are correct

### AI Response Fails
1. Check Groq API quota
2. Ensure post data is loaded
3. Try again (AI calls can occasionally time out)

---

## 💰 API Costs

### Reddit API
- **Free** for personal use
- Rate limit: 60 requests/minute (this app uses ~1/min)

### Groq API
- **Free tier:** 30 requests/minute
- **Cost:** Very low (free tier sufficient for most use)
- Model: Llama 3.3 70B Versatile

**Estimated costs:** $0-5/month for typical usage

---

## ⚠️ Best Practices

### Finding Leads
1. Start with 3-5 subreddits
2. Focus on niche communities first
3. Monitor for a few days before scaling

### Engaging
1. **Always read the full post** before responding
2. **Customize AI suggestions** - don't copy-paste
3. **Add genuine value** - help first, sell never
4. **Follow subreddit rules** - each has unique guidelines
5. **Build relationships** - engage over time

### Avoiding Spam
- Don't post the same response multiple times
- Vary your language
- Space out your responses (don't blast 20 at once)
- Focus on quality over quantity

---

## 🚀 Pro Tips

1. **Use filters effectively:** Start with 70+ score for best leads
2. **Check post age:** Respond to recent posts (< 3 days) for visibility
3. **Read comments:** See what others are suggesting before responding
4. **Track results:** Note which subreddits give best engagement
5. **Iterate:** Refine your business description for better subreddit discovery

---

## 📈 Success Metrics to Track

- **Discovery rate:** Qualified leads per subreddit
- **Engagement rate:** Your responses that get replies
- **Conversion rate:** Leads → conversations → customers
- **Top subreddits:** Which communities work best for your niche

---

## 🔄 Updates & Maintenance

### Regular Tasks
- Check API quotas weekly
- Review and update subreddit list
- Monitor engagement success
- Refine business description as needed

### Future Enhancements (Easy to Add)
- Database for lead persistence
- Email/Slack notifications for high-score leads
- Multiple user prompts/niches
- Chrome extension for quick access
- CRM integration

---

## 📚 Additional Resources

- **Reddit API Docs:** https://www.reddit.com/dev/api
- **PRAW Documentation:** https://praw.readthedocs.io/
- **Groq API Docs:** https://console.groq.com/docs
- **Reddit Marketing Guide:** /r/marketing sidebar

---

## ❓ FAQ

**Q: Will this get my Reddit account banned?**  
A: No. This is read-only and follows all API guidelines. You post manually.

**Q: How many leads can I expect?**  
A: Varies by niche. Typically 10-50 qualified leads per day from 5 subreddits.

**Q: Can I use this for multiple businesses?**  
A: Yes! Clear leads and start a new search with different description.

**Q: Do I need programming knowledge?**  
A: No. Just follow installation steps and use the web interface.

**Q: Can I run this on a server 24/7?**  
A: Yes, but you'll need to manually review leads. Consider adding notifications.

---

## 📞 Support

For issues:
1. Check this README
2. Review error messages in terminal
3. Click "Test APIs" to verify connections
4. Check your `.env` file configuration

---

## 🏆 Why This Solution Works

1. **AI-Powered:** Finds opportunities you'd miss manually
2. **Time-Saving:** Discovers and scores leads automatically
3. **Compliant:** Reddit-safe, no risk of bans
4. **Actionable:** Ready-to-use responses at your fingertips
5. **Professional:** Clean UI, smooth experience

---

**Built by Anatech Consultancy**  
**Version 2.0 - Enhanced Edition**

🎯 **Ready to discover high-quality leads on Reddit!**#   r e d d i t - l e a d - d i s c o v e r y  
 