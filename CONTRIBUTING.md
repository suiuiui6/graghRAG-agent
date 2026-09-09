# Contributing

1. Open an issue before substantial feature work.
2. Keep provider credentials in ignored `.env` files and keep uploaded documents
   and generated logs out of commits.
3. Backend changes should include the relevant tests under `backend/tests/`.
4. Frontend changes should pass `npm run build` from `frontend/` when the local
   Node dependencies are available.
5. Run `python -B tools/check_public_surface.py` before opening a pull request.

Live MinerU, DeepSeek, OSS, Neo4j, and browser checks are opt-in. Record which
checks were actually run; do not present synthetic fixtures as production proof.
