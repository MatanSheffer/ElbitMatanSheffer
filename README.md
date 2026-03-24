# סוכן מידע גאוגרפי בעברית

צ'אטבוט שמנגיש מידע גאוגרפי-צבאי בזמן אמת, על בסיס שלוש טבלאות נתונים ארגוניות.
הסוכן מקבל שאלות בשפה חופשית בעברית, מתרגם אותן לשאילתות SQL, מריץ על בסיס הנתונים,
ומחזיר תשובה עברית מבוססת עובדות עם הראיות מהדאטה.

## ארכיטקטורה

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  שאלה בעברית │────>│  Qwen3 32B (Groq) │────>│   DuckDB Query   │
│              │     │  מתרגם ל-SQL      │     │   + Spatial Ext  │
└──────────────┘     └───────────────────┘     └────────┬─────────┘
                                                        │
                     ┌───────────────────┐              │ תוצאות
                     │  Qwen3 32B (Groq) │<─────────────┘
                     │  מפרמט תשובה     │
                     └────────┬──────────┘
                              │
                     ┌────────▼──────────┐
                     │  תשובה בעברית    │
                     │  עם ראיות מהדאטה │
                     └───────────────────┘
```

**Flow:** שאלה → LLM מייצר SQL → הרצה על DuckDB → LLM מפרמט תשובה עם ראיות

אם ה-SQL נכשל, השגיאה חוזרת ל-LLM לתיקון עצמי (retry אחד).

## טכנולוגיות

| רכיב | בחירה | סיבה |
|-------|--------|-------|
| LLM | Qwen3 32B on Groq | תמיכה ב-119 שפות כולל עברית, free tier, open-source |
| DB | DuckDB + spatial | embedded, אפס התקנה, פונקציות מרחביות מובנות |
| Pattern | Text-to-SQL | עדיף על function calling עבור joins ושאילתות מרחביות |
| Client | OpenAI SDK | provider-agnostic, קל להחליף ל-Cerebras או ספק אחר |
| Config | python-dotenv | טעינת API key מקובץ .env |

## מבנה הפרויקט

```
├── main.py              # נקודת כניסה - CLI chat loop
├── config.py            # הגדרות (API key, model, paths)
├── requirements.txt
├── .env                 # API key (לא נכלל ב-git)
├── src/
│   ├── database.py      # טעינת Excel ל-DuckDB עם spatial
│   ├── agent.py         # pipeline: SQL generation + answer formatting
│   └── prompts.py       # system prompts עם סכמות הטבלאות
├── assignment_database_v2.xlsx
```

## הנתונים

שלוש טבלאות עם קשרים ביניהן:

- **forces** (466 שורות) — כוחות/חלליות: מיקום, סוג, פלוגה, גדוד, חטיבה
- **sector_boundaries** (72 שורות) — גבולות גזרה: פוליגונים לפי דרג (גדוד/חטיבה)
- **settlements** (257 שורות) — ישובים: פוליגון, מדינה, סוג, שטח

**קשרים:** `forces.gdud` ↔ `sector_boundaries.name`, `forces.hativa` ↔ `sector_boundaries.name`

## התקנה והרצה

```bash
# 1. יצירת virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. התקנת dependencies
pip install -r requirements.txt

# 3. הגדרת API key בקובץ .env
echo "GROQ_API_KEY=your-key-here" > .env

# 4. הרצה
python main.py
```

ניתן להשיג API key בחינם ב-[console.groq.com](https://console.groq.com).

## סוגי שאלות נתמכות

- **שליפה ישירה:** "מה סוג החללית של יחידה א 611 פולסר?"
- **Join בין טבלאות:** "אילו כוחות שייכים לגדוד כיוון 611 ומה גבולות הגזרה שלהם?"
- **שאילתות מרחביות:** "כמה ישובים במרחק של פחות מ-30 ק"מ מהכח חללית פיקוד חץ?"
- **קרבה לנ.צ.:** "מה שלושת הכוחות הכי קרובים לנ.צ. 35.48, 33.02?"
- **אגרגציה:** "כמה כוחות מסוג ט120 יש בסך הכל?"
- **ביקורת:** "כמה חימושים ירה כח X?" → הסוכן מזהה שאין מידע כזה בדאטה ומודיע על כך

## החלטות עיצוב ו-Trade-offs

### למה Text-to-SQL ולא Function Calling?
הדאטה כולל 3 טבלאות עם JOINs ופונקציות מרחביות. ב-function calling היינו צריכים להגדיר מראש פונקציה
לכל סוג שאילתה, מה שמגביל את הגמישות. ב-text-to-SQL ה-LLM יכול לחבר שאילתות מורכבות (JOINs, GROUP BY,
spatial functions) בצורה חופשית. בנוסף, שאילתת ה-SQL עצמה משמשת כראיה שקופה לתשובה.

### למה Qwen3 32B ולא Llama?
Llama 3.3 70B ו-Llama 4 לא תומכים רשמית בעברית (8-12 שפות בלבד).
Qwen3 32B תומך ב-119 שפות כולל עברית, וזמין ב-free tier של Groq.

### למה DuckDB ולא SQLite?
DuckDB כולל extension מרחבי מובנה עם פונקציות כמו `ST_Distance_Spheroid`, `ST_Contains`, `ST_Centroid`.
ב-SQLite היינו צריכים ספריית צד שלישי (spatialite) עם התקנה מורכבת.

### למה Two-step LLM?
שלב 1 מייצר SQL בלבד (ממוקד, קל לדבג). שלב 2 מפרמט תשובה בעברית.
הפרדה זו מונעת "זליגה" בין יצירת קוד לטקסט חופשי, ומאפשרת retry על שגיאות SQL
בלי לאבד את ההקשר.

### מגבלות הפרוטוטיפ
- **אין היסטוריית שיחה** — כל שאלה עומדת בפני עצמה
- **חיפוש שמות fuzzy** — מבוסס LIKE ולא vector similarity, מה שעלול לפספס שמות עם רעש חזק
- **אין ולידציה של SQL** — סומכים על retry מ-LLM במקום AST parsing

## הרחבות אפשריות

- **RAG:** אינדוקס שמות כוחות ב-vector DB לחיפוש fuzzy (לטפל ברעש בשמות)
- **Multi-turn:** שמירת היסטוריית שיחה לשאלות המשך
- **UI:** ממשק Streamlit/Gradio עם מפה אינטראקטיבית
- **Caching:** שמירת תוצאות SQL חוזרות
- **SQL Validation:** בדיקת תקינות SQL לפני הרצה (AST parsing)
- **Fine-tuning:** אימון מודל קטן יותר על דוגמאות text-to-SQL בעברית לשיפור דיוק ומהירות
