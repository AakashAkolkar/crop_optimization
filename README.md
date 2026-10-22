# Sustainable Crop Planning Optimizer

A Flask web application that allocates crops to fields using **Vogel's Approximation Method (VAM)** and **MODI optimization**, balancing farm profitability with water conservation and environmental sustainability.

Built for the *Computation and Mathematics* Symposium 2024.

## Features

- **Advanced optimization:** VAM for the initial allocation, MODI to reach the optimal solution
- **Three optimization modes** to trade off profit against sustainability
- **Real agricultural data:** 22 crops and 15 regions stored in MySQL
- **Water-aware planning:** field rainfall and scarcity indices feed into the allocation
- **Visual results:** charts generated with Matplotlib and Seaborn
- **Excel export** of the final allocation
- **Demo scenarios:** Small Farmer, Cooperative Farming, and Water Scarcity

## Tech Stack

| Area | Tools |
|------|-------|
| Backend | Python, Flask |
| Database | MySQL |
| Data and optimization | NumPy, pandas |
| Visualization | Matplotlib, Seaborn |
| Export | openpyxl, XlsxWriter |
| Frontend | HTML, Bootstrap 5, jQuery |

## Project Structure

```
symposium-app/
├── app.py                  # Flask app and optimization logic
├── requirements.txt        # Python dependencies
├── .env.example            # Template for environment variables
├── database/
│   ├── setup_database.py   # Creates the database and loads the CSV data
│   ├── crop_data.csv       # Crop yields, prices, fertilizer and water use
│   └── Field_Data.csv      # Field soil, rainfall and scarcity data
└── templates/
    ├── welcome.html        # Landing page
    └── app.html            # Main application interface
```

## Getting Started

### Prerequisites

- Python 3.10 or newer
- MySQL Server running locally

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/AakashAkolkar/crop_optimization.git
   cd crop optimization
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS / Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Copy `.env.example` to `.env` and enter your MySQL password:
   ```bash
   # Windows
   copy .env.example .env
   # macOS / Linux
   cp .env.example .env
   ```

5. **Set up the database**
   ```bash
   python database/setup_database.py
   ```
   This creates the `optimization_project` database and loads the crop and field data. It is safe to re-run.

6. **Run the application**
   ```bash
   python app.py
   ```
   Open http://127.0.0.1:5000 in your browser.

## Usage

1. Open the landing page and click **Launch Application**, or pick a demo scenario.
2. Select crops and fields.
3. Choose an optimization mode and run the optimizer.
4. Review the allocation, charts, and profit and water-use figures.
5. Export the results to Excel.

## Team

- **Aakash Akolkar**: [@AakashAkolkar](https://github.com/AakashAkolkar)
- **Vasavi Agrawal**: [@Vasavi-16](https://github.com/Vasavi-16)



