"""Convenience generator. Full CSV goes to Drive, NEVER into the Git repo."""

from leo_data_pipeline.cli import main

if __name__ == "__main__":
    main(["generate"])
