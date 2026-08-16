#!/usr/bin/env python
import os
import sys

from dotenv import load_dotenv


def main() -> None:
    """Run administrative tasks."""
    load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hero_path.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

