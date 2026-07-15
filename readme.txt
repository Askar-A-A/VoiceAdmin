Authentication (apps/accounts)

Custom User model — email + password, no username. Fields: email, name (optional), is_active, is_staff, date_joined
Register (/accounts/register/) — creates account, logs in immediately, redirects to dashboard
Login (/accounts/login/) — standard email/password, redirects to /dashboard/
Logout (/accounts/logout/) — POST only, redirects to login
Unauthenticated users are redirected to /accounts/login/ on any protected page
Audio management (apps/audio)

AudioFile model — stores owner (FK to User), name, file_sid, container_sid, uploaded_at
Dashboard (/dashboard/) — shows file count, links to manage and upload
Upload (/audio/upload/) — accepts a file + optional display name, POSTs it to CarrierX, saves the returned file_sid to the DB. 50 MB limit enforced.
List (/audio/) — table of all files belonging to the logged-in user: name, file SID, upload date, delete button
Delete (/audio/<pk>/delete/) — calls CarrierX DELETE endpoint, then removes the DB row. Scoped to the owner so users can't delete each other's files.
Root URL (/) redirects to dashboard
Infrastructure

Settings split into base.py / dev.py, all secrets via .env
PostgreSQL via dj-database-url
Bootstrap 5 (CDN) templates throughout
manage.py check passes clean
What's missing / not yet built

No .env file yet — needs to be created before anything runs
No migrations run yet — DB tables don't exist until makemigrations && migrate
No password reset flow
No account settings (change name/email/password)
No audio preview/playback in the list view
No subscription or billing
No IVR configuration