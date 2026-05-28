# getmetera.com Website Deployment

## Current Site

The static website lives in:

- `site/`

Pages:

- `site/index.html`
- `site/privacy.html`
- `site/support.html`
- `site/security.html`

Domain file:

- `site/CNAME`

Current custom domain:

- `getmetera.com`

Support/contact email used in the site:

- `joshua@getmetera.com`

## Recommended First Deployment: GitHub Pages

This is the leanest path because the repo is already on GitHub and the site is static.

The workflow is:

- `.github/workflows/website-pages.yml`

It deploys `site/` to GitHub Pages on pushes to `main` that touch the site.

## Required GitHub Settings

In the GitHub repo:

1. Go to Settings.
2. Open Pages.
3. Set Source to GitHub Actions.
4. Run the `website-pages` workflow.
5. After first deploy, set or confirm the custom domain:
   - `getmetera.com`
6. Enable Enforce HTTPS after DNS is verified.

## Required DNS Records

At the domain/DNS provider, set either an apex GitHub Pages config or use Cloudflare.

For GitHub Pages apex domain:

```text
Type: A
Name: @
Value: 185.199.108.153

Type: A
Name: @
Value: 185.199.109.153

Type: A
Name: @
Value: 185.199.110.153

Type: A
Name: @
Value: 185.199.111.153

Type: CNAME
Name: www
Value: Chukwu-jay.github.io
```

If the Pages site is attached to a different GitHub owner or organization, confirm the GitHub Pages hostname in repo settings before setting `www`.

## Chrome Web Store Use

Use these URLs in Chrome Web Store submission:

- Website: `https://getmetera.com/`
- Privacy policy: `https://getmetera.com/privacy.html`
- Support: `https://getmetera.com/support.html`
- Security contact: `https://getmetera.com/security.html`

## Beta Copy Positioning

Primary message:

> Safe AI reuse across APIs, ChatGPT, and Claude.

Product:

- one product: Metera
- three suites:
  - Control Plane
  - Browser Bridge
  - Workflow Suite

## Deployment Blockers

I need one of the following to deploy live:

- permission to push this branch to GitHub and run the Pages workflow, or
- you push the changes and enable GitHub Pages from Actions, or
- access to a hosting provider such as Cloudflare Pages/Netlify/Vercel.
