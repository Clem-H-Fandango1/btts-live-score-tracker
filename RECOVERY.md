# BTTS Disaster Recovery

## Rebuild from scratch
1. Clone repo
2. Copy `.env.example` to `.env` and set secrets
3. Start with `docker compose up -d --build`
4. Open the site and log in to admin
5. Recreate or restore JSON state files if needed

## Persistent state files
- assignments.json
- groups.json
- next_groups.json
- results.json
- fixtures.json
- season_points.json
- season_stats.json
- game_history.json

These should be backed up separately if you want full continuity.
