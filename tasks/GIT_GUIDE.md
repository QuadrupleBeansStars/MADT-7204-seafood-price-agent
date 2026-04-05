# Git Guide for Business Contributors

This guide walks you through the full workflow for completing your task and merging it into the main project — no prior Git experience needed.

---

## Step 0 — One-time setup

Make sure you have Git installed and have cloned the repo:

```bash
git clone https://github.com/QuadrupleBeansStars/MADT-7204-seafood-price-agent.git
cd MADT-7204-seafood-price-agent
```

---

## Step 1 — Get the latest code from main

Always start from the latest version:

```bash
git checkout main
git pull origin main
```

---

## Step 2 — Create your feature branch

Replace `<your-task-name>` with your assigned branch name (see your task card):

```bash
git checkout -b feature/<your-task-name>
```

Example:
```bash
git checkout -b feature/tool-order-cost
```

You are now working on your own isolated copy. Nothing you do will affect `main` until you merge.

---

## Step 3 — Do your work (vibe code it!)

1. Open the file(s) listed in your task card
2. Use Claude or Gemini to generate the code (copy the vibe-code prompt from your task card)
3. Paste the output into the correct file and save

---

## Step 4 — Stage and commit your changes

```bash
git add <filename>
git commit -m "feat: short description of what you did"
```

Example:
```bash
git add agent/tools/seafood_prices.py agent/tools/__init__.py
git commit -m "feat: add calculate_order_cost tool with oil surcharge"
```

Commit message tips:
- Start with `feat:` for new features
- Keep it under 72 characters
- Describe **what** it does, not **how**

---

## Step 5 — Push your branch to GitHub

```bash
git push origin feature/<your-task-name>
```

---

## Step 6 — Open a Pull Request

1. Go to the repo on GitHub
2. You'll see a yellow banner: **"Compare & pull request"** — click it
3. Title: use your commit message
4. Description: briefly explain what you built and how to test it
5. Click **"Create pull request"**

The IT Lead (Nititorn) will review and merge it into `main`.

---

## Common issues

| Problem | Fix |
|---------|-----|
| `git: command not found` | Install Git from git-scm.com |
| `Permission denied` | Ask IT Lead to add you as a collaborator on GitHub |
| Merge conflict | Tell the IT Lead — they'll help resolve it |
| Accidentally edited the wrong file | Run `git checkout -- <filename>` to undo |
