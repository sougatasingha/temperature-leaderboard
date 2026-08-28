# Temperature Leaderboard

A small Flask web app for ~10 users.

## Features

- Username/password login
- Admin can create users
- Users submit current temperature
- Server records submission time
- Leaderboard ranks users by their latest temperature
- Users can see their recent readings
- Passwords are stored as hashes, not plain text

## Run locally

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY="replace-with-a-long-random-secret"
python app.py
```

Open http://127.0.0.1:5000

The first admin user can be created with this one-time Python command:

```powershell
python -c "from app import init_db,get_db; from werkzeug.security import generate_password_hash; from datetime import datetime,timezone; init_db(); c=get_db(); c.execute('INSERT INTO users(username,password_hash,is_admin,created_at) VALUES (?,?,1,?)',('admin',generate_password_hash('Change123!'),datetime.now(timezone.utc).isoformat())); c.commit(); c.close()"
```

Change the admin password immediately after testing.

## Production deployment

Recommended simple setup:

1. Create a GitHub repository.
2. Push this project.
3. Create a Render Web Service from the GitHub repository.
4. Build command:
   `pip install -r requirements.txt`
5. Start command:
   `gunicorn app:app`
6. Add an environment variable:
   `SECRET_KEY=<long-random-secret>`

### Important database note

SQLite is fine for a tiny prototype, but for a hosted production app use PostgreSQL if the host's filesystem is ephemeral. Otherwise your SQLite data can be lost on redeploy/restart.

For only ~10 users, PostgreSQL + Flask is still very inexpensive and is the better production architecture.

## Possible next improvements

- Daily leaderboard instead of latest-reading leaderboard
- Highest temperature leaderboard
- Prevent multiple submissions within a time window
- User password change
- Admin delete/reset user
- Charts/history
- Mobile-friendly UI
- HTTPS/domain
- PostgreSQL
