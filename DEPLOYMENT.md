# Deployment guide

The app needs no secrets. Everything it needs (data and trained models, ~6 MB) is in the repository.
Dependencies are pinned in `requirements.txt` (Python 3.11 or newer).

## 0. Push the code to GitHub

```bash
git remote add origin https://github.com/rajkumardotnet90/Digital-twin.git
git push -u origin main
```

Check that the **CI** workflow (Actions tab) is green before deploying.

## 1. Streamlit Community Cloud (free, recommended)

1. Go to <https://share.streamlit.io> and sign in with GitHub. Authorize access to the repository
   (for a private repo, grant access when prompted).
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Fill in: Repository `rajkumardotnet90/Digital-twin`, Branch `main`, Main file path `app.py`.
4. Open **Advanced settings** and choose **Python 3.11** (3.12 also works). Optional: under **Secrets**,
   add environment-style values, for example `DT_DEFAULT_MODEL = "elasticnet"`.
5. Click **Deploy**. The first build takes a few minutes and ends with a public `*.streamlit.app` URL.
6. Every push to `main` redeploys automatically.

Notes: free apps go to sleep after inactivity - open the URL a few minutes before your demo to wake it.

## 2. Alternative A - Render (Docker)

Option 1, blueprint (uses `render.yaml`):

1. Sign in at <https://render.com> with GitHub.
2. **New +** → **Blueprint** → select the repository → **Apply**.

Option 2, manual:

1. **New +** → **Web Service** → select the repository.
2. Runtime: **Docker**. Instance type: **Free**. Leave the build/start commands empty (the `Dockerfile` is used).
3. Under **Advanced**, set Health Check Path to `/_stcore/health`. Add environment variables if wanted
   (see `.env.example`). Render injects `PORT` automatically and the Dockerfile honours it.
4. **Create Web Service**. The URL looks like `https://digital-twin-aqi.onrender.com`.

Notes: free web services spin down after ~15 minutes idle and take about a minute to wake.

## 3. Alternative B - Hugging Face Spaces (Docker)

1. Create an account at <https://huggingface.co>, then **New** → **Space**. Choose SDK **Docker** → **Blank**,
   hardware **CPU basic (free)**.
2. Clone the Space repo and copy this project into it (all files except `.git`):
   ```bash
   git clone https://huggingface.co/spaces/<your-username>/digital-twin-aqi hf-space
   rsync -a --exclude .git --exclude .venv ./ hf-space/
   ```
3. Put this header at the very top of the Space's `README.md` (replace the file's front matter):
   ```yaml
   ---
   title: Digital Twin AQI
   sdk: docker
   app_port: 8501
   ---
   ```
4. In the Space **Settings → Variables and secrets**, add two variables so Streamlit works inside the Spaces iframe:
   `STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false` and `STREAMLIT_SERVER_ENABLE_CORS=false`.
5. Commit and push (`git add -A && git commit -m "Deploy" && git push`). The Space builds the image and serves it at
   `https://huggingface.co/spaces/<your-username>/digital-twin-aqi`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` on the platform | Make sure the dependency is in `requirements.txt` (not only `requirements-dev.txt`) |
| `Required file not found ... DT_MODEL_DIR` | Model files missing from the deploy; check `data/` and `models/` are committed |
| Model loading error mentioning scikit-learn version | Keep `scikit-learn==1.8.0` - the models were trained with it |
| App stuck on "Please wait" on Hugging Face | Set the two Streamlit variables above and `app_port: 8501` |
| Cold start is slow | Free tiers sleep when idle; open the app before presenting |
