# ⬡ KeyVault — Vercel Deployment

## 📁 Structure
```
keyvault-vercel/
├── api/
│   └── index.py          ← All API routes (serverless Python)
├── public/
│   └── index.html        ← Dashboard UI
├── vercel.json           ← Routing config
├── requirements.txt      ← Python deps (supabase)
└── supabase_schema.sql   ← Run once in Supabase SQL editor
```

---

## 🚀 Deploy to Vercel (3 steps)

### Step 1 — Supabase
1. Go to https://supabase.com → create a free project
2. Go to **SQL Editor** → paste & run `supabase_schema.sql`
3. Go to **Settings → API** → copy:
   - **Project URL**
   - **service_role** secret key

### Step 2 — Push to GitHub
1. Create a new GitHub repo
2. Drop this entire folder into it and push

### Step 3 — Deploy on Vercel
1. Go to https://vercel.com → **Add New Project** → import your GitHub repo
2. Leave all build settings as default
3. Go to **Settings → Environment Variables** and add:

| Name | Value |
|------|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Your service_role key |
| `DASHBOARD_PASSWORD` | A strong password for the dashboard |

4. Click **Redeploy** — your app is live! 🎉

---

## 🔌 Verify API (use in your software)

```
POST https://your-app.vercel.app/api/verify
Content-Type: application/json

{
  "key": "A3fX9kLmQ2pR7nBv",
  "hwid": "DESKTOP-ABC123"
}
```

**Python client example:**
```python
import requests, subprocess

def get_hwid():
    r = subprocess.run(['wmic','csproduct','get','UUID'], capture_output=True, text=True)
    return r.stdout.strip().split('\n')[-1].strip()

def check_license(key):
    r = requests.post("https://your-app.vercel.app/api/verify", json={
        "key": key,
        "hwid": get_hwid()
    }).json()
    if not r["valid"]:
        print(f"❌ {r['reason']}")
        exit(1)
    print("✅ Authenticated!")

check_license(input("License key: "))
```
