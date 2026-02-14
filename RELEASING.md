# Releasing rectangle-packer

This project now uses a simple release flow centered on Git tags and GitHub
Actions.

## Release steps

1. Ensure `master` is green and up to date.
2. Bump `rpack.__version__` in `rpack/__init__.py`.
3. Update `doc/changelog.rst` and any user-facing docs.
4. Create and push an annotated tag that matches `rpack.__version__`:

   ```sh
   git tag -a X.Y.Z -m "Release X.Y.Z"
   git push upstream X.Y.Z
   ```

5. Create a GitHub Release for that tag and publish it.

## What CI does

- On push/pull request: build wheels and sdist as artifacts.
- On published GitHub Release: upload wheels + sdist to PyPI.

## Notes

- Version is manually maintained in `rpack/__init__.py` and must match the
  release tag (`X.Y.Z`).
- Documentation images are vendored in `doc/_static/img/`.
- Build/release scripts should not rewrite tracked files. CI checks this for
  the sdist build job.
