# assets

Animated SVGs used by the profile README (banner, light lines, code card, tech stack, project cards, protection shield, footer).
They use SMIL animation only, so they play on GitHub without any scripts.

## Live cards (auto-generated)

`hud.svg`, `city.svg` and `langstack.svg` are produced by `scripts/generate_profile_cards.py`
and refreshed every 6 hours by `.github/workflows/profile-cards.yml` (also runs on manual dispatch).
Until the first run they show a neutral "syncing" placeholder. Run `python3 scripts/generate_profile_cards.py --demo`
to regenerate that placeholder offline.
