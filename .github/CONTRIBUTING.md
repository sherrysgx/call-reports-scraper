# Contributing to WELS Pastor Call Report Scraper

Thank you for your interest in contributing!

## Reporting Bugs

- Use the issue tracker to report bugs
- Include steps to reproduce, error messages or logs, and your OS and Python version
- Include your Chrome version

## Suggesting Enhancements

- Use the issue tracker for feature requests
- Describe the enhancement and why it would be useful
- For new congregation exports, note the congregation name and the keywords needed to match it in the `new_call` field

## Submitting Changes

1. Fork the repository
2. Create a branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Set up the environment:
   ```bash
   pip install -r requirements.txt
   ```
4. Make your changes with clear commit messages
5. Push to your fork and open a pull request with a description of what changed and why

## Style Guidelines

- Follow the existing code style (PEP 8, f-strings, type hints on function signatures)
- Adding a new congregation export? Follow the pattern in `church_exports.py` — add a function using `_export_church()` and register it in `main()`
- Keep docstrings short and factual
- Do not commit files from `data/` or `output/` — they contain scraped data and are gitignored

## Questions

Open an issue to ask questions or discuss ideas.
