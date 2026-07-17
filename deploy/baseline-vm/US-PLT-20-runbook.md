# US-PLT-20 Runbook: Deploy the Stage 1 monolith to vm-baseline-app / vm-baseline-db

Target: `vm-baseline-app` (172.16.200.24) hosts Nginx + the FastAPI monolith.
`vm-baseline-db` (172.16.200.25) hosts PostgreSQL + Redis. Both Ubuntu 24.04, 2 vCPU / 4 GB / 50 GB.

Run each numbered step yourself over SSH; paste back the output if anything errors.

## Phase 0 — Preflight (run on both VMs)

```sh
lsb_release -a               # expect Ubuntu 24.04
sudo -v                      # confirm sudo access
free -h                      # expect ~4 GB
df -h /                      # expect ~50 GB
timedatectl                  # confirm NTP-synced, correct timezone
```

## Phase 1 — vm-baseline-db (172.16.200.25)

1. Install PostgreSQL and Redis:
   ```sh
   sudo apt update
   sudo apt install -y postgresql postgresql-contrib redis-server
   ```

2. Let Postgres listen on the private network, not just localhost — edit
   `/etc/postgresql/*/main/postgresql.conf`:
   ```
   listen_addresses = 'localhost,172.16.200.25'
   ```

3. Allow only `vm-baseline-app` to connect — add to
   `/etc/postgresql/*/main/pg_hba.conf`:
   ```
   host    bookstore    all    172.16.200.24/32    scram-sha-256
   ```

4. Restart Postgres: `sudo systemctl restart postgresql`

5. Firewall — expose 5432/6379 only to the app VM, not the whole subnet:
   ```sh
   sudo ufw allow from 172.16.200.24 to any port 5432
   sudo ufw allow from 172.16.200.24 to any port 6379
   sudo ufw allow OpenSSH
   sudo ufw enable
   ```

6. Redis: bind to the private IP too, and set a password — edit
   `/etc/redis/redis.conf`:
   ```
   bind 127.0.0.1 172.16.200.25
   requirepass <generate one: python3 -c "import secrets; print(secrets.token_urlsafe(24))">
   ```
   Binding to a non-loopback address alone isn't enough: Redis's own
   `protected-mode` (on by default) refuses every non-loopback connection
   until a password is set, independently of firewall rules. Save the
   generated password — you'll need it for the app VM's `REDIS_URL` in
   Phase 2.
   ```sh
   sudo systemctl restart redis-server
   ```

