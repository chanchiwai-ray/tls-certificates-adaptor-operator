---
description: General coding style guidelines for the project.
applyTo: "src/**/*.py, tests/**/*.py"
---

# General coding style guidelines

## Quotes

- Prefer double quotes for strings, unless the string contains double quotes, in which case use single quotes to avoid escaping.

## Constants

- No magic strings or numbers; define them as constants at the top of the file.
- Use uppercase letters with underscores for constant names (e.g., `RENEWAL_THRESHOLD_DAYS`).
- Use a `constants.py` file for project-wide constants.

## SSDLC - logging

- Use the `logging` module for all logging purposes.
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR, CRITICAL).
- Include relevant context (but not confidential information) in log messages to aid in debugging.
- Security events such as user login, user creation, and permission changes should always be logged.

Provide project context and coding guidelines that AI should follow when generating code, answering questions, or reviewing changes.
