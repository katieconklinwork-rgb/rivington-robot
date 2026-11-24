# rivington-robot
Paul and Tina's neighborhood

## How it stays up to date

Every Sunday morning `.github/workflows/weekly-refresh.yml` runs on GitHub and opens a pull request called "Weekly refresh". Merge it to put the week's update live, or close it to skip that week. Nothing changes on the site until it's merged.

It refreshes:
- **Places** (`data/places.json`) from Overture Maps, whenever Overture puts out a new release (about once a month). Katie's census and the robot picks in `tools/refresh/` are always kept.
- **Events** (`data/events.json`) for the next two weeks or so, from Bowery Ballroom, Mercury Lounge and DoNYC listings in the Lower East Side, East Village, Chinatown, Nolita, SoHo and NoHo.
- **The roundup** (`data/roundup.json`): what's new and gone on the map since last week, plus the week's events.

To run it by hand: Actions tab → Weekly refresh → Run workflow.
