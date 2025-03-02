# ER Tool

### A visual database schema explorer that generates Entity-Relationship diagrams from PostgreSQL or MySQL databases. Adding support for other databases is easy.

### This project is the outcome of my long, unsuccessful, search for a simple yet effective tool for visualizing database schemas. I decided to give it a try and roll my own.

![Main Window](docs/images/main-window.png)

**Overview mode:**
![Main Window, overview mode](docs/images/main-window-overview-mode.png)

## Features

- Interactive table filrering (add/remove to the diagram)
- Remove long table prefixes
- Export diagrams as SVG/PNG/PDF
- Overview mode for large schemas
- Zoom and fit controls
- Command Line Interface
- Dark/Light mode support

## Prerequisites

- Python 3.8+
- [**Graphviz**](https://graphviz.org) (`brew install graphviz` on macOS)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/nkanellopoulos/ER_tool.git
cd ER_tool
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

To launch the (GUI) application:
```bash
python ER_Tool.py
```

Connect to your database:
- using the connection dialog
- environment variable:
```bash
export ER_DB_CONNECTION="postgresql://user:pass@host:port/dbname"
```

## Keyboard Shortcuts (on macOS use Cmd instead of Ctrl)

- `Ctrl+B`: Open database connection dialog
- `Ctrl+=`: Zoom in
- `Ctrl+-`: Zoom out
- `Ctrl+0`: Fit view
- `Ctrl+1`: Reset zoom (100%)
- `Ctrl+A`: Select all tables
- `Ctrl+D`: Deselect all tables
- `Ctrl+R`: Refresh diagram
- `Ctrl+S`: Export diagram

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](LICENSE)
