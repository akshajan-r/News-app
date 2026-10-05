# Newsense

A personalised news reader built with Flask: top headlines from NewsAPI,
a clean reader mode, bookmarks, reading streaks and recommendations.

## Run locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
export NEWS_API_KEY=your-key      # Windows: set NEWS_API_KEY=your-key
flask --app app db upgrade
flask --app app run
```

Without `DATABASE_URL` the app uses a local SQLite file (`instance/newsapp.db`).

## Deploy to Render (free)

Render's free web service wipes its disk whenever it restarts or goes to
sleep, so the database has to live somewhere else. Render's own free
Postgres is deleted after 30 days, so use a free [Neon](https://neon.com)
database instead.

1. **Create the database.** Sign up at neon.com, create a project, and copy
   its connection string (it starts with `postgresql://`).
2. **Create the service.** In the [Render dashboard](https://dashboard.render.com)
   choose **New → Blueprint**, connect this GitHub repo and select the branch.
   Render reads `render.yaml` and asks for two values:
   - `NEWS_API_KEY`: your key from [newsapi.org](https://newsapi.org)
   - `DATABASE_URL`: the Neon connection string from step 1
3. **Deploy.** Render installs the requirements, creates the tables and starts
   the site at `https://newsense-xxxx.onrender.com`. `SECRET_KEY` is generated
   for you.
4. **Sign up first.** The first account created on a fresh database becomes the
   admin.

Every push to the deployed branch redeploys automatically.

### Things to know about the free plan

- The site sleeps after 15 minutes without visitors. The next visit takes
  about a minute to wake it up.
- NewsAPI's free Developer plan is intended for development. Check its terms
  before sharing the site widely.
