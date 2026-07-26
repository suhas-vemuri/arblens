# GitHub setup for ArbLens

## Recommended beginner route: GitHub Desktop

### 1. Create your GitHub account

Use a professional username that you will be comfortable placing on a résumé. Verify the email address and enable two-factor authentication. Save the recovery codes somewhere secure.

### 2. Install these tools

- GitHub Desktop
- Visual Studio Code
- Python 3.11 or newer

### 3. Configure your identity

Use the same email address in Git that is connected to your GitHub account. This matters because GitHub uses the commit email to associate command-line commits with your profile.

In a terminal:

```bash
git config --global user.name "Suhas Vemuri"
git config --global user.email "YOUR_VERIFIED_GITHUB_EMAIL"
```

Confirm it:

```bash
git config --global --list
```

### 4. Add the downloaded ArbLens folder to GitHub Desktop

1. Unzip the starter repository.
2. Open GitHub Desktop.
3. Choose **File → Add local repository**.
4. Select the `arblens-starter` folder.
5. If GitHub Desktop says the folder is not yet a Git repository, choose **Create a repository**.
6. Set the repository name to `arblens`.
7. Keep the existing README, `.gitignore`, and license files.

### 5. Make the first commit yourself

Review the files before committing. Use a clear message such as:

```text
Initialize ArbLens analytical platform
```

Do not make meaningless commits solely to fill the contribution graph. Each commit should represent a real, reviewable improvement.

### 6. Publish the repository

Choose **Publish repository** in GitHub Desktop.

Recommended settings:

- Name: `arblens`
- Description: `Options-market integrity and static-arbitrage research platform`
- Visibility: Public, once no secret or private data is present
- Keep this code private: unchecked when you are ready to publish

### 7. Protect API credentials

Never place a real token in code, screenshots, notebooks, or the README.

Use:

```text
.env
```

The repository already ignores `.env`. Copy `.env.example` to `.env` and place the token only there.

### 8. Build visible, credible contribution history

A good pattern is one meaningful commit per completed unit of work:

```text
Add Black-Scholes pricing tests
Implement quote validation rules
Detect call monotonicity violations
Add midpoint versus bid-ask dashboard metrics
Document first SPX data sample
```

Push after each real milestone. Open GitHub issues for planned work, close them through pull requests when practical, and keep the default branch passing its tests.

## Optional profile README

After choosing your GitHub username, create a public repository whose name exactly matches that username and place a `README.md` in it. GitHub will display it on your profile.

Suggested profile content:

```markdown
# Hi, I'm Suhas

Computer Engineering student at Texas A&M interested in software engineering, quantitative finance, machine learning, and embedded systems.

## Featured project

- [ArbLens](YOUR_REPOSITORY_URL): options-market integrity and static-arbitrage research platform

## Current focus

- Python and C++
- Data structures and algorithms
- Options mathematics and market microstructure
```

## Command-line alternative

After reviewing and unzipping the project:

```bash
cd arblens-starter
git init
git branch -M main
git add .
git commit -m "Initialize ArbLens analytical platform"
git remote add origin https://github.com/YOUR_USERNAME/arblens.git
git push -u origin main
```

Create an empty `arblens` repository on GitHub before the final two commands. Do not initialize the remote repository with another README because this project already contains one.
