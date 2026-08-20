#!/usr/bin/env python3
"""
build_etl_structure.py

Creates the following directory/file layout in the current working directory:

etl/
├── __init__.py
│
├── config/
│   ├── __init__.py
│   └── settings.py
│
├── extract/
│   ├── __init__.py
│   └── base.py
│
├── transform/
│   ├── __init__.py
│   └── base.py
│
├── load/
│   ├── __init__.py
│   └── base.py
│
├── pipelines/
│   ├── __init__.py
│   └── customer_pipeline.py
│
├── validators/
│   ├── __init__.py
│   └── customer_validator.py
│
├── models/
│   └── __init__.py
│
└── utils/
    └── __init__.py

Usage:
    python build_etl_structure.py [target_dir]

    target_dir defaults to the current directory, so the "etl" package
    will be created as ./etl by default.
"""

import os
import sys

# Map of relative file path -> file content
FILES = {
    "__init__.py": '"""ETL package."""\n',

    "config/__init__.py": "",
    "config/settings.py": '''"""
Configuration and settings for the ETL package.
"""

class Settings:
    """Holds ETL configuration values (env vars, connection strings, etc.)."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


settings = Settings()
''',

    "extract/__init__.py": "",
    "extract/base.py": '''"""
Base classes for extraction steps.
"""
from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """Base class that all extractors should inherit from."""

    @abstractmethod
    def extract(self, *args, **kwargs):
        """Extract data from a source and return it."""
        raise NotImplementedError
''',

    "transform/__init__.py": "",
    "transform/base.py": '''"""
Base classes for transformation steps.
"""
from abc import ABC, abstractmethod


class BaseTransformer(ABC):
    """Base class that all transformers should inherit from."""

    @abstractmethod
    def transform(self, data, *args, **kwargs):
        """Transform the given data and return the result."""
        raise NotImplementedError
''',

    "load/__init__.py": "",
    "load/base.py": '''"""
Base classes for load steps.
"""
from abc import ABC, abstractmethod


class BaseLoader(ABC):
    """Base class that all loaders should inherit from."""

    @abstractmethod
    def load(self, data, *args, **kwargs):
        """Load the given data into a destination."""
        raise NotImplementedError
''',

    "pipelines/__init__.py": "",
    "pipelines/customer_pipeline.py": '''"""
Customer ETL pipeline: orchestrates extract -> transform -> load
for customer data.
"""
from etl.extract.base import BaseExtractor
from etl.transform.base import BaseTransformer
from etl.load.base import BaseLoader
from etl.validators.customer_validator import CustomerValidator


class CustomerPipeline:
    """Runs the full ETL process for customer data."""

    def __init__(self, extractor: BaseExtractor, transformer: BaseTransformer,
                 loader: BaseLoader, validator: CustomerValidator = None):
        self.extractor = extractor
        self.transformer = transformer
        self.loader = loader
        self.validator = validator or CustomerValidator()

    def run(self, *args, **kwargs):
        raw_data = self.extractor.extract(*args, **kwargs)
        transformed_data = self.transformer.transform(raw_data)
        self.validator.validate(transformed_data)
        return self.loader.load(transformed_data)
''',

    "validators/__init__.py": "",
    "validators/customer_validator.py": '''"""
Validation logic for customer records.
"""


class CustomerValidator:
    """Validates customer data before it gets loaded."""

    REQUIRED_FIELDS = ("customer_id", "name", "email")

    def validate(self, records):
        """
        Validate a list/iterable of customer records (dicts).
        Raises ValueError if a record is missing required fields.
        """
        for record in records:
            missing = [f for f in self.REQUIRED_FIELDS if f not in record]
            if missing:
                raise ValueError(
                    f"Customer record missing required fields: {missing} -> {record}"
                )
        return True
''',

    "models/__init__.py": "",
    "utils/__init__.py": "",
}

# Directories that must exist even though nothing extra is created,
# it's implied by FILES but listing package dirs explicitly is clearer.
PACKAGE_DIRS = [
    "",
    "config",
    "extract",
    "transform",
    "load",
    "pipelines",
    "validators",
    "models",
    "utils",
]


def build_structure(base_dir: str, package_name: str = "etl") -> str:
    """
    Create the etl/ package structure under base_dir.
    Returns the path to the created package root.
    """
    root = os.path.join(base_dir, package_name)

    for rel_dir in PACKAGE_DIRS:
        dir_path = os.path.join(root, rel_dir) if rel_dir else root
        os.makedirs(dir_path, exist_ok=True)

    for rel_path, content in FILES.items():
        full_path = os.path.join(root, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        if not os.path.exists(full_path):
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"created: {full_path}")
        else:
            print(f"skipped (already exists): {full_path}")

    return root


def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    target_dir = os.path.abspath(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    root = build_structure(target_dir)
    print(f"\nDone. ETL package created at: {root}")


if __name__ == "__main__":
    main()