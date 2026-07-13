---
name: publish
description: Automates the version bump, changelog updates, and publishing process for koggi.
---

# Package Publishing Skill

This skill automates the version bump, changelog documentation, and publishing of the `koggi` package.

## Execution Steps

When the user asks to publish or release a new version of the package:

1. **Check Current Version**:
   - Read the current version from `pyproject.toml` and `src/koggi/__init__.py`.
   - Ensure they match.

2. **Analyze Changes & Propose Version Bump & Notes**:
   - Run git commands (e.g., `git status`, `git diff`, or `git log`) to analyze the code changes made since the last release tag.
   - Summarize these changes automatically and propose a draft release description to the user.
   - Propose the appropriate bump type (`patch`, `minor`, or `major`) based on the changes.
   - Confirm the proposed new version, release description, and target (main/test) with the user before proceeding.

3. **Update Version Files**:
   - Modify `pyproject.toml` with the new version.
   - Modify `src/koggi/__init__.py` with the new version.

4. **Update CHANGELOG.md**:
   - Append/prepend the new version, date, and description to `CHANGELOG.md` in the project root. Create the file if it does not exist.

5. **Build and Publish**:
   - Ask the user whether to publish to `main` (default PyPI) or `test` (TestPyPI).
   - Execute the publish command using `bash pp.sh <target>`.

6. **Git Commit & Tag (Optional but Recommended)**:
   - Run `git add` for the updated files.
   - Commit with the message `Release v<new_version>: <description>`.
   - Tag the commit as `v<new_version>`.
