# Contributing

1. Get it running with the steps in the [README](README.md).
2. Make a branch, keep the change small, and add or update tests for it.
3. Before pushing, run:

```bash
ruff check Backend/backend
pytest
cd Frontend && npm run lint && npm test
```

4. If you change a model, add a migration (`python manage.py makemigrations`).

## Style

- Python: ruff settings in `pyproject.toml`, 100 characters per line.
- JavaScript: ESLint settings in `Frontend/eslint.config.js`.
- Keep comments short and about why, not what.
- Never commit `.env` files, keys or real student data.
