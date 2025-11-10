# Contribution Guide

Thank you for contributing to this project!
To maintain code quality and a clean version history, please follow the steps below when submitting your changes.

# 🪄 How to Submit a Pull Request (PR)

## 1️⃣ Fork the Repository

Fork this repository to your GitHub account.

## 2️⃣ Clone to Your Local Machine

```bash
git clone https://github.com/<your-username>/<repository-name>.git
cd <repository-name>
```

## 3️⃣ Switch to the `dev` Branch (Make Sure You Base Your Work on the Latest Code)

```bash
git checkout dev
```

> ⚠️ Always create your feature branch from **`dev`**, not `main`.

## 4️⃣ Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

> Recommended branch naming conventions: `feature/xxx` or `fix/xxx` for easy identification of features or bug fixes.

## 5️⃣ Develop and Test

* Make your code changes while keeping the project’s coding style consistent.
* Ensure that new features or fixes pass all tests.

## 6️⃣ Commit Your Changes

```bash
git add .
git commit -m "type: short description"
```

> It is recommended to follow [Conventional Commits](https://www.conventionalcommits.org/), keeping the commit history clear.

## 7️⃣ Push to Your Remote Repository

```bash
git push origin feature/your-feature-name
```

## 8️⃣ Open a Pull Request

1. Click **New Pull Request** on GitHub.
2. **The target branch must be this repository’s `dev` branch**.
3. Fill in the PR description:

   * Explain the main changes.
   * Link any related issues if applicable.

> ⚠️ Do **not** target the `main` branch with your PR to avoid affecting the stable mainline.
