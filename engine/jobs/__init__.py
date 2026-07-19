"""Seeding / precompute jobs that write to Neon.

These jobs LIVE IN the open-source (AGPL) engine repo: they are just seeding
scripts that read the engine and write plain rows to Neon, with secrets supplied
via environment variables. The future *private* API reads Neon only and never
links Swiss Ephemeris, which keeps the licensing boundary at this repo.
"""
