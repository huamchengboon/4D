# Build and run scrape_history with Rust

The Rust extension makes fetching many dates in parallel much faster. You only need to build it once (or after changing Rust code).

## 1. Install Rust

**Option A – using mise (recommended):**
```bash
cd /Users/chengboon/Projects/4D
mise install rust
mise use rust@latest
```

**Option B – rustup:**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```
Then restart your terminal or run `source "$HOME/.cargo/env"`.

**Check:** `cargo --version`

## 2. Build the extension

From the project root:

```bash
cd /Users/chengboon/Projects/4D
mise exec -- uv run maturin develop
```

First build can take 1–2 minutes. This compiles the `fetch_4d` crate and installs it into your current Python environment.

## 3. Run the scraper

Same as before; the script will use Rust automatically if the extension is installed:

```bash
mise exec -- uv run python scrape_history.py
```

Or with `uv` only (if Rust is already in your PATH): `uv run python scrape_history.py`

You should see:
```
Using Rust extension for fast parallel fetch.
```

Then it will scrape using the Rust HTTP fetcher.

## Troubleshooting

- **`rustc not in PATH`**  
  Restart the terminal after installing Rust, or run `source "$HOME/.cargo/env"`.

- **`maturin develop` fails**  
  Make sure you’re in the project root and that `fetch_4d/Cargo.toml` and `fetch_4d/src/lib.rs` exist.

- **Python can’t import `fetch_4d`**  
  Run `maturin develop` from the same environment you use for `uv run python` (e.g. activate the venv or use `uv run` for both).
