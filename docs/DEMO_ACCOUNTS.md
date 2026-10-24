# Local demo accounts and synthetic responders

This procedure only seeds a local SQLite development database. It refuses other `ENVIRONMENT` values and non-SQLite databases, requires an explicit flag, is repeatable, and does not delete existing rows. Never run demo seeding against production data.

From `backend/`, configure a private `.env` with `ENVIRONMENT=development`, a local SQLite `DATABASE_URL`, and a random `JWT_SECRET` of at least 32 characters, then run:

```sh
python -m app.seed_demo --confirm-demo-seed
```

The first run creates:

- 50 synthetic responders at `demo.responder01@example.test` through `demo.responder50@example.test`.
- One Super Admin, one view-only Co-Admin, and one normal user.
- Ten actual assigned demo incidents and a `DEMO Medical Unit` inventory record.
- Available, assigned, and off-duty responder states. Profiles contain no fake GPS fixes. Demo reports use `example.test` email and simulated text locations.

Passwords for the three administrator/user roles and `demo.responder01` are randomly generated, hashed before persistence, and printed only when those accounts are first created. Save them in a local password manager immediately; they cannot be retrieved or printed again. The other responder passwords are random and intentionally not disclosed. The script never changes existing account passwords. If initial credentials are lost, use the project’s local development database reset procedure only after backing up data, or create another development account through the supported admin workflow.

Public account registration creates only normal users. The demo Co-Admin has only `view_dashboard`. Responder invitations and activation remain available through the real admin flow. These accounts and records are synthetic test data, not real people, live GPS positions, or actual emergency activity.
