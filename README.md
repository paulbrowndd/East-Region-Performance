# East Region Hub & Spoke Dashboard

Shareable browser dashboard for East region spoke and hub performance. Daily snapshots currently include **4/20 through 4/26** (update `data.js` with `update_data.py` when you add more days).

## Run locally

Open `index.html` in a browser.

## Add a new day (automated)

1. Put the new Excel file anywhere on your machine.
2. Run:

```bash
python3 update_data.py --xlsx "/Users/paul.brown/Downloads/4_25.xlsx" --date "4/25"
```

This command will:
- update/add the daily snapshot in `data.js`
- rebuild the weekly snapshot using all current daily snapshots

Optional: limit weekly rollup dates (Mon-Sun only):

```bash
python3 update_data.py --xlsx "/Users/paul.brown/Downloads/4_25.xlsx" --date "4/25" --week-dates "4/21,4/22,4/23,4/24,4/25,4/26,4/27"
```

After it updates `data.js`, publish:

```bash
git add data.js
git commit -m "Add 4/25 dashboard data"
git push
```

## Re-upload to GitHub (replace site files)

If you update the site by uploading files in the GitHub web UI, upload everything at the **root** of the repo (same folder as `index.html`):

- `index.html`
- `styles.css`
- `app.js`
- `data.js` (this is what changes when you add a new day)
- `README.md` (optional but recommended)
- `update_data.py` (optional; handy for your next Excel import)

You do **not** need to upload the hidden `.git` folder when using the website upload flow.

## Publish on GitHub Pages

1. Create a new GitHub repository.
2. Push this folder to the repository.
3. In GitHub, go to **Settings > Pages**.
4. Set source to **Deploy from a branch**.
5. Select `main` and `/ (root)`.
6. Save and wait 1-2 minutes.

Your dashboard will be available at:

`https://<your-github-username>.github.io/<repo-name>/`
