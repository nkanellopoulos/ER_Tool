import os
import shutil
import sys


def cleanup_temp_files(temp_files):
    """Clean up temporary files and directories"""
    for path in temp_files:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.exists(path):
                os.unlink(path)
        except Exception as e:
            print(
                f"Error cleaning up temporary file/directory {path}: {e}",
                file=sys.stderr,
            )
