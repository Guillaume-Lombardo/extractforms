---
name: release
description: Prepare and validate package release workflow for TestPyPI and PyPI.
---

# Release

## Steps
1. Update `version` in `pyproject.toml`.
2. Run full quality pipeline.
3. Build artifacts with `uv run --with build python -m build`.
4. Check metadata with `uv run --with twine python -m twine check dist/*`.
5. Publish using GitHub Actions tag `vX.Y.Z`.

## Notes
- Release workflow supports manual dispatch to TestPyPI.
- Production publish should use tags and trusted publishing.
