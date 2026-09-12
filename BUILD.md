The project is divided into two parts:

- **core_lib:** This is a Rust library with PyO3 bindings (`rqs_lib`) that encompasses all the logic necessary for discovering, connecting to, and transferring files to QuickShare-compatible clients.
- **rquickshare_app / main.py:** A Python desktop application built with PySide 6 that utilizes `core_lib` (via PyO3) to handle incoming requests and initiate outgoing ones.

How to build and run
--------------------------

### 1. Prerequisites

System dependencies required:
- `protobuf-compiler`
- `libdbus-1-dev`
- `pkg-config`
- `Python 3.10+`

On Ubuntu/Debian:
```bash
sudo apt-get install -y protobuf-compiler libdbus-1-dev pkg-config python3-pip
```

### 2. Build Python Bindings (`core_lib`)

Install Python build requirements (`PySide6`, `maturin`):

```bash
pip install PySide6 maturin
```

Build and install `rqs_lib` into your Python environment:

```bash
cd core_lib
python3 -m maturin build --release
pip install target/wheels/rqs_lib*.whl --force-reinstall
cd ..
```

### 3. Run Application

Run the PySide 6 application via `main.py`:

```bash
python3 main.py
```