7. Copy `deploy/baseline-vm/db/init.sql` to this VM, replace both
   `CHANGE_ME_*` passwords with real generated values (save them — you'll need
   them for the app VM's `.env` in Phase 2), then run it:
   ```sh
   sudo -u postgres psql -f init.sql
   ```

8. Verify:
   ```sh
   sudo -u postgres psql -d bookstore -c "\dn"     # expect identity, catalog, inventory, orders, migration schemas
   sudo -u postgres psql -d bookstore -c "\du"     # expect migration_admin, bookstore_monolith roles
   ```

## Optional — pgAdmin access from your laptop (SSH tunnel, no firewall changes)

Phase 1 step 5 deliberately restricts port 5432 to `vm-baseline-app` only, per
PMP 21.1 ("PostgreSQL and Redis remain internal") — do **not** add a ufw rule
opening 5432 to your laptop's VPN IP; that would undo the same restriction
Phase 1 just set up. Instead, tunnel through the SSH access you already have:

```sh
# from your Windows machine — leave this running in its own terminal
ssh -N -L 5433:localhost:5432 student@172.16.200.25
```

This forwards your laptop's local port 5433 through the existing SSH
connection to `172.16.200.25`'s own `localhost:5432` — Postgres never sees a
connection from anywhere but its own VM, so nothing in Phase 1's firewall
config needs to change.

In pgAdmin, register a new server:
- Host: `localhost`, Port: `5433`
- Maintenance DB: `bookstore`
- Username: `bookstore_monolith` (the app role already has `SELECT` on every
  table via the default-privilege grant in `init.sql` — no need to use
  `migration_admin` just to look at data)
- Password: whatever you set for `CHANGE_ME_APP` in Phase 1 step 7

Close the SSH tunnel (Ctrl+C) when you're done — it's a manual, on-demand
connection, not something left running permanently.

## Phase 2 — vm-baseline-app (172.16.200.24)

1. Install runtime dependencies:
   ```sh
   sudo apt update
   sudo apt install -y python3.12-venv nginx
   ```

2. From your Windows machine, build the frontend fresh — don't reuse an
   existing `dist/` folder, since it silently goes stale the moment source
   changes and won't error, it'll just serve old UI:
   ```sh
   cd apps/frontend
   npm run build
   cd ../..
   ```
   Then package the monolith code (excluding local junk you don't want on
   the VM) and copy both over:
   ```sh
   # from repo root, in Git Bash
   tar --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
       --exclude='.import_linter_cache' -czf monolith.tar.gz -C apps monolith
   scp monolith.tar.gz student@172.16.200.24:~/
   scp -r apps/frontend/dist student@172.16.200.24:~/frontend-dist
   ```

   Then move the frontend build into a proper web root, out of the home
   directory — Ubuntu home directories default to `750`, which blocks
   Nginx's `www-data` user from ever traversing into them, no matter what
   permissions the files themselves have:
   ```sh
   sudo mkdir -p /var/www/bookstore
   sudo cp -r ~/frontend-dist/* /var/www/bookstore/
   sudo chown -R www-data:www-data /var/www/bookstore
   ```

3. On the app VM, unpack and set up the venv:
   ```sh
   tar -xzf monolith.tar.gz
   cd monolith
   python3.12 -m venv .venv
   .venv/bin/pip install -e .
   ```

4. Create `.env` (copy `.env.example`, then fill in real values — use the
   passwords you generated in Phase 1 step 7, and a fresh JWT secret):
   ```sh
   cp .env.example .env
   python3.12 -c "import secrets; print(secrets.token_urlsafe(32))"   # use output as JWT_SECRET
   nano .env
   ```
   Point both DB URLs at `172.16.200.25` instead of `localhost`, and set
   `REDIS_URL` to include the password from Phase 1 step 6:
   ```
   REDIS_URL=redis://:<password>@172.16.200.25:6379/0
   ```

   Lock it down — `.env` holds real DB passwords and the JWT secret, and the
   default file mode is world-readable:
   ```sh
   chmod 600 /home/student/monolith/.env
   
   ```

5. Run migrations (uses `MIGRATION_DATABASE_URL`, i.e. `migration_admin`):
   ```sh
   .venv/bin/alembic upgrade head
   ```
   Run it a second time immediately after — it should complete with no
   changes and exit 0. That's your evidence for Gate 2's "migrations repeat
   successfully" criterion.

6. Seed data:
   ```sh
   .venv/bin/python scripts/seed_catalog.py
   .venv/bin/python scripts/seed_inventory.py
   ```

7. Create a systemd unit so the app restarts on failure and on reboot —
   `/etc/systemd/system/bookstore-monolith.service`:
   ```ini
   [Unit]
   Description=Bookstore Stage 1 monolith
   After=network.target

   [Service]
   User=student
   WorkingDirectory=/home/student/monolith
   EnvironmentFile=/home/student/monolith/.env
   ExecStart=/home/student/monolith/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```
   Bind to `127.0.0.1` only — Nginx is the sole public entry point, matching
   the PMP's "only frontend/API/monitoring endpoints required for the
   demonstration are exposed" security control.

   ```sh
   sudo systemctl daemon-reload
   sudo systemctl enable --now bookstore-monolith
   sudo systemctl status bookstore-monolith    # expect active (running)
   ```

8. Serve the frontend and reverse-proxy the API — replace
   `/etc/nginx/sites-available/default`:
   ```nginx
   server {
       listen 80;
       server_name _;

       root /var/www/bookstore;
       index index.html;

       location /api/ {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location / {
           try_files $uri $uri/ /index.html;
       }
   }
   ```
   ```sh
   sudo nginx -t
   sudo systemctl reload nginx
   ```

9. Firewall:
   ```sh
   sudo ufw allow OpenSSH
   sudo ufw allow 80/tcp
   sudo ufw enable
   ```

## Phase 3 — Verify (Gate 2 exit criteria)

From your own machine, over the VPN:
```sh
curl http://172.16.200.24/api/books     # expect 16 seeded books, JSON
```
Then in a browser at `http://172.16.200.24/`, walk the full journey:
register → browse → add to cart → checkout → order history — and confirm it
behaves exactly like the local version already verified in Period 1.

Report back: any step's error output, plus confirmation of the final
browser walkthrough, and I'll mark US-PLT-20 done in `sprint-plan.md`.
