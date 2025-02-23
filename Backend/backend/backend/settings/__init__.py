"""Select an explicit settings profile from APP_ENV."""

import os

APP_ENV = os.getenv('APP_ENV', 'local').strip().lower()

if APP_ENV == 'production':
    from .production import *  # noqa: F403
elif APP_ENV == 'test':
    from .test import *  # noqa: F403
elif APP_ENV == 'local':
    from .local import *  # noqa: F403
else:
    raise RuntimeError(f'Unsupported APP_ENV: {APP_ENV!r}')
