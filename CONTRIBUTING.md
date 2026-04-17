# Contributing

Thanks for stopping by 😀

This document covers what contributions are welcome and the conventions used in this repo.

## Files we're looking for

### Pictures

Pictures of the headunit (display, buttons, connectors, internal boards) are welcome in the `pictures/` directory. Include the year, make, model, and trim of the vehicle so readers know which hardware revision they're looking at.

### `build.prop` files

Collecting `/system/build.prop` and `/system/vendor/build.prop` files across different vehicles helps map out which headunit versions exist in the wild, which is useful for update compatibility, custom ROM work, and general reverse engineering.

If you can extract these from your headunit (e.g., via ADB or FTP), please add them to `build-props/` with a filename that identifies the vehicle year, make, model, and trim.

### Update files

Software updates are distributed as `SwUpdate2.txt` / `SwUpdate.txt` and `SwUpdate.mtd` files, typically only available to authorized dealers. These files are likely copyrighted, so we can't include them in the repo directly. If you have access to them or know where they can be found, reach out privately: `librick@users.noreply.github.com`.

### Documentation

Official Honda service documentation, schematics, and technical references for the headunit are useful for reverse engineering. These files are likely copyrighted, so we can't include them in the repo directly. If you have access to them or know where they can be found, reach out privately: `librick@users.noreply.github.com`.

## Pre-commit hooks

This project uses [pre-commit](https://pre-commit.com/) to run formatters, linters, and commit-message checks. To set it up:

```bash
uv tool install pre-commit
pre-commit install --install-hooks
```

To run all hooks manually:

```bash
pre-commit run --all-files
```

## Commit messages

Commit messages must follow the format:

`<type>: <description>`

where `<type>` is `feat`, `fix`, or `chore`.

Additionally:

- the description must be in the imperative mood
- the description must be lowercase (i.e., not start with a capital letter)
- the description must not end with a period

Examples:

- `feat: add support for foo`
- `fix: correct off-by-one in bar`
- `chore: bump dependency versions`

Enforced by a `commit-msg` pre-commit hook.

## Branch names

- Use descriptive kebab-case names
- Optionally prefix with the commit type (`feat/`, `fix/`, `chore/`) when it helps organize your work
- If the branch corresponds to an issue, including the issue number is encouraged
- If you include an issue number, place it immediately after the type prefix: `feat/42-add-foo-support`

Examples:

- `feat/add-foo-support`
- `fix/incorrect-bar-handling`
- `fix/42-baz-edge-case`
- `qux-refactor`

## Git branching strategy

1. Fork the repo
1. Create a branch off `main` in your fork, named per the conventions above
1. Commit your changes
1. Open a pull request
1. If the PR resolves an issue, add `Fixes #<issue-number>` to the PR body
