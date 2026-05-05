---
description: Code review guidelines for the project.
applyTo: "src/**/*.py tests/**/*.py"
---

# Code review guidelines

When reviewing code, please consider the following guidelines to ensure consistency, maintainability, and quality across the project:

## Coding Style

- Check for consistent use of whitespace, indentation, and line breaks.
- Ensure security events are properly logged and that no confidential information is included in log messages.
- Ensure that the code is human readable and follows the project's coding style guidelines (e.g., PEP 8 for Python).
- Look for any instances of "magic numbers" or hardcoded values that should be defined as constants.
- Verify that variable and function names are descriptive and follow naming conventions.

## Documentation

- Check for typos and grammatical errors in docstrings and comments.
- Ensure that docstrings are clear, concise, and follow the project's style guidelines.
- Ensure that all public classes, methods, and functions have appropriate docstrings that follow the project's style guidelines.

## Design principles

- Ensure that S.O.L.I.D principles are followed.
- Ensure charm design patterns are followed. Ask yourself the following questions:
  - Is there `config.py` for configuration management?
  - Does `state.py` aggregate the charm config, and data from relation handlers?
  - Does `state.py` provides all the data required to configure the workloads / services or write back to the relation databag?
  - Do you see there extra logic to process the data in `charm.py` that should be moved to `state.py` or the relation handlers?
  - Does the relations handlers has proper public methods to get or set data to the relation databag?
  - Does the relations handlers put the necessary data in the state as an attribute after processing the data from the relation databag?
  - Does the relations handlers use the state to write back to the relation databag?
  - Does the reconcile method in `charm.py` only call the public methods of the relation handlers and use the state to configure the workloads / services?

## Dead code and unnecessary comments

- Is there unused public methods, variables, or imports that should be removed?
- Is there commented out code that should be removed?
- Is there commented out code that should be uncommented or removed?
