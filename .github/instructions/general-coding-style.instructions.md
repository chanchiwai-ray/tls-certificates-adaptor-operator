---
description: General coding style guidelines for the project.
applyTo: "src/**/*.py, tests/**/*.py"
---

# General coding style guidelines

## Quotes

- Prefer double quotes for strings, unless the string contains double quotes, in which case use single quotes to avoid escaping.

## Indentation

- Use 4 spaces per indentation level.

## Constants

- No magic strings or numbers; define them as constants at the top of the file.
- Use uppercase letters with underscores for constant names (e.g., `RENEWAL_THRESHOLD_DAYS`).
- Use a `constants.py` file for project-wide constants.

## SSDLC - logging

- Use the `logging` module for all logging purposes.
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR, CRITICAL).
- Include relevant context (but not confidential information) in log messages to aid in debugging.
- Security events such as user login, user creation, and permission changes should always be logged.

## Functions and methods

- Keep functions and methods focused on a single task (single responsibility principle).
- Dependencies should be passed as arguments (dependency injection) rather than imported directly within the function or method.
- Avoid side effects; functions should not modify global state or have hidden dependencies.
- Arrange public methods before private methods in classes.

## Docstrings

- Use docstrings to document all public classes, methods, and functions (except in `tests/`; but you should include a description on what's being tested).

For example:

```python
#file: src/example.py

"""This module provides an example function to demonstrate docstring usage."""


def calculate_area(radius: float) -> float:
    """Calculate the area of a circle given its radius.

    Args:
        radius (float): The radius of the circle.

    Returns:
        float: The area of the circle.

    Raises:
        ValueError: If the radius is negative.
    """
    pass

def test_calculate_area():
    """Test the calculate_area function."""
    pass

class SampleClass:
    """Summary of class here.

    Longer class information...

    Attributes:
        foo: A string representing the foo attribute.
        bar: An integer representing the bar attribute.
    """

    def __init__(self, foo: str) -> None:
        """Initializes the instance based on foo.

        Args:
            foo: A string representing the foo attribute.
        """
        self.foo = foo
        self.bar = 0

    @property
    def foo_bar(self) -> (str, int):
        """Returns a tuple of foo and bar.

        Returns:
            A tuple containing the foo string and bar integer.
        """
        return self.foo, self.bar
```
