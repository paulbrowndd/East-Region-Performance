# East Region Hub & Spoke Dashboard

Shareable browser dashboard for East region spoke and hub performance, based on 4/20-4/23 source data.

## Run locally

Open `index.html` in a browser.

## Add a new day (automated)

1. Put the new Excel file anywhere on your machine.
2. Run:

```bash
python3 update_data.py --xlsx "/Users/paul.brown/Downloads/4_24.xlsx" --date "4/24"
```

This command will:
- update/add the daily snapshot in `data.js`
- rebuild the weekly snapshot using all current daily snapshots

Optional: limit weekly rollup dates (Mon-Sun only):

```bash
python3 update_data.py --xlsx "/Users/paul.brown/Downloads/4_24.xlsx" --date "4/24" --week-dates "4/21,4/22,4/23,4/24,4/25,4/26,4/27"
```

After it updates `data.js`, publish:

```bash
git add data.js
git commit -m "Add 4/24 dashboard data"
git push
```

## Publish on GitHub Pages

1. Create a new GitHub repository.
2. Push this folder to the repository.
3. In GitHub, go to **Settings > Pages**.
4. Set source to **Deploy from a branch**.
5. Select `main` and `/ (root)`.
6. Save and wait 1-2 minutes.

Your dashboard will be available at:

`https://<your-github-username>.github.io/<repo-name>/`
