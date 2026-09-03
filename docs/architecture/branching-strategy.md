# 🌿 Git Branching Strategy

## Branch Structure


## Branch Types

| Branch | Prefix | Purpose | Base Branch | Target |
|--------|--------|---------|-------------|--------|
| Feature | `feature/` | New features | `develop` | `develop` |
| Bugfix | `bugfix/` | Bug fixes | `develop` | `develop` |
| Hotfix | `hotfix/` | Critical fixes | `main` | `main` & `develop` |
| Release | `release/` | Release prep | `develop` | `main` |

## Naming Convention


## Commit Convention


## Workflow

1. Create feature branch from `develop`
2. Develop and commit with conventional commits
3. Create Pull Request to `develop`
4. Pass CI/CD checks (lint, test, build)
5. Get 2 approvals from code owners
6. Merge to `develop`
7. Release branch → `main` with version tag
