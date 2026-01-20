#!/Users/dsquirre/bin/py_env_mc-cli/bin/python3
"""MC CLI wrapper script."""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), 'src'))

from mc.cli.main import main

if __name__ == '__main__':
    main()
