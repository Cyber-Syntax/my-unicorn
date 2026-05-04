# **🤝 Thank you for considering to contribute!**

I was started writing a script to learn Python, but this became my loved project afterwards when I learned to do more things over time. It was initially a learning project, but now it's a problem-solver and time-saving Python project for me, which has saved me so much time.

## Things that would help

### **How You Can Contribute:**

- **Suggest improvements:** If you have ideas on how to improve the script, feel free to open an issue or submit a pull request.
- **Report bugs:** If you encounter any issues or glitches, please let me know by opening an issue with details about the problem.
- **Documentation:** Contributions to improving the documentation are always welcome.
- **Spread the word:** More user means more people testing and contributing.

### **What You Can Expect:**

- I will review contributions and suggestions when I can, but please note this project is in a **permanent beta phase** and my availability may be limited.
- Since this is a personal project for learning, I can’t guarantee that every contribution will be merged or that I’ll be able to offer extensive feedback.

If you'd like to contribute, please feel free to open a pull request or start a discussion. Thank you for your interest!

### **Release logic:**

- Releases will be created in **release/vX.Y.Z-alpha** branches but some releases maybe create directly on **hotfix/** branches if it's urgent fix for a specific issue without creating a new branch for it.
- Github Actions will automatically create a new release when a new tag is pushed to the repository. The tag should follow the format `vX.Y.Z-alpha` for pre-release versions (e.g., `v2.3.0-alpha`), and `vX.Y.Z` for stable releases (e.g., `v2.3.0`).
- Version bump and changelog update must happen in:
    - the branch where the release tag is created (hotfix/ or release/)
- Versioning follows semantic versioning principles, with the addition of an "alpha" suffix to indicate pre-release versions. For example:
    - `v2.3.0-alpha`: Pre-release version indicating that it's still in development.
    - `v2.3.0-beta`: Pre-release version indicating that it's feature-complete but may still have bugs.
    - `v2.3.0-rc`: Release candidate indicating that it's almost ready for production but may still have minor issues.
    - `v2.3.0`: Stable release indicating that it's ready for production use.

### **Branch Logic:**
>
> [!NOTE]
> Most PR going to main, but if you want to hotfix a specific issue for a specific release, you can create a hotfix branch from the latest tagged release and merge it back to main after the fix is applied. I could also create a hotfix branch for urgent fixes and release new tag from it if needed.

- **main**:
    - Primary development branch.
    - All new features, bug fixes, and improvements should be merged into main.
    - Contains only complete, working changes, no partial implementations or unfinished work.
    - Requires review and approval for pull requests.
- **docs/**: Documentation files. Contributions to improve docs are welcome.
- **feat/**: Feature branches for new features or major changes. These should be merged into main when ready.
- **refactor/**: Refactoring branches for code improvements that do not add new features. These should also be merged into main when ready.
- **fix/**:
    - Created from main
    - For bug fixes that are not urgent enough to require a hotfix branch
    - Must be merged back into main
- **hotfix/**:
    - Created from latest tagged release
    - No new features allowed
    - Must be merged back into main and release branch(if applicable)
    - Only for critical fixes that cannot wait for the next release branch to be created.
    - Branch push new tag via `git tag vX.Y.Z` and `git push origin vX.Y.Z` to trigger release creation for github actions
- **release/**:
    - Created from main
    - No new features allowed
    - Only bug fixes, version bumps, and release prep
    - Must be merged back into main after release
    - Branch push new tag via `git tag vX.Y.Z-alpha` and `git push origin vX.Y.Z-alpha` to trigger release creation for github actions
