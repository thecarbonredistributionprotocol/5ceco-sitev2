# 5C Eco Website

Transport emissions measurement infrastructure website with pilot program sign-up pages.

## Structure

```
/
├── index.html                    # Homepage
├── pilot/
│   ├── index.html               # Pilot selection page
│   ├── ghana/
│   │   └── index.html          # Ghana pilot survey
│   └── texas/
│       └── index.html          # Texas pilot survey
└── .github/
    └── workflows/
        └── static.yml          # GitHub Pages deployment
```

## Deployment to GitHub Pages

### Step 1: Create a new repository
1. Go to https://github.com/new
2. Name it something like `5ceco-website`
3. Make it public
4. Don't add README, .gitignore, or license (we already have files)

### Step 2: Push your code
```bash
cd 5ceco-site
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/5ceco-website.git
git push -u origin main
```

### Step 3: Enable GitHub Pages
1. Go to your repository on GitHub
2. Click **Settings** → **Pages**
3. Under "Build and deployment":
   - Source: **GitHub Actions**
4. The workflow will automatically deploy your site

### Step 4: Configure custom domain (optional)
If you want to use 5ceco.com:
1. In GitHub Pages settings, add your custom domain: `5ceco.com`
2. In your domain registrar (where you bought 5ceco.com):
   - Add an A record pointing to GitHub's IPs:
     - 185.199.108.153
     - 185.199.109.153
     - 185.199.110.153
     - 185.199.111.153
   - Or add a CNAME record pointing to: `YOUR_USERNAME.github.io`

Your site will be live at:
- `https://YOUR_USERNAME.github.io/5ceco-website/` (default)
- `https://5ceco.com` (after custom domain setup)

## Pages

- **Homepage** (`/`): Main landing page
- **Pilot Selection** (`/pilot`): Choose Ghana or Texas
- **Ghana Pilot** (`/pilot/ghana`): Ghana driver survey
- **Texas Pilot** (`/pilot/texas`): Texas driver survey

## Contact

contact@5ceco.com
