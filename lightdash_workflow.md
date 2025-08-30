# Lightdash DevOps & Development Workflow Guide

## 1. Guiding Principles

This document outlines the official "Dashboards as Code" workflow for our Lightdash infrastructure. The primary goal is to maintain a clean, version-controlled, and reliable production environment.

-   **`main` is the Source of Truth:** The `main` branch of this Git repository is the single source of truth for all Lightdash content (charts and dashboards) and dbt models.
-   **Production is a Reflection of `main`:** The production Lightdash instance is a direct reflection of the `main` branch. Our CD pipeline ensures this state is enforced automatically.
-   **All Changes Through Pull Requests:** All modifications to our Lightdash production instance must be implemented as code (`.yml` files for content, `.sql` for models) and merged into `main` via a pull request. **Direct changes to the production UI are strongly discouraged**, as the CD pipeline will overwrite them.

## 2. Infrastructure Overview

-   **Development (Local/Preview):** A local Lightdash server or a temporary `lightdash start-preview` instance is used for all development and previewing of new analytics content.
-   **Production Environment:** A separate, deployed Lightdash instance on GCP Cloud Run serves as our production environment. It is managed automatically by our CI/CD pipeline.

## 3. The "Dashboards as Code" Workflow

This workflow leverages the Lightdash CLI and GitHub Actions to manage the entire lifecycle of analytics development.

### Step 1: Branch and Develop

All work begins by branching from `main`. Because our CD pipeline ensures `main` is always synced with production, you are guaranteed to be starting from the latest version.

1.  **Create a Branch:**
    ```bash
    git checkout main
    git pull origin main
    git checkout -b your-feature-name
    ```
2.  **Make Your Changes:**
    -   Modify dbt models (`.sql`) and schema definitions (`.yml`).
    -   Modify Lightdash content by editing the `.yml` files inside the `lightdash/` directory.

### Step 2: Validate Your Changes Locally

Before committing, it's crucial to validate that your dbt and content changes are compatible.

1.  **Launch a Preview:** Use the `lightdash start-preview` command. This spins up a temporary Lightdash instance that uses your local dbt project and content files.
    ```bash
    lightdash start-preview
    ```
2.  **Test in the Preview:** Open the URL provided by the command. Thoroughly test your new or modified charts and dashboards to ensure they work as expected with your dbt changes.

### Step 3: Commit and Create a Pull Request

Once you have validated your work, commit the changes and open a pull request.

1.  **Add to Git:**
    ```bash
    git add .
    ```
2.  **Commit Your Changes:**
    ```bash
    git commit -m "feat: A clear description of your feature or fix"
    ```
3.  **Push to Remote:**
    ```bash
    git push origin your-feature-name
    ```
4.  **Create a Pull Request** against the `main` branch on GitHub.

### Step 4: Automated CI/CD Pipeline

Once your PR is created, our automated pipeline takes over.

1.  **CI Validation (`CI.yml`):** For every push to your PR, a GitHub Action runs `lightdash validate`. This is our automated gatekeeper that ensures your changes are internally consistent and won't break the project. Your PR can only be merged if this check passes.
2.  **Merge to `main`:** After a successful CI run and a code review, your PR is merged into the `main` branch.
3.  **CD Deployment (`CD.yml`):** The merge to `main` triggers our Continuous Deployment workflow, which performs the following actions automatically:
    -   **Deploys dbt Changes:** Runs `lightdash deploy` to update the production Lightdash instance with any changes to the dbt models.
    -   **Uploads Content Changes:** Runs `lightdash upload --force` to synchronize the charts and dashboards in the production instance with the `.yml` files from the `main` branch.
    -   **Synchronizes Git:** Runs `lightdash download` and commits any differences back to the `main` branch with a `[skip ci]` message. This final step is a self-healing mechanism that ensures Git always remains a perfect mirror of the production state.